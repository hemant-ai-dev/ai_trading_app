"""Rule-based prediction model combining technical indicators and Fibonacci."""

from __future__ import annotations

import pandas as pd

from indicators.fibonacci import fibonacci_signal_contribution
from prediction.models import PredictionResult


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None or val != val:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _market_regime(close, ema9, ema20, rsi, vwap, atr) -> str:
    if close > ema9 > ema20 and close > vwap and rsi >= 55:
        return "bullish_trend"
    if close < ema9 < ema20 and close < vwap and rsi <= 45:
        return "bearish_trend"
    if abs(close - vwap) < atr * 0.35:
        return "range_bound"
    if rsi >= 58:
        return "overbought"
    if rsi <= 42:
        return "oversold"
    return "mixed"


def _confidence_from_score(signal: str, score: float, rsi: float) -> float:
    buy_cut, sell_cut = 2.8, -2.8
    if signal == "HOLD":
        neutrality = 1.0 - min(abs(score) / buy_cut, 1.0)
        rsi_neutral = 1.0 - min(abs(rsi - 50) / 25, 1.0)
        return round(42 + (0.6 * neutrality + 0.4 * rsi_neutral) * 28, 1)
    strength = min(abs(score) / 6.0, 1.0)
    conf = 52 + strength * 43
    return round(max(48, min(94, conf)), 1)


def _risk_from_atr(atr_pct: float, confidence: float) -> str:
    if atr_pct > 2.5 or confidence < 55:
        return "High"
    if atr_pct > 1.2 or confidence < 70:
        return "Medium"
    return "Low"


def predict_rule_based(df: pd.DataFrame, indicator_ctx: dict) -> PredictionResult:
    """Generate prediction from weighted technical + Fibonacci scoring."""
    last = df.iloc[-1]
    close = _safe_float(last["Close"], 0)
    ema9 = _safe_float(last.get("EMA9"), close)
    ema20 = _safe_float(last.get("EMA20"), close)
    ema50 = _safe_float(last.get("EMA50"), close)
    rsi = _safe_float(last.get("RSI"), 50)
    macd = _safe_float(last.get("MACD"), 0)
    macd_signal = _safe_float(last.get("MACD_SIGNAL"), 0)
    vwap = _safe_float(last.get("VWAP"), close)
    atr = _safe_float(last.get("ATR"), max(close * 0.01, 1))
    adx = _safe_float(last.get("ADX"), 0)
    vol_ratio = _safe_float(last.get("VOL_RATIO"), 1)
    bb_upper = _safe_float(last.get("BB_UPPER"), close)
    bb_lower = _safe_float(last.get("BB_LOWER"), close)

    score = 0.0
    reasons: list[str] = []
    simple: list[str] = []

    # EMA trend
    if ema9 > ema20 > ema50:
        score += 1.2
        reasons.append("EMA stack bullish (9>20>50)")
        simple.append("Short and medium moving averages point upward — trend is bullish.")
    elif ema9 < ema20 < ema50:
        score -= 1.2
        reasons.append("EMA stack bearish (9<20<50)")
        simple.append("Moving averages are stacked downward — trend is bearish.")
    elif ema9 > ema20:
        score += 0.5
        reasons.append("EMA9 above EMA20")
        simple.append("EMA 20 crossed above EMA 50 — short-term momentum is improving.")
    else:
        score -= 0.5
        reasons.append("EMA9 below EMA20")
        simple.append("Price is below the 20-period average — short-term momentum is weak.")

    # RSI
    if rsi <= 30:
        score += 1.0
        reasons.append(f"RSI oversold ({rsi:.1f})")
        simple.append("RSI is oversold — selling may be exhausted.")
    elif rsi >= 70:
        score -= 1.0
        reasons.append(f"RSI overbought ({rsi:.1f})")
        simple.append("RSI is overbought — rally may be stretched.")
    elif rsi > 55:
        score += 0.4
        reasons.append(f"RSI strong ({rsi:.1f})")
    elif rsi < 45:
        score -= 0.4
        reasons.append(f"RSI weak ({rsi:.1f})")

    # MACD
    if macd > macd_signal and macd > 0:
        score += 1.1
        reasons.append("MACD bullish crossover")
        simple.append("MACD bullish crossover — momentum is turning up.")
    elif macd < macd_signal and macd < 0:
        score -= 1.1
        reasons.append("MACD bearish crossover")
        simple.append("MACD bearish crossover — momentum is turning down.")

    # VWAP
    if close > vwap:
        score += 0.6
        reasons.append("Price above VWAP")
        simple.append("Price is above VWAP — buyers are in control intraday.")
    else:
        score -= 0.6
        reasons.append("Price below VWAP")
        simple.append("Price is below VWAP — sellers have the edge intraday.")

    # Bollinger Bands
    if close <= bb_lower:
        score += 0.5
        reasons.append("Price at lower Bollinger Band")
        simple.append("Price touched the lower Bollinger Band — possible bounce zone.")
    elif close >= bb_upper:
        score -= 0.5
        reasons.append("Price at upper Bollinger Band")
        simple.append("Price touched the upper Bollinger Band — possible pullback zone.")

    # ADX trend strength
    if adx >= 25:
        if score > 0:
            score += 0.4
            reasons.append(f"Strong trend (ADX {adx:.0f})")
            simple.append("ADX shows a strong trend — moves have follow-through.")
        elif score < 0:
            score -= 0.4
            reasons.append(f"Strong downtrend (ADX {adx:.0f})")

    # Volume
    if vol_ratio > 1.2:
        if score > 0:
            score += 0.3
            reasons.append("Volume above average")
            simple.append("Volume increased above average — move has participation.")
        elif score < 0:
            score -= 0.3
            reasons.append("High volume on decline")

    # Fibonacci
    fib = indicator_ctx.get("fibonacci")
    if fib is not None:
        fib_score, fib_reasons = fibonacci_signal_contribution(fib, close)
        score += fib_score
        reasons.extend([f"Fib: {r}" for r in fib_reasons])
        simple.extend(fib_reasons)

    # Candlestick patterns
    for pattern in indicator_ctx.get("patterns") or []:
        if "bullish" in pattern.lower() or "hammer" in pattern.lower():
            score += 0.35
        elif "bearish" in pattern.lower() or "shooting" in pattern.lower():
            score -= 0.35
        simple.append(pattern)

    buy_cut, sell_cut = 2.8, -2.8
    if score >= buy_cut:
        signal = "BUY"
    elif score <= sell_cut:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = _confidence_from_score(signal, score, rsi)
    atr_pct = atr / close * 100 if close else 0
    risk = _risk_from_atr(atr_pct, confidence)
    regime = _market_regime(close, ema9, ema20, rsi, vwap, atr)
    trend = indicator_ctx.get("trend_dir", "neutral")

    if signal == "BUY":
        target = round(close + atr * 2.2, 2)
        stop = round(close - atr * 1.2, 2)
        predicted = round(close + atr * 1.0, 2)
        price_low = round(close - atr * 0.8, 2)
        price_high = round(close + atr * 2.5, 2)
    elif signal == "SELL":
        target = round(close - atr * 2.2, 2)
        stop = round(close + atr * 1.2, 2)
        predicted = round(close - atr * 1.0, 2)
        price_low = round(close - atr * 2.5, 2)
        price_high = round(close + atr * 0.8, 2)
    else:
        target = round(close + atr, 2)
        stop = round(close - atr, 2)
        predicted = round(close, 2)
        price_low = round(close - atr * 1.2, 2)
        price_high = round(close + atr * 1.2, 2)

    return PredictionResult(
        signal=signal,
        confidence=confidence,
        predicted_price=predicted,
        target_price=target,
        stop_loss=stop,
        price_low=price_low,
        price_high=price_high,
        trend=trend,
        risk_level=risk,
        score=round(score, 3),
        market_regime=regime,
        reasons=reasons,
        reasons_simple=simple,
        indicator_snapshot=indicator_ctx,
        source="RULE",
    )
