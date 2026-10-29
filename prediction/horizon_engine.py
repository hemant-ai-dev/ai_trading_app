"""Multi-horizon prediction engine (1m/5m/15m/30m/60m/EOD).

Model (documented, rule-score driven — versioned as MODEL_VERSION):
  * ATR of the working bar interval scales to the horizon with sqrt-time:
        sigma_h = ATR_bar * sqrt(horizon_minutes / bar_minutes)
  * Directional drift comes from the normalized rule score (|score|<=6):
        mu_h = sign(score) * min(|score| / 6, 1) * 0.5 * sigma_h
  * Expected range is mu_h +/- 1.28 * sigma_h (an ~80% band, not a guarantee).
  * Up/sideways/down probabilities come from a normal approximation around the
    drift, with a sideways band of 0.20 * sigma_h. These are DERIVED SCORES,
    labelled uncalibrated until a calibration table exists (prob_source field).
  * Insufficient bars, missing ATR, or a near-zero score produce
    NO_PREDICTION (nothing is stored for that horizon).

No look-ahead: every input is the state at the prediction timestamp.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)

MODEL_VERSION = "angad-horizon-v1"
HORIZON_MINUTES: dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}
MIN_BARS = 40
UNCERTAIN_SCORE = 0.8
SIDEWAYS_BAND = 0.20
Z80 = 1.2816


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def horizon_prediction(
    *,
    base_price: float,
    atr_bar: float,
    score: float,
    horizon: str,
    bar_minutes: int,
    now_ist: datetime,
    session_close_ist: datetime | None,
    bars_available: int,
) -> dict[str, Any] | None:
    """Return a stored-ready prediction dict, or None for NO_PREDICTION."""
    if horizon == "eod":
        if session_close_ist is None or now_ist >= session_close_ist:
            return None
        minutes = max(int((session_close_ist - now_ist).total_seconds() // 60), 1)
        target = session_close_ist
    else:
        minutes = HORIZON_MINUTES.get(horizon)
        if minutes is None:
            return None
        target = now_ist + timedelta(minutes=minutes)

    if (
        not base_price
        or base_price <= 0
        or not atr_bar
        or atr_bar <= 0
        or bars_available < MIN_BARS
        or abs(score) < UNCERTAIN_SCORE
    ):
        return None

    sigma = atr_bar * math.sqrt(max(minutes / max(bar_minutes, 1), 0.2))
    strength = min(abs(score) / 6.0, 1.0)
    drift = math.copysign(strength * 0.5 * sigma, score)
    predicted = base_price + drift
    price_low = predicted - Z80 * sigma
    price_high = predicted + Z80 * sigma
    band = SIDEWAYS_BAND * sigma

    p_up = 1.0 - _norm_cdf((band - drift) / sigma)
    p_down = _norm_cdf((-band - drift) / sigma)
    p_side = max(0.0, 1.0 - p_up - p_down)
    total = p_up + p_down + p_side
    p_up, p_down, p_side = (100.0 * p_up / total, 100.0 * p_down / total, 100.0 * p_side / total)

    if drift >= 0:
        direction = "Bullish" if p_up >= max(p_down, p_side) else ("Bearish" if p_down > p_side else "Sideways")
    else:
        direction = "Bearish" if p_down >= max(p_up, p_side) else ("Bullish" if p_up > p_side else "Sideways")

    # Horizon decay: longer horizons carry more uncertainty by construction.
    decay = 1.0 / math.sqrt(max(minutes / max(bar_minutes, 1), 1.0))
    confidence = round(48.0 + strength * 34.0 * max(decay, 0.35), 1)

    return {
        "horizon": horizon,
        "minutes": minutes,
        "target_time": target,
        "direction": direction,
        "predicted_price": round(predicted, 2),
        "price_low": round(price_low, 2),
        "price_high": round(price_high, 2),
        "prob_up": round(p_up, 1),
        "prob_sideways": round(p_side, 1),
        "prob_down": round(p_down, 1),
        "prob_source": "score_derived_uncalibrated",
        "confidence": confidence,
        "sigma": sigma,
        "drift": drift,
        "model_version": MODEL_VERSION,
    }


def resample_ohlcv(df, rule: str):
    """Aggregate OHLCV without pulling future bars into earlier buckets.

    The in-progress bucket uses only prints seen so far. Timezone-aware
    indexes are converted to exchange wall time before resampling so daily
    and weekly bins follow the NSE session date.
    """
    import pandas as pd

    if df is None or len(df) == 0 or not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()
    work = df.copy()
    if work.index.tz is not None:
        work.index = work.index.tz_convert("Asia/Kolkata").tz_localize(None)
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in work.columns]
    if len(cols) < 4:
        return pd.DataFrame()
    out = work[cols].resample(rule, label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    return out.dropna(subset=["Open", "High", "Low", "Close"])


def blend_timeframe_score(
    fast_score: float,
    fast_trend: str,
    higher_score: float,
    higher_trend: str,
) -> tuple[float, list[str]]:
    """Multi-timeframe context without blind averaging.

    Aligned timeframes get a modest boost; a conflict dampens the fast score
    and records the disagreement as evidence.
    """
    notes: list[str] = []
    fast_dir = 1 if fast_score > 0 else (-1 if fast_score < 0 else 0)
    slow_dir = 1 if higher_score > 0 else (-1 if higher_score < 0 else 0)
    if fast_dir == 0 or slow_dir == 0:
        notes.append("Higher-timeframe signal neutral — fast score used unchanged.")
        return fast_score, notes
    if fast_dir == slow_dir:
        notes.append(f"Aligned: {fast_trend} short-term with {higher_trend} higher timeframe.")
        return fast_score * 1.15, notes
    notes.append(
        f"Timeframe conflict: short-term {fast_trend} vs higher-timeframe {higher_trend} — conviction reduced."
    )
    return fast_score * 0.55, notes


def signal_from_probs(probs: tuple[float, float, float]) -> str:
    """BUY/SELL only when one direction clearly dominates sideways and the opposite side."""
    up, side, down = probs
    scale = 100.0 if (up + side + down) > 1.5 else 1.0
    margin = 0.03 * scale  # a 3-point lead over the opposing side is required
    if side >= max(up, down):
        return "HOLD"
    if up > down:
        return "BUY" if up - down >= margin and up - side >= margin else "HOLD"
    return "SELL" if down - up >= margin and down - side >= margin else "HOLD"
