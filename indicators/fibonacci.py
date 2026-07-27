"""Fibonacci retracement, extension, and support/resistance levels."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


RETRACEMENT_RATIOS = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
EXTENSION_RATIOS = (1.272, 1.618, 2.0)


@dataclass
class FibonacciLevels:
    swing_high: float
    swing_low: float
    trend: str
    retracements: dict[str, float]
    extensions: dict[str, float]
    nearest_support: float
    nearest_resistance: float


def _find_swing_points(df: pd.DataFrame, lookback: int = 50) -> tuple[float, float, str]:
    """Identify recent swing high/low for Fibonacci calculations."""
    window = df.tail(lookback)
    swing_high = float(window["High"].max())
    swing_low = float(window["Low"].min())
    close = float(df["Close"].iloc[-1])
    mid = (swing_high + swing_low) / 2
    trend = "bullish" if close >= mid else "bearish"
    return swing_high, swing_low, trend


def calculate_fibonacci_levels(df: pd.DataFrame, lookback: int = 50) -> FibonacciLevels:
    """
    Compute Fibonacci retracement and extension levels from recent swing range.

    In an uptrend, retracements measure pullbacks from high toward low.
    In a downtrend, retracements measure bounces from low toward high.
    """
    swing_high, swing_low, trend = _find_swing_points(df, lookback)
    span = swing_high - swing_low
    if span <= 0:
        span = max(swing_high * 0.01, 1.0)

    retracements: dict[str, float] = {}
    extensions: dict[str, float] = {}

    if trend == "bullish":
        for ratio in RETRACEMENT_RATIOS:
            retracements[f"{ratio * 100:.1f}%"] = round(swing_high - span * ratio, 2)
        for ratio in EXTENSION_RATIOS:
            extensions[f"{ratio * 100:.1f}%"] = round(swing_high + span * (ratio - 1), 2)
    else:
        for ratio in RETRACEMENT_RATIOS:
            retracements[f"{ratio * 100:.1f}%"] = round(swing_low + span * ratio, 2)
        for ratio in EXTENSION_RATIOS:
            extensions[f"{ratio * 100:.1f}%"] = round(swing_low - span * (ratio - 1), 2)

    close = float(df["Close"].iloc[-1])
    supports = [v for v in retracements.values() if v < close]
    resistances = [v for v in retracements.values() if v > close]

    nearest_support = max(supports) if supports else swing_low
    nearest_resistance = min(resistances) if resistances else swing_high

    return FibonacciLevels(
        swing_high=swing_high,
        swing_low=swing_low,
        trend=trend,
        retracements=retracements,
        extensions=extensions,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
    )


def fibonacci_signal_contribution(fib: FibonacciLevels, close: float) -> tuple[float, list[str]]:
    """Score contribution from Fibonacci proximity (-1 to +1 scale contribution)."""
    reasons: list[str] = []
    score = 0.0
    tol = close * 0.003

    for label, level in fib.retracements.items():
        if abs(close - level) <= tol:
            if label in ("61.8%", "50.0%", "38.2%"):
                if fib.trend == "bullish":
                    score += 0.6
                    reasons.append(f"Price bounced near Fibonacci {label} support.")
                else:
                    score -= 0.6
                    reasons.append(f"Price rejected near Fibonacci {label} resistance.")
            break

    if close > fib.nearest_resistance * 0.998:
        score += 0.3
        reasons.append("Price is testing Fibonacci resistance zone.")
    elif close < fib.nearest_support * 1.002:
        score -= 0.3
        reasons.append("Price is testing Fibonacci support zone.")

    return score, reasons
