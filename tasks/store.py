"""Shared task records between Portal 1 (strategy) and Portal 2 (workers)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from db.database import execute, fetch_all, fetch_one

STATUSES = (
    "queued",
    "planning",
    "monitoring",
    "awaiting_approval",
    "executing",
    "completed",
    "failed",
    "rejected",
    "cancelled",
)


def _dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, default=str)


def _loads(raw: Any) -> Any:
    if not raw:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def hydrate(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("IntentJson", "PlanJson", "MarketJson", "RiskJson", "AuthorizationJson", "ResultJson"):
        out[key.replace("Json", "")] = _loads(out.get(key))
    return out


def create_task(
    *,
    user_id: int,
    request_text: str,
    source: str,
    priority: str = "normal",
    symbol: str | None = None,
) -> dict[str, Any]:
    public_id = "T" + uuid.uuid4().hex[:10].upper()
    execute(
        """
        INSERT INTO TWorkerTask (PublicId, UserId, Source, RequestText, Symbol, Priority, Status, CurrentWorker)
        VALUES (?, ?, ?, ?, ?, ?, 'queued', 'intake')
        """,
        (public_id, int(user_id), source, request_text.strip(), (symbol or "").upper() or None, priority),
    )
    task = fetch_one("SELECT * FROM TWorkerTask WHERE PublicId = ?", (public_id,))
    assert task is not None
    add_event(int(task["TaskId"]), "intake", "Request received", "queued", "Recorded in the shared task queue.")
    write_audit(int(user_id), int(task["TaskId"]), "task.created", f"{source}: {request_text[:180]}")
    return hydrate(task)


def get_task(task_id: int) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM TWorkerTask WHERE TaskId = ?", (int(task_id),))
    return hydrate(row) if row else None


def get_task_by_public(public_id: str) -> dict[str, Any] | None:
    row = fetch_one("SELECT * FROM TWorkerTask WHERE PublicId = ?", (public_id,))
    return hydrate(row) if row else None


def list_tasks(user_id: int | None = None, *, limit: int = 80) -> list[dict[str, Any]]:
    if user_id is None:
        rows = fetch_all("SELECT * FROM TWorkerTask ORDER BY TaskId DESC LIMIT ?", (int(limit),))
    else:
        rows = fetch_all(
            "SELECT * FROM TWorkerTask WHERE UserId = ? ORDER BY TaskId DESC LIMIT ?",
            (int(user_id), int(limit)),
        )
    return [hydrate(r) for r in rows]


def update_task(task_id: int, **fields: Any) -> None:
    allowed = {
        "IntentJson",
        "Symbol",
        "RequiredAction",
        "Status",
        "CurrentWorker",
        "PlanJson",
        "StepIndex",
        "MarketJson",
        "RiskJson",
        "AuthorizationJson",
        "ResultJson",
        "ErrorMessage",
        "Priority",
    }
    sets = []
    params: list[Any] = []
    mapping = {
        "intent": "IntentJson",
        "plan": "PlanJson",
        "market": "MarketJson",
        "risk": "RiskJson",
        "authorization": "AuthorizationJson",
        "result": "ResultJson",
        "symbol": "Symbol",
        "required_action": "RequiredAction",
        "status": "Status",
        "current_worker": "CurrentWorker",
        "step_index": "StepIndex",
        "error": "ErrorMessage",
        "priority": "Priority",
    }
    for key, value in fields.items():
        col = mapping.get(key, key)
        if col not in allowed:
            continue
        if col.endswith("Json"):
            value = _dumps(value)
        sets.append(f"{col} = ?")
        params.append(value)
    if not sets:
        return
    sets.append("UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')")
    params.append(int(task_id))
    execute(f"UPDATE TWorkerTask SET {', '.join(sets)} WHERE TaskId = ?", tuple(params))


def add_event(task_id: int, worker: str, step: str, status: str, detail: str, payload: Any = None) -> None:
    execute(
        """
        INSERT INTO TTaskEvent (TaskId, WorkerCode, StepName, Status, Detail, PayloadJson)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (int(task_id), worker, step, status, detail, _dumps(payload)),
    )


def list_events(task_id: int) -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM TTaskEvent WHERE TaskId = ? ORDER BY EventId ASC", (int(task_id),))


def write_audit(user_id: int | None, task_id: int | None, action: str, detail: str) -> None:
    execute(
        "INSERT INTO TAuditLog (UserId, TaskId, Action, Detail) VALUES (?, ?, ?, ?)",
        (user_id, task_id, action, detail),
    )


def list_audit(user_id: int | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    if user_id is None:
        return fetch_all("SELECT * FROM TAuditLog ORDER BY AuditId DESC LIMIT ?", (int(limit),))
    return fetch_all(
        "SELECT * FROM TAuditLog WHERE UserId = ? ORDER BY AuditId DESC LIMIT ?",
        (int(user_id), int(limit)),
    )


def counts(user_id: int | None = None) -> dict[str, int]:
    sql = "SELECT Status, COUNT(*) AS n FROM TWorkerTask"
    params: tuple = ()
    if user_id is not None:
        sql += " WHERE UserId = ?"
        params = (int(user_id),)
    sql += " GROUP BY Status"
    rows = fetch_all(sql, params)
    out = {s: 0 for s in STATUSES}
    for r in rows:
        out[str(r["Status"])] = int(r["n"])
    return out
