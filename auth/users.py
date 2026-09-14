"""TReadUser authentication against SQLite."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any

from auth.passwords import hash_password, validate_password_strength, validate_signup, verify_password
from db.bootstrap import initialize
from db.database import DatabaseError, fetch_all, fetch_one, get_connection


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    username: str
    email: str
    role: str = "User"
    is_active: bool = True
    must_change_password: bool = False


def init_user_store() -> None:
    initialize()
    _maybe_bootstrap_admin()


def _row_user(row: dict[str, Any]) -> UserRecord:
    return UserRecord(
        user_id=int(row["UserId"]),
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row.get("Role") or "User"),
        is_active=bool(row.get("IsActive", 1)),
        must_change_password=bool(row.get("MustChangePassword", 0)),
    )


def _count_users() -> int:
    row = fetch_one("SELECT COUNT(*) AS n FROM TReadUser")
    return int(row["n"]) if row else 0


def _count_admins() -> int:
    row = fetch_one("SELECT COUNT(*) AS n FROM TReadUser WHERE Role = 'Admin'")
    return int(row["n"]) if row else 0


def _maybe_bootstrap_admin() -> None:
    username = (os.getenv("ANGAD_BOOTSTRAP_ADMIN_USERNAME") or "").strip()
    password = os.getenv("ANGAD_BOOTSTRAP_ADMIN_PASSWORD") or ""
    email = (os.getenv("ANGAD_BOOTSTRAP_ADMIN_EMAIL") or "admin@local").strip().lower()
    if not username or not password:
        return
    if _count_admins() > 0:
        return
    existing = fetch_one("SELECT UserId FROM TReadUser WHERE Username = ?", (username,))
    if existing:
        with get_connection() as cn:
            cn.execute(
                "UPDATE TReadUser SET Role = 'Admin', UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE UserId = ?",
                (int(existing["UserId"]),),
            )
        return
    err = validate_signup(username, email, password)
    if err:
        return
    with get_connection() as cn:
        cn.execute(
            """
            INSERT INTO TReadUser (Username, Email, PasswordHash, Role, IsActive)
            VALUES (?, ?, ?, 'Admin', 1)
            """,
            (username, email, hash_password(password)),
        )


def create_user(
    username: str,
    email: str,
    password: str,
    *,
    role: str | None = None,
) -> tuple[UserRecord | None, str | None]:
    try:
        init_user_store()
    except DatabaseError as exc:
        return None, str(exc)
    err = validate_signup(username, email, password)
    if err:
        return None, err
    username = username.strip()
    email = email.strip().lower()
    assigned = role if role in ("Admin", "User") else ("Admin" if _count_users() == 0 else "User")
    try:
        with get_connection() as cn:
            taken = cn.execute(
                "SELECT Username, Email FROM TReadUser WHERE Username = ? OR Email = ?",
                (username, email),
            ).fetchone()
            if taken:
                return None, "That username or email is already registered."
            cur = cn.execute(
                """
                INSERT INTO TReadUser (Username, Email, PasswordHash, Role, IsActive)
                VALUES (?, ?, ?, ?, 1)
                """,
                (username, email, hash_password(password), assigned),
            )
            user_id = int(cur.lastrowid)
        row = fetch_one("SELECT * FROM TReadUser WHERE UserId = ?", (user_id,))
        return _row_user(row), None  # type: ignore[arg-type]
    except DatabaseError as exc:
        msg = str(exc).lower()
        if "unique" in msg:
            return None, "That username or email is already registered."
        return None, str(exc)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    init_user_store()
    ident = username.strip()
    return fetch_one(
        "SELECT * FROM TReadUser WHERE Username = ? OR Email = ?",
        (ident, ident.lower()),
    )


def authenticate(username: str, password: str) -> tuple[UserRecord | None, str | None]:
    try:
        init_user_store()
    except DatabaseError as exc:
        return None, str(exc)
    if not username or not password:
        return None, "Enter username and password."
    try:
        row = get_user_by_username(username)
    except DatabaseError as exc:
        return None, str(exc)
    if row is None or not verify_password(password, str(row["PasswordHash"])):
        return None, "Invalid username or password."
    if not int(row.get("IsActive", 1)):
        return None, "This account is inactive."
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TReadUser
            SET LastLoginAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ?
            """,
            (int(row["UserId"]),),
        )
    return _row_user(row), None


def change_password(user_id: int, current_password: str, new_password: str) -> str | None:
    row = fetch_one("SELECT * FROM TReadUser WHERE UserId = ?", (int(user_id),))
    if not row:
        return "User not found."
    if not verify_password(current_password, str(row["PasswordHash"])):
        return "Current password is incorrect."
    err = validate_password_strength(new_password, str(row["Username"]), str(row["Email"]))
    if err:
        return err
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TReadUser
            SET PasswordHash = ?, MustChangePassword = 0,
                UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ?
            """,
            (hash_password(new_password), int(user_id)),
        )
    return None


def request_password_reset(identifier: str) -> None:
    """Record a reset request. Always behaves the same to the caller (no account enumeration)."""
    init_user_store()
    row = get_user_by_username(identifier)
    if not row:
        return
    with get_connection() as cn:
        cn.execute(
            "INSERT INTO TPasswordReset (UserId, Status) VALUES (?, 'pending')",
            (int(row["UserId"]),),
        )


def admin_reset_password(user_id: int) -> tuple[str | None, str | None]:
    """Set a new random password. Returns (temporary_password, error). Shown once to admin."""
    row = fetch_one("SELECT UserId FROM TReadUser WHERE UserId = ?", (int(user_id),))
    if not row:
        return None, "User not found."
    temp = secrets.token_urlsafe(10)
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TReadUser
            SET PasswordHash = ?, MustChangePassword = 1,
                UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ?
            """,
            (hash_password(temp), int(user_id)),
        )
        cn.execute(
            """
            UPDATE TPasswordReset
            SET Status = 'completed', CompletedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ? AND Status = 'pending'
            """,
            (int(user_id),),
        )
    return temp, None
