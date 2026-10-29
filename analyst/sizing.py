"""Theoretical position size from user-configured capital. Never places orders."""

from __future__ import annotations

from typing import Any

DEFAULTS = {
    "capital": None,
    "max_risk_pct": 1.0,
    "max_daily_loss_pct": 3.0,
    "max_positions": 3,
    "max_instrument_pct": 25.0,
    "slippage_pct": 0.05,
    "cost_pct": 0.03,
}


def risk_config_from_session() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        import streamlit as st

        cap = st.session_state.get("risk_capital")
        if cap not in (None, "", 0, 0.0):
            cfg["capital"] = float(cap)
        cfg["max_risk_pct"] = float(st.session_state.get("risk_max_pct") or 1.0)
        cfg["max_daily_loss_pct"] = float(st.session_state.get("risk_max_daily_pct") or 3.0)
        cfg["max_positions"] = int(st.session_state.get("risk_max_positions") or 3)
        cfg["max_instrument_pct"] = float(st.session_state.get("risk_max_instrument_pct") or 25.0)
    except Exception:
        pass
    return cfg


def theoretical_size(
    *,
    entry: float,
    stop: float,
    capital: float | None,
    max_risk_pct: float = 1.0,
    lot_size: int = 1,
    is_option_buy: bool = False,
    premium: float | None = None,
    cost_pct: float = 0.03,
    slippage_pct: float = 0.05,
) -> dict[str, Any]:
    """Shares/lots so a stop (or full premium wipeout for long options) stays inside the risk budget."""
    if not capital or capital <= 0:
        return {
            "configured": False,
            "warning": "Set trading capital in Risk limits before a size is calculated. No default capital is assumed.",
            "exceeds_risk": False,
            "qty": 0,
        }
    entry = float(entry)
    stop = float(stop)
    slip = entry * (slippage_pct / 100.0)
    cost = entry * (cost_pct / 100.0)
    if is_option_buy:
        prem = float(premium or entry)
        per_unit = prem + cost + slip  # entire premium can be lost
        risk_note = "Long option: budget assumes the full premium can be lost."
    else:
        per_unit = abs(entry - stop) + cost + slip
        risk_note = "Cash/index size uses stop distance plus a small cost/slippage allowance."
    budget = capital * (max_risk_pct / 100.0)
    if per_unit <= 0:
        return {"configured": True, "qty": 0, "exceeds_risk": True, "warning": "Stop distance is zero.", "note": risk_note}
    raw = int(budget // per_unit)
    lot = max(int(lot_size or 1), 1)
    qty = (raw // lot) * lot
    risk_used = qty * per_unit
    notional = qty * entry
    exceeds = qty <= 0 or risk_used > budget * 1.01 or notional > capital
    warning = None
    if qty <= 0:
        warning = "NO TRADE: stop distance vs capital would exceed the configured risk per trade."
    elif notional > capital:
        warning = "NO TRADE: notional exceeds configured capital."
        exceeds = True
    return {
        "configured": True,
        "qty": int(qty),
        "lot_size": lot,
        "risk_rupees": round(risk_used, 2),
        "budget_rupees": round(budget, 2),
        "notional": round(notional, 2),
        "position_pct": round(100.0 * notional / capital, 2) if capital else 0,
        "exceeds_risk": bool(exceeds),
        "warning": warning,
        "note": risk_note,
        "capital": capital,
        "max_risk_pct": max_risk_pct,
    }
