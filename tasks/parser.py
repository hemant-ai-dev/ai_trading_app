"""Turn a user sentence into a structured worker intent. Not a trade by itself."""

from __future__ import annotations

import re
from typing import Any

SYMBOL_ALIASES = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "TATAMOTORS": "TATAMOTORS.NS",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
}

_PRICE = re.compile(r"(?:₹|rs\.?\s*)(\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
_BARE_BELOW = re.compile(
    r"(?:below|under|falls?\s+(?:below|to)|goes?\s+below|above|over|rises?\s+(?:above|to)|goes?\s+above)\s*(?:₹|rs\.?\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)",
    re.I,
)
_AT_PRICE = re.compile(r"\bat\s*(?:₹|rs\.?\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
_QTY = re.compile(r"(\d+(?:\.\d+)?)\s*(?:shares?|qty|quantity)", re.I)
_BUDGET = re.compile(r"(?:using|with|budget(?:\s+of)?)\s*(?:₹|rs\.?\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)", re.I)
_TICKER = re.compile(r"\b([A-Z]{2,12}(?:\.[A-Z]{1,4})?|\^[A-Z]{3,12})\b")


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def resolve_symbol(raw: str | None, fallback: str | None = None) -> str | None:
    if not raw:
        return fallback
    key = raw.strip().upper().replace(" ", "")
    if key in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[key]
    if key.startswith("^"):
        return key
    if "." in key:
        return key
    if key.isalpha() and len(key) >= 3:
        return f"{key}.NS"
    return fallback or key


def parse_intent(text: str, *, default_symbol: str | None = None) -> dict[str, Any]:
    """
    Structured intent for Portal 2. Creating this is not execution.

    action: notify | monitor_prepare | paper_buy | paper_sell | analyze | unknown
    """
    raw = (text or "").strip()
    lower = raw.lower()
    tickers = _TICKER.findall(raw.upper())
    skip = {
        "BUY", "SELL", "HOLD", "IF", "THE", "AND", "FOR", "WITH", "BELOW", "ABOVE",
        "PRICE", "USING", "CHECK", "MONITOR", "PREPARE", "ORDER", "NOTIFY", "ME",
        "WHEN", "GOES", "FALLS", "SHARE", "SHARES", "INR",
    }
    symbol = None
    for t in tickers:
        if t in skip:
            continue
        symbol = resolve_symbol(t, default_symbol)
        break
    symbol = symbol or resolve_symbol(default_symbol)

    qty_m = _QTY.search(raw)
    budget_m = _BUDGET.search(raw)
    trig_m = _BARE_BELOW.search(raw)
    at_m = _AT_PRICE.search(raw)
    rupee_prices = [_num(p) for p in _PRICE.findall(raw)]
    quantity = float(qty_m.group(1)) if qty_m else None
    budget = _num(budget_m.group(1)) if budget_m else None
    trigger = None
    limit_price = None
    if trig_m:
        level = _num(trig_m.group(1))
        chunk = trig_m.group(0).lower()
        op = "above" if any(w in chunk for w in ("above", "over", "rises")) else "below"
        trigger = {"op": op, "price": level}
    if at_m:
        limit_price = _num(at_m.group(1))
    elif rupee_prices and not trigger:
        limit_price = rupee_prices[0]
    elif rupee_prices and trigger and rupee_prices[0] != trigger["price"]:
        limit_price = rupee_prices[0]

    wants_buy = bool(re.search(r"\bbuy\b", lower))
    wants_sell = bool(re.search(r"\bsell\b", lower))
    wants_monitor = bool(re.search(r"\bmonitor\b|\bnotify\b|\balert\b|\bwatch\b|\bif\b", lower))
    prepare_only = "prepare" in lower or "notify" in lower or "alert" in lower

    if wants_buy and trigger and prepare_only:
        action = "monitor_prepare"
    elif wants_buy and trigger:
        action = "monitor_prepare"
    elif wants_buy:
        action = "paper_buy"
    elif wants_sell:
        action = "paper_sell"
    elif wants_monitor:
        action = "notify"
    elif "analy" in lower or "outlook" in lower or "trend" in lower:
        action = "analyze"
    else:
        action = "unknown"

    needs_approval = action in ("paper_buy", "paper_sell")
    plan = _plan_for(action, bool(trigger))
    return {
        "action": action,
        "symbol": symbol,
        "quantity": quantity,
        "budget": budget,
        "limit_price": limit_price,
        "trigger": trigger,
        "side": "BUY" if wants_buy else ("SELL" if wants_sell else None),
        "needs_approval": needs_approval,
        "execution_mode": "paper",
        "original_text": raw,
        "plan": plan,
        "confidence": 0.82 if action != "unknown" else 0.35,
    }


def _plan_for(action: str, has_trigger: bool) -> list[str]:
    base = ["intake", "planner"]
    if action == "unknown":
        return base + ["audit"]
    if action == "analyze":
        return base + ["market", "analysis", "notify", "audit"]
    if action == "notify":
        steps = base + ["market"]
        if has_trigger:
            steps.append("monitor")
        return steps + ["notify", "audit"]
    if action == "monitor_prepare":
        return base + ["market", "monitor", "analysis", "risk", "authorization", "execution", "status", "notify", "audit"]
    if action in ("paper_buy", "paper_sell"):
        steps = base + ["market"]
        if has_trigger:
            steps.append("monitor")
        return steps + ["analysis", "risk", "authorization", "execution", "status", "notify", "audit"]
    return base + ["audit"]
