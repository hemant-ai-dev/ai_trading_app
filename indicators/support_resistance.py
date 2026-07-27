"""Support and resistance level detection."""

from __future__ import annotations

import pandas as pd


def find_support_resistance(df: pd.DataFrame, lookback: int = 40, zones: int = 3) -> dict[str, list[float]]:
    """
    Identify support and resistance using local minima/maxima clustering.

    Returns nearest support and resistance levels below/above current price.
    """
    window = df.tail(lookback)
    if window.empty:
        return {"support": [], "resistance": []}

    close = float(df["Close"].iloc[-1])
    highs = window["High"].astype(float)
    lows = window["Low"].astype(float)

    resistance_candidates = sorted(highs.nlargest(zones * 2).unique(), reverse=True)
    support_candidates = sorted(lows.nsmallest(zones * 2).unique())

    resistance = [r for r in resistance_candidates if r > close][:zones]
    support = [s for s in reversed(support_candidates) if s < close][:zones]

    return {"support": support, "resistance": resistance}
