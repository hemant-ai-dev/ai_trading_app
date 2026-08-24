"""Step 3 — Detect market regime and auto-select analysis techniques."""

from __future__ import annotations

from typing import Any

from analyst.models import MarketRegimeState


def detect_regime(indicator_ctx: dict[str, Any], market_ctx: dict[str, Any] | None = None) -> MarketRegimeState:
    """
    Decide whether the market is trending, sideways, volatile, or breaking out,
    then choose which techniques an experienced trader would emphasize.
    """
    close = float((indicator_ctx.get("ohlcv") or {}).get("close") or 0)
    adx = float(indicator_ctx.get("adx") or 0)
    atr = float(indicator_ctx.get("atr") or 0)
    atr_pct = (atr / close * 100) if close else 0.0
    vol_ratio = float(indicator_ctx.get("vol_ratio") or 1.0)
    trend_dir = str(indicator_ctx.get("trend_dir") or "neutral")
    ema9 = float(indicator_ctx.get("ema9") or close)
    ema20 = float(indicator_ctx.get("ema20") or close)
    rsi = float(indicator_ctx.get("rsi") or 50)
    vix = None
    if market_ctx:
        vix = market_ctx.get("india_vix")

    notes: list[str] = []
    preferred: list[str] = []
    de_emphasized: list[str] = []

    # Breakout: ADX rising + volume spike + price away from mid
    breakout = vol_ratio >= 1.6 and adx >= 22 and abs(ema9 - ema20) / max(close, 1) > 0.002

    if breakout:
        regime = "breakout"
        preferred = ["volume", "vwap", "ema", "support_resistance", "macd", "atr"]
        de_emphasized = ["rsi_mean_reversion", "bollinger_mean_reversion"]
        notes.append("Volume spike with directional move — prioritize breakout confirmation.")
    elif atr_pct >= 1.8 or (vix is not None and float(vix) >= 18):
        regime = "volatile"
        preferred = ["atr", "vwap", "volume", "support_resistance", "bollinger"]
        de_emphasized = ["tight_targets", "low_liquidity_patterns"]
        notes.append("Elevated volatility — use ATR/VWAP and wider risk bands.")
    elif adx >= 25 and trend_dir in ("bullish", "bearish"):
        regime = "trending_up" if trend_dir == "bullish" else "trending_down"
        preferred = ["ema", "sma", "adx", "macd", "trendline", "fibonacci"]
        de_emphasized = ["rsi_mean_reversion", "range_oscillators"]
        notes.append("ADX shows a real trend — follow EMA/MACD, fade mean-reversion signals.")
    elif adx < 18 or (45 <= rsi <= 55 and abs(ema9 - ema20) / max(close, 1) < 0.0015):
        regime = "sideways"
        preferred = ["rsi", "bollinger", "support_resistance", "volume", "candlestick"]
        de_emphasized = ["trend_following", "ema_stack"]
        notes.append("Range-bound tape — prioritize RSI, Bollinger, and S/R.")
    else:
        # Soft trend
        regime = "trending_up" if trend_dir == "bullish" else (
            "trending_down" if trend_dir == "bearish" else "sideways"
        )
        preferred = ["ema", "rsi", "macd", "fibonacci", "support_resistance"]
        de_emphasized = []
        notes.append("Mixed regime — blend trend and momentum tools carefully.")

    # Fibonacci always useful near swing levels
    fib = indicator_ctx.get("fibonacci")
    if fib is not None:
        preferred = list(dict.fromkeys(preferred + ["fibonacci"]))

    return MarketRegimeState(
        regime=regime,
        adx=adx,
        atr_pct=atr_pct,
        vol_ratio=vol_ratio,
        preferred_techniques=preferred,
        de_emphasized=de_emphasized,
        notes=notes,
    )


def auto_indicator_flags(regime: MarketRegimeState) -> dict[str, bool]:
    """Map regime preferences to chart indicator toggles."""
    pref = set(regime.preferred_techniques)
    return {
        "ema": "ema" in pref or "sma" in pref or regime.regime.startswith("trending"),
        "sma": "sma" in pref,
        "vwap": "vwap" in pref or regime.regime in ("volatile", "breakout"),
        "bollinger": "bollinger" in pref or regime.regime == "sideways",
        "rsi": "rsi" in pref or regime.regime == "sideways",
        "macd": "macd" in pref or regime.regime.startswith("trending") or regime.regime == "breakout",
        "volume": True,
        "atr": "atr" in pref or regime.regime == "volatile",
        "adx": "adx" in pref or regime.regime.startswith("trending"),
        "support_resistance": "support_resistance" in pref or True,
        "fibonacci": "fibonacci" in pref,
        "fib_extension": "fibonacci" in pref and regime.regime.startswith("trending"),
    }
