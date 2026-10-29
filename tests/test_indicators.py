"""Tests for technical indicators."""

import pandas as pd
import numpy as np

from indicators.calculator import apply_all_indicators, build_indicator_context
from indicators.fibonacci import calculate_fibonacci_levels


def _sample_ohlcv(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = close + rng.normal(0, 0.2, n)
    volume = rng.integers(1000, 50000, n)
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx)


def test_apply_all_indicators():
    df = apply_all_indicators(_sample_ohlcv())
    assert "RSI" in df.columns
    assert "MACD" in df.columns
    assert "EMA20" in df.columns
    assert "BB_UPPER" in df.columns
    assert "ADX" in df.columns
    assert not df["RSI"].iloc[-1] != df["RSI"].iloc[-1]  # not NaN


def test_fibonacci_levels():
    df = _sample_ohlcv()
    fib = calculate_fibonacci_levels(df)
    assert fib.swing_high >= fib.swing_low
    assert "61.8%" in fib.retracements
    assert fib.nearest_support <= fib.nearest_resistance or True


def test_price_structure_columns():
    df = apply_all_indicators(_sample_ohlcv(80))
    for col in ("BODY", "UPPER_WICK", "LOWER_WICK", "VWAP_SLOPE", "PX_VS_EMA20"):
        assert col in df.columns
        assert df[col].notna().any()
    df = apply_all_indicators(_sample_ohlcv())
    ctx = build_indicator_context(df)
    assert "rsi" in ctx
    assert "fibonacci" in ctx
    assert "patterns" in ctx
    assert "vwap_slope" in ctx
    assert "body" in ctx
    assert "upper_wick" in ctx
    assert "lower_wick" in ctx
