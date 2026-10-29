"""Potential setup: entry band, ATR/S-R stop, targets, exit state. Not an order."""

from __future__ import annotations

from typing import Any

MIN_RR = 1.5
MODEL_VERSION = "angad-trade-plan-v1"


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def classify_setup_status(
    *,
    signal: str,
    spot: float,
    entry_low: float,
    entry_high: float,
    stop: float,
    target1: float,
    target2: float,
    rr: float,
    previous: str | None = None,
) -> str:
    sig = (signal or "HOLD").upper()
    prev = (previous or "").upper()
    if sig == "HOLD" or rr < MIN_RR:
        status = "NO TRADE" if rr < MIN_RR and sig != "HOLD" else "WAIT"
        if sig == "HOLD":
            status = "WAIT"
    elif sig == "BUY":
        if spot <= stop:
            status = "STOP LOSS"
        elif spot >= target2:
            status = "TARGET 2"
        elif spot >= target1:
            status = "TARGET 1"
        elif entry_low <= spot <= entry_high:
            status = "ENTRY"
        elif spot > entry_high:
            status = "HOLD"
        else:
            status = "WAIT"
    elif sig == "SELL":
        if spot >= stop:
            status = "STOP LOSS"
        elif spot <= target2:
            status = "TARGET 2"
        elif spot <= target1:
            status = "TARGET 1"
        elif entry_low <= spot <= entry_high:
            status = "ENTRY"
        elif spot < entry_low:
            status = "HOLD"
        else:
            status = "WAIT"
    else:
        status = "WAIT"
    if prev in ("ENTRY", "HOLD", "ACTIVE", "TARGET 1") and status == "WAIT":
        status = "INVALIDATED"
    if prev.startswith("BUY") or prev in ("ENTRY", "ACTIVE"):
        if status == "WAIT":
            status = "HOLD"
    return status


def build_trade_plan(
    *,
    symbol: str,
    name: str | None,
    spot: float,
    signal: str,
    trend: str,
    confidence: float,
    predicted_price: float,
    atr: float,
    support: float | None,
    resistance: float | None,
    regime: str,
    strategy_id: str,
    strategy_name: str,
    risk_plan: dict[str, Any] | None,
    reasons: list[str] | None = None,
    horizon: str = "1d",
    previous_status: str | None = None,
    strategy_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dynamic entry / SL / targets from ATR, S/R, and the existing risk plan."""
    spot = float(spot)
    atr = float(max(atr, spot * 0.002, 0.01))
    sig = (signal or "HOLD").upper()
    rp = risk_plan or {}
    stop = _f(rp.get("stop_loss"), spot - atr)
    t1 = _f(rp.get("target_price"), spot + atr * 2)
    predicted = _f(predicted_price, spot)
    band = atr * 0.18
    if sig == "BUY":
        entry_low = round(spot - band, 2)
        entry_high = round(spot + band * 0.55, 2)
        if support:
            stop = round(min(stop, float(support) - atr * 0.15), 2)
        t2 = round(t1 + atr * 0.9, 2)
        direction = "Bullish"
        exit_cond = f"Exit if close loses support near ₹{stop:,.2f} or momentum reverses below the entry band."
        sl_why = (
            f"Stop uses ATR ({atr:.2f}) and nearby support so the long is invalid if that structure breaks — "
            "not a fixed percentage."
        )
        hold = "Intraday to a few sessions while the trend regime holds."
    elif sig == "SELL":
        entry_low = round(spot - band * 0.55, 2)
        entry_high = round(spot + band, 2)
        if resistance:
            stop = round(max(stop, float(resistance) + atr * 0.15), 2)
        t2 = round(t1 - atr * 0.9, 2)
        direction = "Bearish"
        exit_cond = f"Exit if close reclaims resistance near ₹{stop:,.2f} or the short thesis is invalidated."
        sl_why = (
            f"Stop uses ATR ({atr:.2f}) and nearby resistance so the short is invalid if that cap fails — "
            "not a fixed percentage."
        )
        hold = "Intraday to a few sessions while the downtrend or fade holds."
    else:
        entry_low = round(spot - band, 2)
        entry_high = round(spot + band, 2)
        t2 = round(spot + atr * 1.2, 2)
        direction = "Unclear"
        exit_cond = "No trade until direction, liquidity, and risk/reward confirm together."
        sl_why = "HOLD: stops are reference levels only until a directional setup clears."
        hold = "Wait."

    risk = abs(spot - stop) or atr * 0.4
    reward = abs(t1 - spot) or atr * 0.4
    rr = round(reward / risk, 2) if risk else 0.0
    status = classify_setup_status(
        signal=sig,
        spot=spot,
        entry_low=entry_low,
        entry_high=entry_high,
        stop=stop,
        target1=t1,
        target2=t2,
        rr=rr,
        previous=previous_status,
    )
    if sig == "HOLD" or rr < MIN_RR:
        if status not in ("STOP LOSS", "TARGET 1", "TARGET 2", "INVALIDATED"):
            status = "NO TRADE" if rr < MIN_RR and sig != "HOLD" else "WAIT"
    hist = strategy_history or {}
    from analyst.sizing import risk_config_from_session, theoretical_size

    cfg = risk_config_from_session()
    sizing = theoretical_size(
        entry=spot,
        stop=stop,
        capital=cfg.get("capital"),
        max_risk_pct=float(cfg.get("max_risk_pct") or 1.0),
    )
    if sizing.get("exceeds_risk") and status not in ("STOP LOSS", "TARGET 1", "TARGET 2", "INVALIDATED"):
        if sig != "HOLD":
            status = "NO TRADE"
    return {
        "symbol": symbol,
        "name": name or symbol,
        "spot": round(spot, 2),
        "direction": direction,
        "expected_move": round(predicted - spot, 2),
        "predicted_price": round(predicted, 2),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": round(stop, 2),
        "target1": round(t1, 2),
        "target2": round(t2, 2),
        "rr": rr,
        "probability": round(float(confidence or 0), 1),
        "confidence": round(float(confidence or 0), 1),
        "horizon": horizon,
        "holding_period": hold,
        "reasons": list(reasons or [])[:5],
        "regime": regime,
        "strategy_id": strategy_id,
        "strategy": strategy_name,
        "model_version": MODEL_VERSION,
        "exit_condition": exit_cond,
        "stop_reason": sl_why,
        "status": status,
        "disclaimer": "Potential setup from local models. Not a guarantee and not a broker order.",
        "sizing": sizing,
        "entry_reason": (
            f"{direction} setup: last ₹{spot:,.2f} is the reference; entry band is ±ATR({atr:.2f}) around that print."
        ),
        "target_reason": (
            f"T1 ₹{round(t1, 2):,.2f} / T2 ₹{round(t2, 2):,.2f} come from the ATR/regime risk plan, not a round number."
        ),
        "strategy_reliability": {
            "sample": hist.get("completed") or 0,
            "direction_accuracy_pct": hist.get("direction_accuracy_pct"),
            "validated": bool(hist.get("validated")),
            "note": hist.get("note")
            or "Historical strategy reliability is separate from this run's model probability.",
        },
    }
