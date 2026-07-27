"""Tests for prediction engine."""

import pandas as pd
import numpy as np

from indicators.calculator import apply_all_indicators, build_indicator_context
from prediction.rule_engine import predict_rule_based


def _sample_df():
    n = 60
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    df = pd.DataFrame({
        "Open": close, "High": close + 0.5, "Low": close - 0.5,
        "Close": close, "Volume": rng.integers(5000, 20000, n),
    }, index=pd.date_range("2026-01-01", periods=n, freq="5min"))
    return apply_all_indicators(df)


def test_rule_prediction_output():
    df = _sample_df()
    ctx = build_indicator_context(df)
    result = predict_rule_based(df, ctx)
    assert result.signal in ("BUY", "SELL", "HOLD")
    assert 0 < result.confidence <= 100
    assert result.predicted_price > 0
    assert len(result.reasons) > 0
    assert result.risk_level in ("Low", "Medium", "High")


def test_prediction_price_range():
    df = _sample_df()
    ctx = build_indicator_context(df)
    result = predict_rule_based(df, ctx)
    assert result.price_low <= result.price_high
