"""Bearer tokens for the internal FastAPI layer. Raw tokens are never stored."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from db.database import execute, fetch_one, get_connection

TOKEN_TTL_HOURS = 12


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(user_id: int, *, label: str = "api") -> tuple[str, datetime]:
    raw = "angad_" + secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    execute(
        """
        INSERT INTO TApiToken (UserId, TokenHash, Label, ExpiresAt)
        VALUES (?, ?, ?, ?)
        """,
        (int(user_id), _hash(raw), label[:80], expires.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    return raw, expires


def resolve_token(raw: str) -> dict[str, Any] | None:
    if not raw or not raw.startswith("angad_"):
        return None
    row = fetch_one(
        """
        SELECT t.TokenId, t.UserId, t.ExpiresAt, t.Label,
               u.Username, u.Email, u.Role, u.IsActive
        FROM TApiToken t
        LEFT JOIN TReadUser u ON u.UserId = t.UserId
        WHERE t.TokenHash = ?
        """,
        (_hash(raw),),
    )
    if not row:
        return None
    try:
        exp = datetime.fromisoformat(str(row["ExpiresAt"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        return None
    if row.get("IsActive") is not None and int(row["IsActive"]) != 1:
        return None
    with get_connection() as cn:
        cn.execute(
            "UPDATE TApiToken SET LastUsedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE TokenId = ?",
            (int(row["TokenId"]),),
        )
    return dict(row)
