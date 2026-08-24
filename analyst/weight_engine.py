"""Step 6 — Dynamic weight engine (context-aware, not fixed rules)."""

from __future__ import annotations

from typing import Any

from analyst.models import MarketRegimeState


# Base importance by category; regime and news amplify/dampen these.
BASE_WEIGHTS: dict[str, float] = {
    "trend": 1.0,
    "momentum": 0.9,
    "macd": 0.9,
    "vwap": 0.7,
    "bollinger": 0.6,
    "volume": 0.7,
    "fibonacci": 0.8,
    "support_resistance": 0.75,
    "candlestick": 0.55,
    "chart_pattern": 0.7,
    "news": 0.85,
    "macro": 0.5,
    "relative_strength": 0.55,
    "adx": 0.5,
}


def compute_dynamic_weights(
    regime: MarketRegimeState,
    news_aggregate: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
) -> dict[str, float]:
    """
    Assign dynamic weights based on what matters *right now*.

    Examples:
      - Major earnings/news → boost news
      - Trending market → boost EMA/MACD/ADX, cut RSI mean-reversion
      - Sideways → boost RSI/Bollinger/S&R
      - Breakout + volume → boost volume/VWAP
      - Memory: if past wins correlated with fib, nudge fib higher
    """
    w = dict(BASE_WEIGHTS)
    pref = set(regime.preferred_techniques)
    de = set(regime.de_emphasized)

    # Regime mapping
    if regime.regime.startswith("trending"):
        w["trend"] *= 1.35
        w["macd"] *= 1.25
        w["adx"] *= 1.3
        w["fibonacci"] *= 1.15
        w["momentum"] *= 0.75  # less mean-reversion
        w["bollinger"] *= 0.7
    elif regime.regime == "sideways":
        w["momentum"] *= 1.35
        w["bollinger"] *= 1.35
        w["support_resistance"] *= 1.3
        w["candlestick"] *= 1.15
        w["trend"] *= 0.65
        w["macd"] *= 0.75
    elif regime.regime == "volatile":
        w["volume"] *= 1.25
        w["vwap"] *= 1.3
        w["support_resistance"] *= 1.15
        w["news"] *= 1.1
        w["chart_pattern"] *= 0.85
    elif regime.regime == "breakout":
        w["volume"] *= 1.45
        w["vwap"] *= 1.25
        w["trend"] *= 1.2
        w["macd"] *= 1.15
        w["support_resistance"] *= 1.1
        w["momentum"] *= 0.7

    # Preferred / de-emphasized techniques
    technique_map = {
        "ema": "trend",
        "sma": "trend",
        "adx": "adx",
        "macd": "macd",
        "rsi": "momentum",
        "bollinger": "bollinger",
        "vwap": "vwap",
        "atr": "volume",
        "volume": "volume",
        "fibonacci": "fibonacci",
        "support_resistance": "support_resistance",
        "candlestick": "candlestick",
        "trendline": "trend",
    }
    for tech in pref:
        key = technique_map.get(tech)
        if key:
            w[key] = w.get(key, 1.0) * 1.15
    for tech in de:
        key = technique_map.get(tech) or tech.replace("_mean_reversion", "")
        # map rsi_mean_reversion → momentum
        if "rsi" in tech:
            key = "momentum"
        if key in w:
            w[key] *= 0.55

    # News dominance
    news_aggregate = news_aggregate or {}
    if news_aggregate.get("major_event"):
        w["news"] *= 1.6
        # Soften pure oscillators when a major headline dominates
        w["momentum"] *= 0.8
        w["bollinger"] *= 0.85
    elif abs(float(news_aggregate.get("net_score") or 0)) > 0.8:
        w["news"] *= 1.3

    # Memory feedback (accuracy-informed nudge)
    memory = memory or {}
    for key, bump in (memory.get("weight_nudges") or {}).items():
        if key in w:
            w[key] *= float(bump)

    # Normalize roughly around 1.0 mean
    mean = sum(w.values()) / max(len(w), 1)
    if mean > 0:
        w = {k: round(v / mean, 3) for k, v in w.items()}
    return w
