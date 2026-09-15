"""Portal 2 — AI Workers & Automation Control Center."""

from __future__ import annotations

from typing import Any

import streamlit as st

from broker.paper import PaperBroker
from tasks import store
from workers.orchestrator import approve, reject, run_until_blocked
from workers.steps import REGISTRY


def _worker_ctx(user: dict) -> dict[str, Any]:
    return {
        "market": st.session_state["analysis"].market,
        "analysis": st.session_state["analysis"],
        "default_symbol": st.session_state.get("desk_custom_ticker") or "^NSEI",
    }


def render_workers_portal(user: dict) -> None:
    uid = int(user["user_id"])
    ctx = _worker_ctx(user)
    n = 0
    for task in store.list_tasks(uid, limit=30):
        if task["Status"] in ("queued", "planning", "monitoring", "executing"):
            run_until_blocked(int(task["TaskId"]), ctx)
            n += 1

    st.markdown(
        '<div class="brand-sub">PORTAL 2</div>'
        '<div class="hello-line">AI Workers Control Center</div>'
        '<div class="hello-sub">Intake → plan → data → risk → approval → paper execution → audit. Not a live broker.</div>',
        unsafe_allow_html=True,
    )

    counts = store.counts(uid)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Queued", counts.get("queued", 0))
    c2.metric("Monitoring", counts.get("monitoring", 0))
    c3.metric("Need approval", counts.get("awaiting_approval", 0))
    c4.metric("Running", counts.get("planning", 0) + counts.get("executing", 0))
    c5.metric("Completed", counts.get("completed", 0))
    c6.metric("Failed", counts.get("failed", 0) + counts.get("rejected", 0))

    paper = PaperBroker().ensure_account(uid)
    from services.api_monitor import usage_summary

    summary = usage_summary()
    enabled = sum(1 for p in summary if p.get("IsEnabled", 1))
    w1, w2, w3 = st.columns(3)
    with w1:
        st.markdown("##### Active workers")
        busy = {t.get("CurrentWorker") for t in store.list_tasks(uid, limit=40) if t["Status"] in ("monitoring", "executing", "planning")}
        for code, (label, _) in REGISTRY.items():
            state = "busy" if code in busy else "idle"
            st.caption(f"{'●' if state == 'busy' else '○'} {label} · {state}")
    with w2:
        st.markdown("##### System health")
        st.write(f"Paper cash **₹{float(paper.get('CashBalance') or 0):,.2f}**")
        st.caption("Live Kite/broker: not configured. Execution adapter = paper.")
        st.caption(f"API catalog rows: {enabled}")
    with w3:
        st.markdown("##### New request")
        txt = st.text_area(
            "Manual task",
            placeholder="Monitor TATAMOTORS and prepare a buy of 5 shares if price falls below ₹640.",
            key="worker_manual_text",
        )
        if st.button("Send to intake", type="primary", key="worker_manual_send"):
            if not txt.strip():
                st.error("Enter a request.")
            else:
                task = store.create_task(user_id=uid, request_text=txt.strip(), source="portal2_manual")
                run_until_blocked(int(task["TaskId"]), ctx)
                st.success(f"Task {task['PublicId']} queued.")
                st.rerun()

    inbox, detail, audit = st.tabs(["Request inbox", "Task workflow", "Audit"])
    tasks = store.list_tasks(uid, limit=80)
    with inbox:
        if not tasks:
            st.info("No tasks yet. Create one from AI Chat on Portal 1 or the box above.")
        else:
            rows = [
                {
                    "ID": t["PublicId"],
                    "Request": (t["RequestText"] or "")[:80],
                    "Source": t["Source"],
                    "Symbol": t.get("Symbol") or "—",
                    "Action": t.get("RequiredAction") or "—",
                    "Status": t["Status"],
                    "Worker": t.get("CurrentWorker") or "—",
                    "Created": t["CreatedAt"],
                }
                for t in tasks
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

    with detail:
        if not tasks:
            st.caption("Inbox is empty.")
        else:
            labels = [f"{t['PublicId']} · {t['Status']} · {(t['RequestText'] or '')[:40]}" for t in tasks]
            pick = st.selectbox("Open task", labels, key="worker_task_pick")
            task = tasks[labels.index(pick)]
            _render_task_detail(task, user, ctx)

    with audit:
        logs = store.list_audit(uid, limit=40)
        if not logs:
            st.caption("No audit rows yet.")
        else:
            st.dataframe(
                [{"When": r["CreatedAt"], "Action": r["Action"], "Detail": r["Detail"]} for r in logs],
                use_container_width=True,
                hide_index=True,
            )


def _render_task_detail(task: dict, user: dict, ctx: dict) -> None:
    tid = int(task["TaskId"])
    fresh = store.get_task(tid) or task
    events = store.list_events(tid)
    plan = fresh.get("Plan") or ["intake", "planner", "audit"]
    idx = int(fresh.get("StepIndex") or 0)
    st.markdown(f"#### {fresh['PublicId']}")
    st.write(fresh["RequestText"])
    a, b, c = st.columns(3)
    a.metric("Status", fresh["Status"])
    b.metric("Symbol", fresh.get("Symbol") or "—")
    c.metric("Action", fresh.get("RequiredAction") or "—")
    st.markdown("##### Workflow")
    for i, code in enumerate(plan):
        label = REGISTRY.get(code, (code, None))[0]
        if i < idx:
            mark = "done"
        elif i == idx and fresh["Status"] not in ("completed", "failed", "rejected"):
            mark = "active"
        elif fresh["Status"] == "failed" and i == idx:
            mark = "failed"
        else:
            mark = "pending"
        icon = {"done": "✓", "active": "⏳", "failed": "✕", "pending": "○"}[mark]
        st.markdown(f"{icon} **{label}** · `{mark}`")
    intent = fresh.get("Intent") or {}
    if intent:
        st.json(intent)
    if fresh.get("Market"):
        st.caption("Market data used")
        st.json(fresh["Market"])
    if fresh.get("Risk"):
        st.caption("Risk checks")
        st.json(fresh["Risk"])
    if fresh.get("Result"):
        st.caption("Result")
        st.json(fresh["Result"])
    if fresh.get("ErrorMessage"):
        st.error(fresh["ErrorMessage"])
    if fresh["Status"] == "awaiting_approval":
        x, y = st.columns(2)
        if x.button("Approve paper execution", type="primary", key=f"appr_{tid}"):
            approve(tid, int(user["user_id"]), ctx)
            st.rerun()
        if y.button("Reject", key=f"rej_{tid}"):
            reject(tid, int(user["user_id"]))
            st.rerun()
    st.markdown("##### Task log")
    for ev in events:
        st.caption(f"{ev['CreatedAt']} · {ev['WorkerCode']} · {ev['Status']} — {ev['Detail']}")
