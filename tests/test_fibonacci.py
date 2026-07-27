"""Tests for Fibonacci calculations."""

import pandas as pd
import numpy as np

from indicators.fibonacci import calculate_fibonacci_levels, fibonacci_signal_contribution


def test_fibonacci_retracement_count():
    n = 50
    close = np.linspace(90, 110, n)
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.ones(n) * 1000,
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    fib = calculate_fibonacci_levels(df)
    assert len(fib.retracements) == 7
    assert len(fib.extensions) == 3


def test_fibonacci_signal():
    n = 50
    close = np.linspace(90, 110, n)
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": np.ones(n) * 1000,
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    fib = calculate_fibonacci_levels(df)
    score, reasons = fibonacci_signal_contribution(fib, float(close[-1]))
    assert isinstance(score, float)
    assert isinstance(reasons, list)
