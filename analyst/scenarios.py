"""Step 9 — Multi-scenario future projection paths."""

from __future__ import annotations

from typing import Any

import pandas as pd

from analyst.models import ScenarioPath
from intraday_forecast import linear_projection, nse_regular_5m_index
from market_calendar import MarketStatus, SessionPhase


def _session_index(ms: MarketStatus):
    today = ms.now_ist.date()
    if ms.phase in (SessionPhase.HOLIDAY_OR_WEEKEND,) or not ms.is_trading_day:
        return nse_regular_5m_index(ms.next_session_date)
    if ms.phase == SessionPhase.POST_CLOSE:
        return nse_regular_5m_index(ms.next_session_date)
    return nse_regular_5m_index(today)


def build_scenarios(
    *,
    last_close: float,
    atr: float,
    signal: str,
    confidence: float,
    target_price: float,
    stop_loss: float,
    price_low: float,
    price_high: float,
    ms: MarketStatus,
) -> list[ScenarioPath]:
    """
    Build bullish / base / bearish scenario paths from the last price.

    Probabilities tilt with the decided signal and confidence.
    """
    idx = _session_index(ms)
    # Keep only future-ish stamps from now
    now = ms.now_ist
    future_idx = idx[idx >= now]
    if len(future_idx) < 4:
        future_idx = idx[-24:] if len(idx) >= 24 else idx

    atr = max(float(atr), last_close * 0.002, 0.01)
    bull_tgt = max(price_high, target_price, last_close + atr * 2.0)
    bear_tgt = min(price_low, stop_loss if signal != "BUY" else last_close - atr * 2.0, last_close - atr * 2.0)
    base_tgt = float(target_price)

    # Probability mix
    conf_n = max(0.35, min(0.92, confidence / 100))
    if signal == "BUY":
        probs = {"bullish": 0.35 + 0.25 * conf_n, "base": 0.35, "bearish": 0.30 - 0.20 * conf_n}
    elif signal == "SELL":
        probs = {"bearish": 0.35 + 0.25 * conf_n, "base": 0.35, "bullish": 0.30 - 0.20 * conf_n}
    else:
        probs = {"bullish": 0.28, "base": 0.44, "bearish": 0.28}

    # Normalize
    total = sum(probs.values())
    probs = {k: v / total for k, v in probs.items()}

    scenarios = [
        ScenarioPath(
            name="bullish",
            target_price=round(bull_tgt, 2),
            series=linear_projection(future_idx, last_close, bull_tgt),
            probability=probs["bullish"],
            summary=f"Upside path toward ₹{bull_tgt:,.2f} if buyers stay in control.",
            trigger=f"Price confirms above ₹{max(price_high, last_close):,.2f} with volume.",
            invalidation=f"Close falls back below the breakout / last close ₹{last_close:,.2f}.",
            direction="UP",
            evidence="Tilted by the current BUY/HOLD mix and ATR expansion room.",
        ),
        ScenarioPath(
            name="base",
            target_price=round(base_tgt, 2),
            series=linear_projection(future_idx, last_close, base_tgt),
            probability=probs["base"],
            summary=f"Base case path toward ₹{base_tgt:,.2f} (primary prediction).",
            trigger="Price holds the current range and follows the primary path.",
            invalidation="A close through the opposite invalidation (stop) of the primary plan.",
            direction="PRIMARY",
            evidence="Primary model path — not a guarantee.",
        ),
        ScenarioPath(
            name="bearish",
            target_price=round(bear_tgt, 2),
            series=linear_projection(future_idx, last_close, bear_tgt),
            probability=probs["bearish"],
            summary=f"Downside path toward ₹{bear_tgt:,.2f} if sellers dominate.",
            trigger=f"Price confirms below ₹{min(price_low, last_close):,.2f} with volume.",
            invalidation=f"Close reclaims last close ₹{last_close:,.2f} after a failed breakdown.",
            direction="DOWN",
            evidence="Tilted by the current SELL/HOLD mix and ATR downside room.",
        ),
    ]
    return scenarios


def scenario_overlays(scenarios: list[ScenarioPath]) -> dict[str, Any]:
    """Helper for chart layer: return named series dict."""
    return {s.name: s.series for s in scenarios if s.series is not None and len(s.series)}
