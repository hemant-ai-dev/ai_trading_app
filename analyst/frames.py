"""Daily / weekly / monthly context from the same OHLCV the desk already uses."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame()
    work = df.copy()
    if work.index.tz is not None:
        work = work.tz_convert(None)
    # Pandas 2.2+ removed the month-end alias "M" in favor of "ME".
    alias = {"M": "ME", "Q": "QE", "Y": "YE", "A": "YE"}.get(rule, rule)
    try:
        agg = work.resample(alias).agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        )
    except ValueError:
        return pd.DataFrame()
    return agg.dropna(how="any")


def _bar_pack(row: pd.Series | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "open": _f(row.get("Open")),
        "high": _f(row.get("High")),
        "low": _f(row.get("Low")),
        "close": _f(row.get("Close")),
        "volume": _f(row.get("Volume")),
    }


def build_market_frames(df: pd.DataFrame, *, support=None, resistance=None) -> dict[str, Any]:
    """Structured current / daily / weekly / longer-term context. Educational only."""
    if df is None or df.empty:
        return {"ok": False}
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None
    close = _f(last.get("Close"), 0) or 0
    prev_close = _f(prev.get("Close") if prev is not None else None, close) or close
    chg = close - prev_close
    pct = (chg / prev_close * 100) if prev_close else 0
    weekly = _resample(df, "W-FRI")
    monthly = _resample(df, "ME")
    w_last = weekly.iloc[-1] if len(weekly) else None
    w_prev = weekly.iloc[-2] if len(weekly) >= 2 else None
    m_last = monthly.iloc[-1] if len(monthly) else None
    w_trend = "neutral"
    if w_last is not None and w_prev is not None:
        if float(w_last["Close"]) > float(w_prev["Close"]):
            w_trend = "bullish"
        elif float(w_last["Close"]) < float(w_prev["Close"]):
            w_trend = "bearish"
    m_trend = "neutral"
    if m_last is not None and len(monthly) >= 2:
        if float(m_last["Close"]) > float(monthly.iloc[-2]["Close"]):
            m_trend = "bullish"
        elif float(m_last["Close"]) < float(monthly.iloc[-2]["Close"]):
            m_trend = "bearish"
    sup = None
    res = None
    if isinstance(support, (list, tuple)) and support:
        sup = _f(support[0])
    if isinstance(resistance, (list, tuple)) and resistance:
        res = _f(resistance[0])
    return {
        "ok": True,
        "current": {
            **_bar_pack(last),
            "previous_close": round(prev_close, 2),
            "change": round(chg, 2),
            "pct_change": round(pct, 3),
        },
        "daily": {
            "previous_session": _bar_pack(prev) if prev is not None else {},
            "previous_high": _f(prev.get("High") if prev is not None else None),
            "previous_low": _f(prev.get("Low") if prev is not None else None),
            "previous_close": round(prev_close, 2),
            "recent_support": sup,
            "recent_resistance": res,
        },
        "weekly": {
            **_bar_pack(w_last),
            "previous_week_close": _f(w_prev.get("Close") if w_prev is not None else None),
            "trend": w_trend,
            "bars": int(len(weekly)),
        },
        "longer_term": {
            **_bar_pack(m_last),
            "trend": m_trend,
            "bars": int(len(monthly)),
        },
    }
