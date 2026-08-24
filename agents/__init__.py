"""
Independent agent modules for the Agentic AI Trading Assistant.

Each agent is a thin, named wrapper around specialist logic so the system
stays modular and easy to extend (Prompt.txt §10).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from analyst.candles import detect_candlestick_patterns_rich
from analyst.chart_patterns import detect_chart_patterns
from analyst.context_gatherer import gather_market_context
from analyst.decision_engine import build_evidence_factors, decide_from_factors
from analyst.memory import load_memory_feedback
from analyst.models import MarketRegimeState
from analyst.news_impact import analyze_news_impact
from analyst.regime import auto_indicator_flags, detect_regime
from analyst.report import build_analyst_report
from analyst.risk import RiskPlan, build_risk_plan
from analyst.weight_engine import compute_dynamic_weights
from prediction.history_store import PredictionHistoryStore
from services.market_service import MarketService


class MarketDataAgent:
    """Collect live OHLCV, volume, indices, VIX, and macro proxies."""

    name = "Market Data Agent"

    def run(
        self,
        *,
        symbol: str,
        df: pd.DataFrame,
        market: MarketService,
        indicator_ctx: dict[str, Any],
    ) -> dict[str, Any]:
        return gather_market_context(
            symbol=symbol, df=df, market=market, indicator_ctx=indicator_ctx
        )


class NewsAgent:
    """Score headlines as bullish / bearish / neutral with impact strength."""

    name = "News Agent"

    def run(
        self, equity_news: list | None, world_news: list | None
    ) -> tuple[list, dict[str, Any]]:
        return analyze_news_impact(equity_news, world_news)


class SentimentAgent:
    """Derive aggregate sentiment tilt from scored news (social-ready later)."""

    name = "Sentiment Agent"

    def run(self, news_aggregate: dict[str, Any]) -> dict[str, Any]:
        return {
            "tilt": news_aggregate.get("tilt", "neutral"),
            "net_score": news_aggregate.get("net_score", 0),
            "summary": news_aggregate.get("summary", ""),
            "source": "news_proxy",
        }


class TechnicalAnalysisAgent:
    """Detect regime and choose which indicators matter most right now."""

    name = "Technical Analysis Agent"

    def run(
        self, indicator_ctx: dict[str, Any], market_ctx: dict[str, Any] | None = None
    ) -> tuple[MarketRegimeState, dict[str, bool]]:
        regime = detect_regime(indicator_ctx, market_ctx)
        return regime, auto_indicator_flags(regime)


class PatternRecognitionAgent:
    """Detect chart + candlestick patterns."""

    name = "Pattern Recognition Agent"

    def run(self, df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
        return detect_chart_patterns(df), detect_candlestick_patterns_rich(df)


class DecisionAgent:
    """Weight evidence dynamically and produce BUY / SELL / HOLD."""

    name = "Decision Agent"

    def run(
        self,
        *,
        indicator_ctx: dict[str, Any],
        regime: MarketRegimeState,
        news_aggregate: dict[str, Any],
        news_items: list,
        chart_patterns: list[dict],
        candle_patterns: list[dict],
        market_ctx: dict[str, Any],
        memory: dict[str, Any],
    ) -> tuple[str, float, float, list[str], list[str], list, dict[str, float]]:
        weights = compute_dynamic_weights(regime, news_aggregate, memory)
        factors = build_evidence_factors(
            indicator_ctx=indicator_ctx,
            regime=regime,
            weights=weights,
            news_aggregate=news_aggregate,
            news_items=news_items,
            chart_patterns=chart_patterns,
            candle_patterns=candle_patterns,
            market_ctx=market_ctx,
        )
        signal, confidence, score, primary, rejected = decide_from_factors(factors)
        return signal, confidence, score, primary, rejected, factors, weights


class RiskManagementAgent:
    """Stops, targets, R:R, and position sizing."""

    name = "Risk Management Agent"

    def run(
        self,
        *,
        close: float,
        atr: float,
        signal: str,
        confidence: float,
        regime: str,
    ) -> RiskPlan:
        return build_risk_plan(
            close=close,
            atr=atr,
            signal=signal,
            confidence=confidence,
            regime=regime,
        )


class LearningAgent:
    """Track outcomes and nudge future weights from past accuracy."""

    name = "Learning Agent"

    def run(self, symbol: str, history: PredictionHistoryStore | None = None) -> dict[str, Any]:
        return load_memory_feedback(symbol, history)


class ExplainableAIAgent:
    """Beginner-friendly full report for every prediction."""

    name = "Explainable AI Agent"

    def run(self, **kwargs):
        return build_analyst_report(**kwargs)


# Public registry for discovery / extension
AGENT_CLASSES = {
    "market_data": MarketDataAgent,
    "news": NewsAgent,
    "sentiment": SentimentAgent,
    "technical": TechnicalAnalysisAgent,
    "patterns": PatternRecognitionAgent,
    "decision": DecisionAgent,
    "risk": RiskManagementAgent,
    "learning": LearningAgent,
    "explainable": ExplainableAIAgent,
}
