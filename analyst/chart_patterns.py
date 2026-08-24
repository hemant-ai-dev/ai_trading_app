"""Step 4 — Classic chart pattern recognition (heuristic swing-based)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _local_extrema(series: pd.Series, order: int = 3) -> tuple[list[int], list[int]]:
    """Return indices of local highs and lows."""
    vals = series.astype(float).values
    highs: list[int] = []
    lows: list[int] = []
    n = len(vals)
    for i in range(order, n - order):
        window = vals[i - order : i + order + 1]
        if vals[i] == np.max(window):
            highs.append(i)
        if vals[i] == np.min(window):
            lows.append(i)
    return highs, lows


def detect_chart_patterns(df: pd.DataFrame, lookback: int = 60) -> list[dict]:
    """
    Detect common chart patterns using recent swing structure.

    Returns list of {name, direction, strength, reason}.
    Not as precise as discretionary TA — educational heuristics.
    """
    if df is None or len(df) < 20:
        return []

    window = df.tail(lookback).copy()
    close = window["Close"].astype(float)
    high = window["High"].astype(float)
    low = window["Low"].astype(float)
    highs_i, lows_i = _local_extrema(close, order=2)
    patterns: list[dict] = []

    # Double top / bottom
    if len(highs_i) >= 2:
        i1, i2 = highs_i[-2], highs_i[-1]
        p1, p2 = float(high.iloc[i1]), float(high.iloc[i2])
        if abs(p1 - p2) / max(p1, 1e-9) < 0.008 and i2 - i1 >= 3:
            patterns.append(
                {
                    "name": "Double Top",
                    "direction": "bearish",
                    "strength": 0.7,
                    "reason": "Two similar swing highs — possible topping pattern.",
                }
            )
    if len(lows_i) >= 2:
        i1, i2 = lows_i[-2], lows_i[-1]
        p1, p2 = float(low.iloc[i1]), float(low.iloc[i2])
        if abs(p1 - p2) / max(p1, 1e-9) < 0.008 and i2 - i1 >= 3:
            patterns.append(
                {
                    "name": "Double Bottom",
                    "direction": "bullish",
                    "strength": 0.7,
                    "reason": "Two similar swing lows — possible basing / reversal.",
                }
            )

    # Head & Shoulders (simplified 3 highs: left < head > right, shoulders similar)
    if len(highs_i) >= 3:
        a, b, c = highs_i[-3], highs_i[-2], highs_i[-1]
        ha, hb, hc = float(high.iloc[a]), float(high.iloc[b]), float(high.iloc[c])
        if hb > ha and hb > hc and abs(ha - hc) / max(hb, 1e-9) < 0.02:
            patterns.append(
                {
                    "name": "Head & Shoulders",
                    "direction": "bearish",
                    "strength": 0.75,
                    "reason": "Three-peak structure with higher middle peak — classic topping hint.",
                }
            )
        if hb < ha and hb < hc and abs(ha - hc) / max(ha, 1e-9) < 0.02:
            patterns.append(
                {
                    "name": "Inverse Head & Shoulders",
                    "direction": "bullish",
                    "strength": 0.75,
                    "reason": "Three-trough structure with lower middle trough — bullish reversal hint.",
                }
            )

    # Triangle / consolidation: shrinking range
    if len(window) >= 30:
        first = window.iloc[:15]
        last = window.iloc[-15:]
        r1 = float(first["High"].max() - first["Low"].min())
        r2 = float(last["High"].max() - last["Low"].min())
        if r1 > 0 and r2 / r1 < 0.65:
            patterns.append(
                {
                    "name": "Triangle / Compression",
                    "direction": "neutral",
                    "strength": 0.55,
                    "reason": "Price range is compressing — breakout may follow.",
                }
            )

    # Flag / pennant-like: strong move then tight range
    if len(window) >= 25:
        impulse = window.iloc[-25:-10]
        coil = window.iloc[-10:]
        impulse_move = abs(float(impulse["Close"].iloc[-1] - impulse["Close"].iloc[0]))
        coil_range = float(coil["High"].max() - coil["Low"].min())
        if impulse_move > 0 and coil_range / impulse_move < 0.35:
            direction = "bullish" if float(impulse["Close"].iloc[-1]) > float(impulse["Close"].iloc[0]) else "bearish"
            patterns.append(
                {
                    "name": "Flag / Pennant",
                    "direction": direction,
                    "strength": 0.6,
                    "reason": "Sharp move followed by a tight pause — continuation pattern candidate.",
                }
            )

    # Channel: parallel swing highs/lows roughly sloping same way
    if len(highs_i) >= 2 and len(lows_i) >= 2:
        hslope = (float(high.iloc[highs_i[-1]]) - float(high.iloc[highs_i[-2]])) / max(highs_i[-1] - highs_i[-2], 1)
        lslope = (float(low.iloc[lows_i[-1]]) - float(low.iloc[lows_i[-2]])) / max(lows_i[-1] - lows_i[-2], 1)
        if abs(hslope - lslope) < abs(hslope) * 0.5 + 1e-6 and abs(hslope) > 0:
            direction = "bullish" if hslope > 0 else "bearish"
            patterns.append(
                {
                    "name": "Channel",
                    "direction": direction,
                    "strength": 0.5,
                    "reason": "Swing highs and lows slope similarly — price may travel in a channel.",
                }
            )

    # Rectangle: flat highs and lows
    if len(highs_i) >= 2 and len(lows_i) >= 2:
        h_vals = [float(high.iloc[i]) for i in highs_i[-3:]]
        l_vals = [float(low.iloc[i]) for i in lows_i[-3:]]
        if max(h_vals) - min(h_vals) < np.mean(h_vals) * 0.006 and max(l_vals) - min(l_vals) < np.mean(l_vals) * 0.006:
            patterns.append(
                {
                    "name": "Rectangle",
                    "direction": "neutral",
                    "strength": 0.5,
                    "reason": "Similar highs and lows — sideways box / range.",
                }
            )

    # Wedge hint via converging slopes of opposite sign quality
    if len(highs_i) >= 2 and len(lows_i) >= 2:
        hslope = (float(high.iloc[highs_i[-1]]) - float(high.iloc[highs_i[-2]])) / max(highs_i[-1] - highs_i[-2], 1)
        lslope = (float(low.iloc[lows_i[-1]]) - float(low.iloc[lows_i[-2]])) / max(lows_i[-1] - lows_i[-2], 1)
        if hslope < 0 < lslope:
            patterns.append(
                {
                    "name": "Rising/Converging Wedge hint",
                    "direction": "bearish",
                    "strength": 0.45,
                    "reason": "Highs falling while lows rising — squeeze that often resolves sharply.",
                }
            )
        elif hslope > 0 > lslope:
            patterns.append(
                {
                    "name": "Expanding Wedge hint",
                    "direction": "neutral",
                    "strength": 0.4,
                    "reason": "Range is expanding — volatility may stay elevated.",
                }
            )

    # Cup & Handle: rounded base then shallow pullback near prior high
    if len(window) >= 40:
        left = window.iloc[:15]
        mid = window.iloc[15:30]
        right = window.iloc[30:]
        left_high = float(left["High"].max())
        mid_low = float(mid["Low"].min())
        right_high = float(right["High"].max())
        cup_depth = (left_high - mid_low) / max(left_high, 1e-9)
        rim_ok = abs(right_high - left_high) / max(left_high, 1e-9) < 0.03
        handle = right.iloc[-8:] if len(right) >= 8 else right
        handle_depth = (
            (float(handle["High"].max()) - float(handle["Low"].min()))
            / max(float(handle["High"].max()), 1e-9)
        )
        if 0.04 <= cup_depth <= 0.25 and rim_ok and handle_depth < cup_depth * 0.55:
            patterns.append(
                {
                    "name": "Cup & Handle",
                    "direction": "bullish",
                    "strength": 0.65,
                    "reason": "Rounded base with a shallow handle near the rim — bullish continuation candidate.",
                }
            )

    # Harmonic-style AB=CD hint (equal swing legs)
    if len(highs_i) >= 2 and len(lows_i) >= 2:
        a, b = lows_i[-2], highs_i[-1] if highs_i[-1] > lows_i[-2] else highs_i[-2]
        if a < b and b < len(close) - 2:
            leg1 = abs(float(close.iloc[b]) - float(close.iloc[a]))
            c_idx = len(close) - 1
            leg2 = abs(float(close.iloc[c_idx]) - float(close.iloc[b]))
            if leg1 > 0 and abs(leg1 - leg2) / leg1 < 0.12:
                direction = "bullish" if float(close.iloc[c_idx]) > float(close.iloc[a]) else "bearish"
                patterns.append(
                    {
                        "name": "Harmonic AB=CD hint",
                        "direction": direction,
                        "strength": 0.5,
                        "reason": "Two swing legs of similar length — harmonic-style measured-move hint.",
                    }
                )

    # Deduplicate by name
    seen = set()
    unique = []
    for p in patterns:
        if p["name"] in seen:
            continue
        seen.add(p["name"])
        unique.append(p)
    return unique
