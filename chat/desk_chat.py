"""Grounded desk chat — answers from analysis, predictions, and tasks only."""

from __future__ import annotations

from typing import Any

from db.database import execute, fetch_all
from prediction import archive
from tasks import store
from tasks.parser import parse_intent
from workers.orchestrator import run_until_blocked


def save_message(user_id: int, role: str, content: str, symbol: str | None = None) -> None:
    execute(
        "INSERT INTO TChatMessage (UserId, Role, Content, Symbol) VALUES (?, ?, ?, ?)",
        (int(user_id), role, content, symbol),
    )


def load_messages(user_id: int, *, limit: int = 40) -> list[dict[str, Any]]:
    rows = fetch_all(
        "SELECT * FROM TChatMessage WHERE UserId = ? ORDER BY MessageId DESC LIMIT ?",
        (int(user_id), int(limit)),
    )
    return list(reversed(rows))


def answer(
    *,
    user_id: int,
    text: str,
    analysis: dict[str, Any] | None,
    symbol: str,
) -> str:
    q = (text or "").strip()
    lower = q.lower()
    analysis = analysis or {}
    primary = analysis.get("primary")
    explanation = analysis.get("explanation") or {}
    preds = archive.list_predictions(user_id, symbol, limit=8)
    tasks = store.list_tasks(user_id, limit=5)

    if any(w in lower for w in ("buy tatamotors", "monitor", "prepare a buy", "notify me", "if price", "shares")):
        intent = parse_intent(q, default_symbol=symbol)
        if intent["action"] != "unknown":
            task = store.create_task(
                user_id=user_id,
                request_text=q,
                source="portal1_chat",
                symbol=intent.get("symbol") or symbol,
            )
            return (
                f"Created worker task **{task['PublicId']}** ({intent['action']} for {intent.get('symbol')}). "
                "This is a structured request for the AI Workers portal — not a live broker order. "
                "Open **AI Workers Portal** to watch the workflow and approve paper execution if asked."
            )

    if primary is None:
        return "Run the Strategy portal once so I have a live analysis snapshot to talk about."

    signal = primary.signal
    latest = analysis.get("latest_price")
    snap = primary.indicator_snapshot or {}

    if "trend" in lower:
        return (
            f"{symbol} trend is **{(snap.get('trend_dir') or primary.trend)}** "
            f"in regime `{primary.market_regime}`. Live ₹{float(latest):,.2f}. "
            f"{explanation.get('trend_summary') or ''}"
        )
    if "why" in lower or "hold" in lower:
        reasons = explanation.get("reasons") or primary.reasons_simple or primary.reasons or []
        body = " ".join(str(r) for r in reasons[:4])
        if signal == "HOLD":
            return (
                f"I recommend **HOLD** at ₹{float(latest):,.2f} with {primary.confidence:.0f}% confidence. {body} "
                f"Invalidation: a confirmed break of support/resistance in the Smart Box, or regime shift away from `{primary.market_regime}`."
            )
        return f"I recommend **{signal}** ({primary.confidence:.0f}%). {body}"
    if "risk" in lower:
        return (
            f"Risk level **{primary.risk_level}**. Stop ₹{primary.stop_loss:,.2f}, target ₹{primary.target_price:,.2f}. "
            f"{explanation.get('suggested_action') or ''} This is not a profit guarantee."
        )
    if "history" in lower or "previous prediction" in lower or "changed" in lower:
        if len(preds) < 2:
            return f"I have {len(preds)} stored SQLite prediction(s) for {symbol} on this account. Need at least two to compare."
        a, b = preds[0], preds[1]
        return (
            f"Latest stored prediction {a['CreatedAt']}: {a['Signal']} target ₹{a['PredictedPrice']:.2f} "
            f"({a['Confidence']:.0f}%). Previous {b['CreatedAt']}: {b['Signal']} ₹{b['PredictedPrice']:.2f} "
            f"({b['Confidence']:.0f}%). Rows are append-only in TPrediction."
        )
    if "outlook" in lower or "next" in lower:
        return (
            f"Horizon view for {symbol}: predicted ₹{primary.predicted_price:,.2f} "
            f"range ₹{primary.price_low:,.2f}–₹{primary.price_high:,.2f}, signal {signal}. "
            f"Not a guaranteed next-day print."
        )
    if "buy" in lower and "trigger" in lower:
        return (
            f"A BUY becomes more interesting if price holds above support and momentum confirms "
            f"(RSI {float(snap.get('rsi') or 0):.1f}, trend {snap.get('trend_dir')}). "
            f"Current official recommendation remains **{signal}**."
        )
    if "chart" in lower:
        return (
            f"Candles are traded OHLC. The gold dashed line is a guessed path from the last close toward "
            f"₹{primary.predicted_price:,.2f}, not extra history. {explanation.get('price_range')}"
        )
    if tasks:
        t = tasks[0]
        extra = f" Latest worker task {t['PublicId']} is {t['Status']}."
    else:
        extra = ""
    return (
        f"{symbol}: **{signal}** @ ₹{float(latest):,.2f}, confidence {primary.confidence:.0f}%, "
        f"target ₹{primary.target_price:,.2f}, stop ₹{primary.stop_loss:,.2f}. "
        f"{explanation.get('suggested_action') or ''}{extra} Educational analysis only."
    )
