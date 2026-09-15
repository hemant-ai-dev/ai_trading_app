"""Advance shared tasks through workers. Portal 1 never calls the broker."""

from __future__ import annotations

from typing import Any

from tasks import store
from workers.steps import REGISTRY


def _plan(task: dict[str, Any]) -> list[str]:
    plan = task.get("Plan")
    if isinstance(plan, list) and plan:
        return [str(x) for x in plan]
    return ["intake", "planner", "audit"]


def advance(task_id: int, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        return {"ok": False, "detail": "Task not found."}
    if task["Status"] in ("completed", "failed", "rejected", "cancelled"):
        return {"ok": True, "detail": f"Already {task['Status']}.", "done": True}

    plan = _plan(task)
    idx = int(task.get("StepIndex") or 0)
    if idx >= len(plan):
        store.update_task(task_id, status="completed", current_worker=None)
        return {"ok": True, "done": True, "detail": "Plan finished."}

    code = plan[idx]
    label, fn = REGISTRY[code]
    store.update_task(task_id, current_worker=code)
    runtime = dict(ctx or {})
    runtime["task"] = task
    result = fn(runtime)
    status = result.get("status") or ("done" if result.get("ok") else "failed")
    store.add_event(task_id, code, label, status, result.get("detail") or "", result)
    if result.get("halt") or (not result.get("ok") and not result.get("wait")):
        store.update_task(task_id, status="failed", error=result.get("detail"))
        store.write_audit(int(task["UserId"]), task_id, "task.failed", result.get("detail") or "")
        return result
    if result.get("wait"):
        return result
    store.update_task(task_id, step_index=idx + 1)
    if idx + 1 >= len(plan):
        store.update_task(task_id, status="completed", current_worker=None)
        store.write_audit(int(task["UserId"]), task_id, "task.completed", "Worker plan completed.")
        return {**result, "done": True}
    return result


def run_until_blocked(task_id: int, ctx: dict[str, Any] | None = None, *, max_steps: int = 16) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for _ in range(max_steps):
        last = advance(task_id, ctx)
        if last.get("wait") or last.get("done") or last.get("halt") or not last.get("ok", True):
            return last
    return last


def tick_open_tasks(user_id: int, ctx: dict[str, Any] | None = None) -> int:
    """Re-run monitoring / queued work. Does not skip waiting approval."""
    n = 0
    for task in store.list_tasks(user_id, limit=40):
        if task["Status"] in ("queued", "planning", "monitoring", "executing"):
            run_until_blocked(int(task["TaskId"]), ctx)
            n += 1
    return n


def approve(task_id: int, user_id: int, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task or int(task["UserId"]) != int(user_id):
        return {"ok": False, "detail": "Task not found for this user."}
    auth = dict(task.get("Authorization") or {})
    auth["approved"] = True
    auth["rejected"] = False
    auth["state"] = "approved"
    store.update_task(task_id, authorization=auth, status="executing")
    store.add_event(task_id, "authorization", "User approval", "done", "User approved paper execution.")
    store.write_audit(user_id, task_id, "task.approved", "User approved paper path.")
    return run_until_blocked(task_id, ctx)


def reject(task_id: int, user_id: int) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task or int(task["UserId"]) != int(user_id):
        return {"ok": False, "detail": "Task not found for this user."}
    store.update_task(task_id, status="rejected", authorization={"approved": False, "rejected": True, "state": "rejected"})
    store.add_event(task_id, "authorization", "User rejection", "failed", "User rejected the action.")
    store.write_audit(user_id, task_id, "task.rejected", "User rejected.")
    return {"ok": True, "detail": "Rejected. No order was sent."}
