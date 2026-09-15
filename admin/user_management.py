"""Admin operations on the Excel user workbook — never returns password hashes."""

from __future__ import annotations

from typing import Any

from auth.excel_store import find_by_id, load_rows, save_rows, upsert_user

SAFE_KEYS = (
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


def _safe(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in SAFE_KEYS}


def list_users(*, search: str = "", role: str = "", status: str = "") -> list[dict[str, Any]]:
    rows = [_safe(r) for r in load_rows()]
    q = search.strip().lower()
    out = []
    for r in rows:
        if q and q not in str(r.get("Username", "")).lower() and q not in str(r.get("Email", "")).lower():
            continue
        if role in ("Admin", "User") and str(r.get("Role")) != role:
            continue
        if status == "Active" and int(r.get("IsActive") or 0) != 1:
            continue
        if status == "Inactive" and int(r.get("IsActive") or 0) == 1:
            continue
        out.append(r)
    out.sort(key=lambda r: str(r.get("CreatedAt") or ""), reverse=True)
    return out


def get_user(user_id: int) -> dict[str, Any] | None:
    row = find_by_id(user_id)
    return _safe(row) if row else None


def set_active(user_id: int, active: bool) -> None:
    row = find_by_id(user_id)
    if not row:
        return
    row["IsActive"] = 1 if active else 0
    upsert_user(row)


def set_role(user_id: int, role: str) -> str | None:
    if role not in ("Admin", "User"):
        return "Invalid role."
    rows = load_rows()
    if role == "User":
        admins = [r for r in rows if str(r.get("Role")) == "Admin" and int(r.get("UserId") or 0) != int(user_id)]
        if not admins:
            return "Cannot remove the last administrator."
    row = find_by_id(user_id)
    if not row:
        return "User not found."
    row["Role"] = role
    upsert_user(row)
    return None


def delete_user(user_id: int, *, actor_id: int) -> str | None:
    if int(user_id) == int(actor_id):
        return "You cannot delete your own account while signed in."
    target = find_by_id(user_id)
    if not target:
        return "User not found."
    rows = load_rows()
    if str(target.get("Role")) == "Admin":
        others = [r for r in rows if str(r.get("Role")) == "Admin" and int(r.get("UserId") or 0) != int(user_id)]
        if not others:
            return "Cannot delete the last administrator."
    keep = [r for r in rows if int(r.get("UserId") or 0) != int(user_id)]
    save_rows(keep)
    return None


def pending_resets() -> list[dict[str, Any]]:
    out = []
    for r in load_rows():
        if int(r.get("ResetPending") or 0) == 1:
            out.append(
                {
                    "ResetId": int(r.get("UserId") or 0),
                    "UserId": int(r.get("UserId") or 0),
                    "RequestedAt": r.get("UpdatedAt"),
                    "Username": r.get("Username"),
                    "Email": r.get("Email"),
                }
            )
    return out
