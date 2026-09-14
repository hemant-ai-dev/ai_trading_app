"""Admin operations on TReadUser — never returns password hashes to the UI."""

from __future__ import annotations

from typing import Any

from db.database import fetch_all, fetch_one, get_connection


SAFE_COLUMNS = (
    "UserId",
    "Username",
    "Email",
    "Role",
    "IsActive",
    "MustChangePassword",
    "CreatedAt",
    "UpdatedAt",
    "LastLoginAt",
)


def _select() -> str:
    return ", ".join(SAFE_COLUMNS)


def list_users(
    *,
    search: str = "",
    role: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if search.strip():
        q = f"%{search.strip()}%"
        clauses.append("(Username LIKE ? OR Email LIKE ?)")
        params.extend([q, q])
    if role in ("Admin", "User"):
        clauses.append("Role = ?")
        params.append(role)
    if status == "Active":
        clauses.append("IsActive = 1")
    elif status == "Inactive":
        clauses.append("IsActive = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"SELECT {_select()} FROM TReadUser {where} ORDER BY CreatedAt DESC",
        tuple(params),
    )


def get_user(user_id: int) -> dict[str, Any] | None:
    return fetch_one(
        f"SELECT {_select()} FROM TReadUser WHERE UserId = ?",
        (int(user_id),),
    )


def set_active(user_id: int, active: bool) -> None:
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TReadUser
            SET IsActive = ?, UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ?
            """,
            (1 if active else 0, int(user_id)),
        )


def set_role(user_id: int, role: str) -> str | None:
    if role not in ("Admin", "User"):
        return "Invalid role."
    if role == "User":
        remaining = fetch_one(
            "SELECT COUNT(*) AS n FROM TReadUser WHERE Role = 'Admin' AND UserId <> ?",
            (int(user_id),),
        )
        if remaining and int(remaining["n"]) == 0:
            return "Cannot remove the last administrator."
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TReadUser
            SET Role = ?, UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE UserId = ?
            """,
            (role, int(user_id)),
        )
    return None


def delete_user(user_id: int, *, actor_id: int) -> str | None:
    if int(user_id) == int(actor_id):
        return "You cannot delete your own account while signed in."
    target = get_user(user_id)
    if not target:
        return "User not found."
    if target.get("Role") == "Admin":
        remaining = fetch_one(
            "SELECT COUNT(*) AS n FROM TReadUser WHERE Role = 'Admin' AND UserId <> ?",
            (int(user_id),),
        )
        if remaining and int(remaining["n"]) == 0:
            return "Cannot delete the last administrator."
    with get_connection() as cn:
        cn.execute("DELETE FROM TReadUser WHERE UserId = ?", (int(user_id),))
    return None


def pending_resets() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT r.ResetId, r.UserId, r.RequestedAt, u.Username, u.Email
        FROM TPasswordReset r
        JOIN TReadUser u ON u.UserId = r.UserId
        WHERE r.Status = 'pending'
        ORDER BY r.RequestedAt DESC
        """
    )
