"""Option intelligence unit tests (no network)."""

import pandas as pd

from options.classify import moneyness_label
from options.intelligence import recommend


def _side(strikes, right, spot=100):
    return pd.DataFrame(
        {
            "strike": strikes,
            "ltp": [2.5, 1.8, 1.1],
            "bid": [2.4, 1.7, 1.0],
            "ask": [2.6, 1.9, 1.2],
            "spread": [0.2, 0.2, 0.2],
            "volume": [800, 1200, 400],
            "open_interest": [5000, 8000, 2000],
            "iv": [0.22, 0.25, 0.3],
            "right": right,
        }
    )


def test_moneyness_atm_call():
    assert moneyness_label(100, 100.2, "CE") == "ATM"
    assert moneyness_label(100, 95, "CE") == "ITM"
    assert moneyness_label(100, 108, "PE") == "ITM"


def test_recommend_separates_hold_from_trade():
    rec = recommend(
        underlying="RELIANCE.NS",
        spot=100,
        predicted_underlying=100.1,
        signal="HOLD",
        trend="sideways",
        confidence=48,
        rsi=51,
        macd=0.0,
        atr=1.2,
        vwap=100,
        expiry="2026-10-01",
        days_remaining=5,
        calls=_side([98, 100, 102], "CE"),
        puts=_side([98, 100, 102], "PE"),
    )
    assert rec["prediction"]["bias"] in ("Bullish", "Bearish", "Unclear")
    assert rec["action"] in ("NO TRADE", "WAIT")
    assert rec["prediction"]["separate_from_trade"] is True


def test_recommend_buy_attaches_theoretical_greeks():
    rec = recommend(
        underlying="RELIANCE.NS",
        spot=100,
        predicted_underlying=108,
        signal="BUY",
        trend="bullish",
        confidence=80,
        rsi=62,
        macd=0.4,
        atr=1.2,
        vwap=99,
        expiry="2026-11-01",
        days_remaining=12,
        calls=_side([98, 100, 102], "CE"),
        puts=_side([98, 100, 102], "PE"),
    )
    if rec.get("strike"):
        assert rec.get("greeks", {}).get("source") == "black_scholes_theoretical"
        assert rec["greeks"]["delta"] is not None
