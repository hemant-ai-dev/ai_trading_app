"""Specialized workers. Each function records real work on a shared task."""

from __future__ import annotations

from typing import Any

from broker.paper import PaperBroker, get_broker
from services.market_service import MarketService
from tasks.parser import parse_intent
from tasks import store


def intake(ctx: dict[str, Any]) -> dict[str, Any]:
    task = ctx["task"]
    return {
        "ok": True,
        "status": "done",
        "detail": f"Intake recorded request {task['PublicId']} from {task['Source']}.",
    }


def planner(ctx: dict[str, Any]) -> dict[str, Any]:
    task = ctx["task"]
    intent = parse_intent(task["RequestText"], default_symbol=ctx.get("default_symbol"))
    store.update_task(
        int(task["TaskId"]),
        intent=intent,
        plan=intent["plan"],
        symbol=intent.get("symbol"),
        required_action=intent.get("action"),
        status="planning",
    )
    if intent["action"] == "unknown":
        return {
            "ok": False,
            "status": "failed",
            "detail": "Could not parse a monitor, notify, or paper-trade action from the text.",
            "halt": True,
        }
    return {
        "ok": True,
        "status": "done",
        "detail": f"Intent {intent['action']} for {intent.get('symbol') or 'n/a'}. Plan: {' → '.join(intent['plan'])}.",
        "updates": {"intent": intent},
    }


def market(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    intent = (task or {}).get("Intent") or {}
    symbol = intent.get("symbol") or (task or {}).get("Symbol")
    if not symbol:
        return {"ok": False, "status": "failed", "detail": "No symbol to fetch.", "halt": True}
    svc: MarketService = ctx["market"]
    px = svc.get_latest_price(symbol)
    df = svc.get_ohlcv(symbol, "3mo", "1d")
    last = float(df["Close"].iloc[-1]) if df is not None and not df.empty else px
    payload = {
        "symbol": symbol,
        "last_price": last or px,
        "bars": 0 if df is None else len(df),
        "fresh": last is not None,
        "source": "yahoo/stooq via MarketService",
    }
    store.update_task(int(task["TaskId"]), market=payload, symbol=symbol)
    if last is None:
        return {"ok": False, "status": "failed", "detail": f"No market data for {symbol}.", "halt": True}
    return {"ok": True, "status": "done", "detail": f"{symbol} last ₹{float(last):,.2f} ({payload['bars']} bars)."}


def monitor(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    intent = (task or {}).get("Intent") or {}
    trigger = intent.get("trigger") or {}
    market_data = (task or {}).get("Market") or {}
    last = market_data.get("last_price")
    op = trigger.get("op")
    level = trigger.get("price")
    if last is None or op is None or level is None:
        return {"ok": True, "status": "done", "detail": "No price condition — skipping wait."}
    hit = (op == "below" and float(last) <= float(level)) or (op == "above" and float(last) >= float(level))
    if not hit:
        store.update_task(int(task["TaskId"]), status="monitoring", current_worker="monitor")
        return {
            "ok": True,
            "status": "waiting",
            "detail": f"Monitoring {task.get('Symbol')}: last ₹{float(last):,.2f} vs {op} ₹{float(level):,.2f}. Condition not met.",
            "wait": True,
        }
    return {
        "ok": True,
        "status": "done",
        "detail": f"Condition met: last ₹{float(last):,.2f} is {op} ₹{float(level):,.2f}.",
    }


def analysis(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    analysis_svc = ctx.get("analysis")
    symbol = (task or {}).get("Symbol")
    if not analysis_svc or not symbol:
        return {"ok": True, "status": "done", "detail": "Analysis skipped (no desk service in this context)."}
    result = analysis_svc.analyze(symbol=symbol, period="3mo", interval="1d", use_genai=False, include_world_news=False)
    if result.get("error"):
        return {"ok": True, "status": "done", "detail": f"Analysis unavailable: {result['error']}"}
    primary = result["primary"]
    summary = {
        "signal": primary.signal,
        "confidence": primary.confidence,
        "target": primary.target_price,
        "stop": primary.stop_loss,
        "regime": primary.market_regime,
        "risk": primary.risk_level,
    }
    store.update_task(int(task["TaskId"]), result={**(task.get("Result") or {}), "analysis": summary})
    return {
        "ok": True,
        "status": "done",
        "detail": f"Desk analysis {primary.signal} {primary.confidence:.0f}% · regime {primary.market_regime}.",
    }


def risk(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    intent = (task or {}).get("Intent") or {}
    market_data = (task or {}).get("Market") or {}
    last = float(market_data.get("last_price") or 0)
    qty = intent.get("quantity")
    budget = intent.get("budget")
    limit = float(intent.get("limit_price") or last or 0)
    notes = []
    if budget and last > 0 and not qty:
        qty = int(float(budget) // last)
        notes.append(f"Quantity from budget ₹{budget:,.0f} / ₹{last:,.2f} = {qty} shares (integer lots only).")
        intent["quantity"] = qty
        store.update_task(int(task["TaskId"]), intent=intent)
    if not qty or qty <= 0:
        check = {
            "ok": False,
            "reason": "Quantity is missing or zero. Risk worker will not invent a size.",
            "last_price": last,
        }
        store.update_task(int(task["TaskId"]), risk=check)
        return {"ok": False, "status": "failed", "detail": check["reason"], "halt": True}
    notional = float(qty) * float(limit or last)
    max_notional = 250000.0
    ok = notional <= max_notional
    check = {
        "ok": ok,
        "quantity": qty,
        "price": limit or last,
        "notional": round(notional, 2),
        "max_notional": max_notional,
        "notes": notes,
        "paper_cash_required": True,
        "live_holdings_assumed": False,
    }
    store.update_task(int(task["TaskId"]), risk=check)
    if not ok:
        return {"ok": False, "status": "failed", "detail": f"Notional ₹{notional:,.2f} exceeds desk limit ₹{max_notional:,.0f}.", "halt": True}
    return {"ok": True, "status": "done", "detail": f"Risk check passed for {qty} × ₹{limit or last:,.2f} (paper rules only)."}


def authorization(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    intent = (task or {}).get("Intent") or {}
    auth = (task or {}).get("Authorization") or {}
    action = intent.get("action")
    if action in ("notify", "analyze"):
        store.update_task(int(task["TaskId"]), authorization={"required": False, "state": "not_required"})
        return {"ok": True, "status": "done", "detail": "No broker action — authorization not required."}
    if auth.get("rejected"):
        store.update_task(int(task["TaskId"]), status="rejected", authorization={**auth, "state": "rejected"})
        return {"ok": False, "status": "failed", "halt": True, "detail": "User rejected the action."}
    if auth.get("approved"):
        store.update_task(int(task["TaskId"]), authorization={**auth, "required": True, "state": "approved"})
        return {"ok": True, "status": "done", "detail": "User approved paper execution."}
    store.update_task(
        int(task["TaskId"]),
        status="awaiting_approval",
        authorization={"required": True, "state": "pending", "mode": "paper"},
    )
    return {
        "ok": True,
        "status": "waiting",
        "wait": True,
        "detail": "Waiting for user authorization. Paper broker only — not a live order.",
    }


def execution(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    intent = (task or {}).get("Intent") or {}
    risk = (task or {}).get("Risk") or {}
    auth = (task or {}).get("Authorization") or {}
    if not auth.get("approved"):
        return {"ok": False, "status": "failed", "halt": True, "detail": "Execution blocked: not approved."}
    if intent.get("action") == "monitor_prepare" and not auth.get("approved"):
        return {"ok": True, "status": "done", "detail": "Prepared only — execution skipped."}
    broker = get_broker()
    if not isinstance(broker, PaperBroker) or not broker.is_configured():
        return {"ok": False, "status": "failed", "halt": True, "detail": "No executable broker configured."}
    qty = float(risk.get("quantity") or intent.get("quantity") or 0)
    px = float(risk.get("price") or intent.get("limit_price") or 0)
    side = intent.get("side") or "BUY"
    store.update_task(int(task["TaskId"]), status="executing")
    result = broker.submit_order(
        user_id=int(task["UserId"]),
        task_id=int(task["TaskId"]),
        symbol=str(task.get("Symbol")),
        side=side,
        quantity=qty,
        limit_price=px,
    )
    merged = {**(task.get("Result") or {}), "execution": result}
    store.update_task(int(task["TaskId"]), result=merged)
    if not result.get("ok"):
        return {"ok": False, "status": "failed", "halt": True, "detail": result.get("reason") or "Paper order rejected."}
    return {"ok": True, "status": "done", "detail": f"Paper {result['status']} {result.get('order_id')} @ ₹{result.get('filled_price')}."}


def status_worker(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    exe = ((task or {}).get("Result") or {}).get("execution") or {}
    st = exe.get("status") or "none"
    return {"ok": True, "status": "done", "detail": f"Order status from paper broker: {st}. Live brokers are not queried."}


def notify(ctx: dict[str, Any]) -> dict[str, Any]:
    task = store.get_task(int(ctx["task"]["TaskId"]))
    detail = f"Notification recorded for {task.get('PublicId')} status={task.get('Status')}."
    return {"ok": True, "status": "done", "detail": detail}


def audit(ctx: dict[str, Any]) -> dict[str, Any]:
    task = ctx["task"]
    store.write_audit(int(task["UserId"]), int(task["TaskId"]), "task.step.audit", "Audit worker closed the trail.")
    return {"ok": True, "status": "done", "detail": "Audit row written."}


REGISTRY = {
    "intake": ("Request Intake", intake),
    "planner": ("Intent & Task Planning", planner),
    "market": ("Market Data", market),
    "monitor": ("Market Monitoring", monitor),
    "analysis": ("Analysis", analysis),
    "risk": ("Risk & Funds Validation", risk),
    "authorization": ("Authorization", authorization),
    "execution": ("Broker / Execution (paper)", execution),
    "status": ("Order Status", status_worker),
    "notify": ("Notification", notify),
    "audit": ("Audit", audit),
}
