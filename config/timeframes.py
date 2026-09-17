"""Daily-first chart windows. Live/intraday feeds are not required."""

from __future__ import annotations

TIMEFRAME_PRESETS: list[dict[str, str]] = [
    {"label": "1 Month · Daily", "period": "1mo", "interval": "1d"},
    {"label": "3 Months · Daily", "period": "3mo", "interval": "1d"},
    {"label": "6 Months · Daily", "period": "6mo", "interval": "1d"},
    {"label": "1 Year · Daily", "period": "1y", "interval": "1d"},
    {"label": "5 Days · Daily", "period": "5d", "interval": "1d"},
]

PERIODS = ["5d", "1mo", "3mo", "6mo", "1y"]

INTERVALS = ["1d"]

PERIOD_INTERVALS: dict[str, tuple[str, ...]] = {
    "5d": ("1d",),
    "1mo": ("1d",),
    "3mo": ("1d",),
    "6mo": ("1d",),
    "1y": ("1d",),
}

FETCH_FALLBACKS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("5d", "1d"): [("1mo", "1d")],
    ("1mo", "1d"): [("3mo", "1d")],
    ("3mo", "1d"): [("6mo", "1d")],
    ("6mo", "1d"): [("1y", "1d")],
    ("1y", "1d"): [("2y", "1d")],
}


def intervals_for_period(period: str) -> list[str]:
    return list(PERIOD_INTERVALS.get(period, ("1d",)))


def default_interval(period: str) -> str:
    return "1d"


def label_for(period: str, interval: str) -> str:
    for row in TIMEFRAME_PRESETS:
        if row["period"] == period and row["interval"] == interval:
            return row["label"]
    return f"{period} · {interval}"
