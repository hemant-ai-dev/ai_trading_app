"""Basic candlestick pattern recognition."""

from __future__ import annotations

import pandas as pd


def detect_candlestick_patterns(df: pd.DataFrame) -> list[str]:
    """Detect simple candlestick patterns on the last few bars."""
    if len(df) < 3:
        return []

    patterns: list[str] = []
    o = df["Open"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)

    body = (c - o).abs()
    range_ = (h - l).replace(0, pd.NA)
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l

    last_body = float(body.iloc[-1])
    last_range = float(range_.iloc[-1]) if range_.iloc[-1] == range_.iloc[-1] else 0
    last_upper = float(upper_wick.iloc[-1])
    last_lower = float(lower_wick.iloc[-1])

    if last_range > 0 and last_body / last_range < 0.1:
        patterns.append("Doji — market is undecided; watch for a breakout.")

    if last_range > 0 and last_lower > last_body * 2 and last_upper < last_body * 0.5:
        patterns.append("Hammer — possible bullish reversal after a decline.")

    if last_range > 0 and last_upper > last_body * 2 and last_lower < last_body * 0.5:
        patterns.append("Shooting star — possible bearish reversal after a rally.")

    # Bullish engulfing
    prev_o, prev_c = float(o.iloc[-2]), float(c.iloc[-2])
    cur_o, cur_c = float(o.iloc[-1]), float(c.iloc[-1])
    if prev_c < prev_o and cur_c > cur_o and cur_c > prev_o and cur_o < prev_c:
        patterns.append("Bullish engulfing — buyers took control.")

    if prev_c > prev_o and cur_c < cur_o and cur_c < prev_o and cur_o > prev_c:
        patterns.append("Bearish engulfing — sellers took control.")

    return patterns
