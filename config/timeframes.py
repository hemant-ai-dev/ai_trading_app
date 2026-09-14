"""Yahoo-safe chart timeframes used by the trading desk."""

from __future__ import annotations

# Yahoo Finance refuses many period/interval pairs (empty frame or silent no-op).
# These presets are known to return usable OHLCV for Indian cash/index symbols.
TIMEFRAME_PRESETS: list[dict[str, str]] = [
    {"label": "1 Day · 1 min", "period": "1d", "interval": "1m"},
    {"label": "1 Day · 5 min", "period": "1d", "interval": "5m"},
    {"label": "1 Day · 15 min", "period": "1d", "interval": "15m"},
    {"label": "1 Day · 1 hour", "period": "1d", "interval": "1h"},
    {"label": "5 Days · 5 min", "period": "5d", "interval": "5m"},
    {"label": "5 Days · 15 min", "period": "5d", "interval": "15m"},
    {"label": "5 Days · 1 hour", "period": "5d", "interval": "1h"},
    {"label": "1 Month · 1 hour", "period": "1mo", "interval": "1h"},
    {"label": "1 Month · Daily", "period": "1mo", "interval": "1d"},
    {"label": "3 Months · Daily", "period": "3mo", "interval": "1d"},
    {"label": "1 Year · Daily", "period": "1y", "interval": "1d"},
]

PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y"]

INTERVALS = ["1m", "2m", "5m", "15m", "30m", "1h", "1d"]

# Intervals Yahoo can serve for a requested lookback window.
PERIOD_INTERVALS: dict[str, tuple[str, ...]] = {
    "1d": ("1m", "2m", "5m", "15m", "30m", "1h"),
    "5d": ("1m", "2m", "5m", "15m", "30m", "1h"),
    "1mo": ("5m", "15m", "30m", "1h", "1d"),
    "3mo": ("1h", "1d"),
    "6mo": ("1h", "1d"),
    "1y": ("1d",),
}

# Fetch fallbacks when the first Yahoo request is empty (weekends, holidays, limits).
FETCH_FALLBACKS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("1d", "1m"): [("2d", "1m"), ("5d", "1m")],
    ("1d", "2m"): [("5d", "2m")],
    ("1d", "5m"): [("5d", "5m")],
    ("1d", "15m"): [("5d", "15m")],
    ("1d", "30m"): [("5d", "30m")],
    ("1d", "1h"): [("5d", "1h"), ("1mo", "1h")],
    ("5d", "1m"): [("7d", "1m")],
    ("5d", "1h"): [("1mo", "1h")],
    ("1mo", "5m"): [("5d", "5m"), ("1mo", "15m")],
    ("1mo", "1h"): [("3mo", "1h")],
}


def intervals_for_period(period: str) -> list[str]:
    return list(PERIOD_INTERVALS.get(period, ("5m", "15m", "1h", "1d")))


def default_interval(period: str) -> str:
    opts = intervals_for_period(period)
    preferred = {"1d": "5m", "5d": "5m", "1mo": "1h", "3mo": "1d", "6mo": "1d", "1y": "1d"}
    want = preferred.get(period, opts[0])
    return want if want in opts else opts[0]


def label_for(period: str, interval: str) -> str:
    for row in TIMEFRAME_PRESETS:
        if row["period"] == period and row["interval"] == interval:
            return row["label"]
    return f"{period} · {interval}"
