"""Append-only AI decision trail. Original predictions stay in TPrediction."""

from __future__ import annotations

import json
from typing import Any

from db.database import execute, fetch_all


def log_decision(
    *,
    user_id: int | None,
    action: str,
    instrument: str | None = None,
    prediction_id: int | None = None,
    strategy_id: str | None = None,
    model_version: str | None = None,
    regime: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    payload = {
        "instrument": instrument,
        "prediction_id": prediction_id,
        "strategy_id": strategy_id,
        "model_version": model_version,
        "regime": regime,
        **(detail or {}),
    }
    try:
        execute(
            "INSERT INTO TAuditLog (UserId, TaskId, Action, Detail) VALUES (?, NULL, ?, ?)",
            (int(user_id) if user_id else None, action[:80], json.dumps(payload, default=str)[:4000]),
        )
    except Exception:
        return


def recent(user_id: int, *, limit: int = 30) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT * FROM TAuditLog WHERE UserId = ? ORDER BY AuditId DESC LIMIT ?",
        (int(user_id), int(limit)),
    )
