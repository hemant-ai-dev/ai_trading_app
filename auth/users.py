"""User authentication against data/users.xlsx. No SQL Server. Passwords are hashed."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from auth.excel_store import (
    count_admins,
    count_users,
    find_by_id,
    find_user,
    load_rows,
    upsert_user,
    workbook_path,
)
from auth.passwords import hash_password, validate_password_strength, validate_signup, verify_password


@dataclass(frozen=True)
class UserRecord:
    user_id: int
    username: str
    email: str
    role: str = "User"
    is_active: bool = True
    must_change_password: bool = False


def _row_user(row: dict[str, Any]) -> UserRecord:
    return UserRecord(
        user_id=int(row["UserId"]),
        username=str(row["Username"]),
        email=str(row["Email"]),
        role=str(row.get("Role") or "User"),
        is_active=bool(int(row.get("IsActive", 1))),
        must_change_password=bool(int(row.get("MustChangePassword", 0))),
    )


def init_user_store() -> None:
    workbook_path()
    load_rows()
    _maybe_bootstrap_admin()


def _maybe_bootstrap_admin() -> None:
    username = (os.getenv("ANGAD_BOOTSTRAP_ADMIN_USERNAME") or "").strip()
    password = os.getenv("ANGAD_BOOTSTRAP_ADMIN_PASSWORD") or ""
    email = (os.getenv("ANGAD_BOOTSTRAP_ADMIN_EMAIL") or "admin@local").strip().lower()
    try:
        import streamlit as st

        secrets_auth = st.secrets.get("auth") if hasattr(st, "secrets") else None
        if isinstance(secrets_auth, dict):
            username = str(secrets_auth.get("username") or username).strip()
            password = str(secrets_auth.get("password") or password)
            email = str(secrets_auth.get("email") or email).strip().lower()
    except Exception:
        pass
    if not username or not password:
        return
    if count_admins() > 0:
        return
    existing = find_user(username) or find_user(email)
    if existing:
        existing["Role"] = "Admin"
        existing["IsActive"] = 1
        saved = upsert_user(existing)
        _mirror_sqlite(saved)
        return
    if validate_signup(username, email, password):
        return
    saved = upsert_user(
        {
            "Username": username,
            "Email": email,
            "PasswordHash": hash_password(password),
            "Role": "Admin",
            "IsActive": 1,
            "MustChangePassword": 0,
            "ResetPending": 0,
            "LastLoginAt": "",
        }
    )
    _mirror_sqlite(saved)


def create_user(
    username: str,
    email: str,
    password: str,
    *,
    role: str | None = None,
) -> tuple[UserRecord | None, str | None]:
    init_user_store()
    err = validate_signup(username, email, password)
    if err:
        return None, err
    username = username.strip()
    email = email.strip().lower()
    if find_user(username) or find_user(email):
        return None, "That username or email is already registered."
    assigned = role if role in ("Admin", "User") else ("Admin" if count_users() == 0 else "User")
    saved = upsert_user(
        {
            "Username": username,
            "Email": email,
            "PasswordHash": hash_password(password),
            "Role": assigned,
            "IsActive": 1,
            "MustChangePassword": 0,
            "ResetPending": 0,
            "LastLoginAt": "",
        }
    )
    _mirror_sqlite(saved)
    return _row_user(saved), None


def get_user_by_id(user_id: int) -> UserRecord | None:
    init_user_store()
    row = find_by_id(user_id)
    return _row_user(row) if row else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    init_user_store()
    return find_user(username)


def authenticate(username: str, password: str) -> tuple[UserRecord | None, str | None]:
    init_user_store()
    if not username or not password:
        return None, "Enter username and password."
    row = find_user(username)
    if row is None:
        if count_users() == 0:
            return None, "No accounts in the user Excel file yet. Use Sign up on this site."
        return None, "Invalid username or password."
    if not verify_password(password, str(row.get("PasswordHash") or "")):
        return None, "Invalid username or password."
    if not int(row.get("IsActive", 1)):
        return None, "This account is inactive."
    row["LastLoginAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        upsert_user(row)
    except OSError:
        pass
    try:
        _mirror_sqlite(row)
    except Exception:
        pass
    return _row_user(row), None


def change_password(user_id: int, current_password: str, new_password: str) -> str | None:
    row = find_by_id(user_id)
    if not row:
        return "User not found."
    if not verify_password(current_password, str(row.get("PasswordHash") or "")):
        return "Current password is incorrect."
    err = validate_password_strength(new_password, str(row["Username"]), str(row["Email"]))
    if err:
        return err
    row["PasswordHash"] = hash_password(new_password)
    row["MustChangePassword"] = 0
    upsert_user(row)
    return None


def request_password_reset(identifier: str) -> None:
    init_user_store()
    row = find_user(identifier)
    if not row:
        return
    row["ResetPending"] = 1
    upsert_user(row)


def admin_reset_password(user_id: int) -> tuple[str | None, str | None]:
    row = find_by_id(user_id)
    if not row:
        return None, "User not found."
    temp = secrets.token_urlsafe(10)
    row["PasswordHash"] = hash_password(temp)
    row["MustChangePassword"] = 1
    row["ResetPending"] = 0
    upsert_user(row)
    _mirror_sqlite(row)
    return temp, None


def _mirror_sqlite(row: dict[str, Any]) -> None:
    """Keep a stub SQLite row so paper tasks/predictions can reference UserId. Login never reads it."""
    try:
        from db.database import get_connection

        uid = int(row.get("UserId") or 0)
        if uid <= 0:
            return
        stub = str(row.get("PasswordHash") or "xlsx-auth")
        with get_connection(commit=True) as cn:
            cn.execute(
                """
                INSERT INTO TReadUser (
                    UserId, Username, Email, PasswordHash, Role, IsActive, MustChangePassword
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(UserId) DO UPDATE SET
                    Username=excluded.Username,
                    Email=excluded.Email,
                    Role=excluded.Role,
                    IsActive=excluded.IsActive
                """,
                (
                    uid,
                    str(row.get("Username") or f"user{uid}"),
                    str(row.get("Email") or f"user{uid}@local"),
                    stub,
                    str(row.get("Role") or "User"),
                    int(row.get("IsActive", 1)),
                    int(row.get("MustChangePassword", 0)),
                ),
            )
    except Exception:
        return
