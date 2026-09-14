"""
Predefined strategy filters from trading_prompt_master.md §2.

Strategy Alpha — Trend-Following & Momentum
Strategy Beta  — Volatility Mean-Reversion
Strategy Gamma — Event-Driven Sentiment (+ divergence)
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x != x:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def classify_master_regime(indicator_ctx: dict[str, Any], regime_name: str) -> str:
    """Map internal regime → master schema labels."""
    name = (regime_name or "").lower()
    if name in ("volatile",) or _f(indicator_ctx.get("atr"), 0) / max(
        _f((indicator_ctx.get("ohlcv") or {}).get("close"), 1), 1
    ) >= 0.025:
        if name == "volatile":
            return "High Volatility"
    if name == "trending_up" or (
        name == "breakout" and str(indicator_ctx.get("trend_dir")) == "bullish"
    ):
        return "Bullish Expansion"
    if name == "trending_down" or (
        name == "breakout" and str(indicator_ctx.get("trend_dir")) == "bearish"
    ):
        return "Bearish Expansion"
    if name == "sideways":
        return "Mean-Reverting Chop"
    # Fallback from price structure
    trend = str(indicator_ctx.get("trend_dir") or "neutral")
    if trend == "bullish":
        return "Bullish Expansion"
    if trend == "bearish":
        return "Bearish Expansion"
    return "Mean-Reverting Chop"


def run_strategy_alpha(df: pd.DataFrame, indicator_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Trend-Following & Momentum.

    LONG: close above EMA20, RSI 50–65, volume ≥ VOL_MA20
    SHORT: close below EMA20, RSI 35–50, volume ≥ VOL_MA20
    FLAT: otherwise / choppy / volume filter fails
    """
    close = _f((indicator_ctx.get("ohlcv") or {}).get("close"), _f(df["Close"].iloc[-1] if len(df) else 0))
    ema20 = _f(indicator_ctx.get("ema20"), close)
    rsi = _f(indicator_ctx.get("rsi"), 50)
    vol_ratio = _f(indicator_ctx.get("vol_ratio"), 1.0)

    volume_ok = vol_ratio >= 1.0  # current bar vs 20-period volume MA
    rationale_bits: list[str] = []

    # Optional 2-bar confirmation beyond EMA20
    confirmed = True
    if len(df) >= 2 and "EMA20" in df.columns:
        c0, c1 = _f(df["Close"].iloc[-1]), _f(df["Close"].iloc[-2])
        e0, e1 = _f(df["EMA20"].iloc[-1]), _f(df["EMA20"].iloc[-2])
        # For long, both bars above; for short, both below — checked after side pick
    else:
        c0 = c1 = close
        e0 = e1 = ema20

    signal = "FLAT"
    if not volume_ok:
        rationale_bits.append("Volume below 20-period average — momentum breakout disregarded.")
    elif close > ema20 and 50 <= rsi <= 65:
        confirmed = c0 > e0 and c1 > e1
        if confirmed:
            signal = "LONG"
            rationale_bits.append(
                f"Price closed above EMA20 with RSI {rsi:.0f} in 50–65 and volume support."
            )
        else:
            rationale_bits.append("EMA20 breakout not sustained for 2 candles — treated as FLAT.")
    elif close < ema20 and 35 <= rsi <= 50:
        confirmed = c0 < e0 and c1 < e1
        if confirmed:
            signal = "SHORT"
            rationale_bits.append(
                f"Price closed below EMA20 with RSI {rsi:.0f} in 35–50 and volume support."
            )
        else:
            rationale_bits.append("EMA20 breakdown not sustained for 2 candles — treated as FLAT.")
    else:
        rationale_bits.append("Alpha conditions unaligned or choppy — FLAT.")

    signed = 0.85 if signal == "LONG" else (-0.85 if signal == "SHORT" else 0.0)
    return {
        "name": "Alpha",
        "label": "Trend-Following & Momentum",
        "prediction": signal,
        "signed_strength": signed,
        "volume_ok": volume_ok,
        "rationale": " ".join(rationale_bits),
        "active": signal != "FLAT",
    }


def run_strategy_beta(df: pd.DataFrame, indicator_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Volatility Mean-Reversion on Bollinger (20, 2σ).

    Exhaustion: pierce band + volume spike → fade the move.
    Risk guardrail: stop = 1.5 × ATR from entry pivot (close).
    """
    close = _f((indicator_ctx.get("ohlcv") or {}).get("close"), _f(df["Close"].iloc[-1] if len(df) else 0))
    bb_upper = _f(indicator_ctx.get("bb_upper"), close)
    bb_lower = _f(indicator_ctx.get("bb_lower"), close)
    atr = max(_f(indicator_ctx.get("atr"), close * 0.01), close * 0.002, 0.01)
    vol_ratio = _f(indicator_ctx.get("vol_ratio"), 1.0)
    volume_spike = vol_ratio >= 1.35

    signal = "FLAT"
    rationale = "Price inside bands — no Beta exhaustion setup."
    if close >= bb_upper and volume_spike:
        signal = "SHORT"
        rationale = (
            "Price pierced upper Bollinger with volume spike — mean-reversion SHORT exhaustion setup."
        )
    elif close <= bb_lower and volume_spike:
        signal = "LONG"
        rationale = (
            "Price pierced lower Bollinger with volume spike — mean-reversion LONG exhaustion setup."
        )
    elif close >= bb_upper or close <= bb_lower:
        rationale = "Band touch without volume spike — Beta stays FLAT."

    stop_mult = 1.5
    if signal == "LONG":
        stop = round(close - atr * stop_mult, 2)
        target = round(close + atr * 1.5, 2)  # weak/mean-reversion style target
    elif signal == "SHORT":
        stop = round(close + atr * stop_mult, 2)
        target = round(close - atr * 1.5, 2)
    else:
        stop = round(close - atr * stop_mult, 2)
        target = round(close + atr * 0.5, 2)

    signed = 0.7 if signal == "LONG" else (-0.7 if signal == "SHORT" else 0.0)
    return {
        "name": "Beta",
        "label": "Volatility Mean-Reversion",
        "prediction": signal,
        "signed_strength": signed,
        "stop_loss_level": stop,
        "take_profit_target": target,
        "atr_stop_mult": stop_mult,
        "rationale": rationale,
        "active": signal != "FLAT",
    }


def run_strategy_gamma(
    df: pd.DataFrame,
    news_aggregate: dict[str, Any] | None,
    news_items: list | None = None,
) -> dict[str, Any]:
    """
    Event-Driven Sentiment.

    Score headlines on −1.0 … +1.0.
    Divergence: sentiment ≥ +0.7 but price fails to mark a higher high → distribution flag.
    """
    news_aggregate = news_aggregate or {}
    # Map existing net_score roughly into −1…+1
    net = _f(news_aggregate.get("net_score"), 0.0)
    # net is typically small sum of strengths; normalize
    sentiment = max(-1.0, min(1.0, net / 2.5))

    # Prefer strongest single headline signed score if available
    best = 0.0
    for item in news_items or []:
        signed = getattr(item, "signed_score", None)
        if signed is None and isinstance(item, dict):
            signed = item.get("signed_score")
        if signed is not None:
            best = signed if abs(float(signed)) > abs(best) else best
            continue
        if hasattr(item, "impact") and hasattr(item, "strength"):
            s = float(item.strength)
            if item.impact == "bullish":
                best = max(best, s)
            elif item.impact == "bearish":
                best = min(best, -s)
        elif isinstance(item, dict):
            impact = item.get("impact")
            s = float(item.get("strength") or 0)
            if impact == "bullish":
                best = max(best, s)
            elif impact == "bearish":
                best = min(best, -s)
    if abs(best) > abs(sentiment):
        sentiment = max(-1.0, min(1.0, float(best)))

    # Higher-high check on recent closes
    divergence = False
    higher_high = False
    if df is not None and len(df) >= 10:
        highs = df["High"].astype(float).tail(10)
        closes = df["Close"].astype(float).tail(10)
        prior_high = float(highs.iloc[:-1].max())
        last_high = float(highs.iloc[-1])
        higher_high = last_high > prior_high * 1.0005
        if sentiment >= 0.7 and not higher_high:
            divergence = True

    if divergence:
        signal = "SHORT"  # distribution risk — fade / caution short bias
        rationale = (
            f"Sentiment highly positive ({sentiment:+.2f}) but price failed a higher high — "
            "distribution divergence flagged."
        )
        signed = -0.55
    elif sentiment >= 0.45:
        signal = "LONG"
        rationale = f"Event sentiment bullish ({sentiment:+.2f})."
        signed = min(1.0, sentiment)
    elif sentiment <= -0.45:
        signal = "SHORT"
        rationale = f"Event sentiment bearish ({sentiment:+.2f})."
        signed = max(-1.0, sentiment)
    else:
        signal = "FLAT"
        rationale = f"Event sentiment near neutral ({sentiment:+.2f})."
        signed = 0.0

    return {
        "name": "Gamma",
        "label": "Event-Driven Sentiment",
        "prediction": signal,
        "signed_strength": signed,
        "sentiment_score": round(sentiment, 3),
        "divergence": divergence,
        "higher_high": higher_high,
        "rationale": rationale,
        "active": signal != "FLAT",
    }


def select_active_strategies(
    *,
    df: pd.DataFrame,
    indicator_ctx: dict[str, Any],
    regime_name: str,
    news_aggregate: dict[str, Any] | None,
    news_items: list | None,
) -> dict[str, Any]:
    """
    Run Alpha/Beta/Gamma and emphasize the strategy matching the regime.

    Returns bundle used by decision engine + master JSON builder.
    """
    alpha = run_strategy_alpha(df, indicator_ctx)
    beta = run_strategy_beta(df, indicator_ctx)
    gamma = run_strategy_gamma(df, news_aggregate, news_items)
    master_regime = classify_master_regime(indicator_ctx, regime_name)

    # Which filter is primary for this regime
    if master_regime in ("Bullish Expansion", "Bearish Expansion"):
        primary = "Alpha"
    elif master_regime == "High Volatility":
        primary = "Beta"
    elif master_regime == "Mean-Reverting Chop":
        primary = "Beta"
    else:
        primary = "Alpha"

    # Always keep Gamma as overlay when |sentiment| strong or divergence
    strategies = {"Alpha": alpha, "Beta": beta, "Gamma": gamma}
    return {
        "master_regime": master_regime,
        "primary_strategy": primary,
        "strategies": strategies,
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
    }
