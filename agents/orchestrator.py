"""
Orchestrator Agent — coordinates all specialist agents into one recommendation.

Prefer ``analyst.pipeline.run_analyst_pipeline`` for the production path;
this module exposes the same coordination with explicit agent objects for
clarity and future extension.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from agents import (
    DecisionAgent,
    ExplainableAIAgent,
    LearningAgent,
    MarketDataAgent,
    NewsAgent,
    PatternRecognitionAgent,
    RiskManagementAgent,
    SentimentAgent,
    TechnicalAnalysisAgent,
)
from analyst.models import AnalystResult
from market_calendar import MarketStatus
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult
from services.market_service import MarketService


class OrchestratorAgent:
    """Central coordinator for the multi-agent trading desk."""

    name = "Orchestrator Agent"

    def __init__(self) -> None:
        self.market_data = MarketDataAgent()
        self.news = NewsAgent()
        self.sentiment = SentimentAgent()
        self.technical = TechnicalAnalysisAgent()
        self.patterns = PatternRecognitionAgent()
        self.decision = DecisionAgent()
        self.risk = RiskManagementAgent()
        self.learning = LearningAgent()
        self.explainable = ExplainableAIAgent()

    def run(
        self,
        *,
        symbol: str,
        df: pd.DataFrame,
        indicator_ctx: dict[str, Any],
        ms: MarketStatus,
        market: MarketService,
        equity_news: list | None = None,
        world_news: list | None = None,
        history: PredictionHistoryStore | None = None,
    ) -> tuple[AnalystResult, PredictionResult, dict[str, bool]]:
        """Delegate to the production pipeline (shared implementation)."""
        from analyst.pipeline import run_analyst_pipeline

        return run_analyst_pipeline(
            symbol=symbol,
            df=df,
            indicator_ctx=indicator_ctx,
            ms=ms,
            market=market,
            equity_news=equity_news,
            world_news=world_news,
            history=history,
        )


def run_multi_agent_analysis(**kwargs):
    """Convenience entry used by services / tests."""
    return OrchestratorAgent().run(**kwargs)
