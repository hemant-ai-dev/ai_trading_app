"""Application services — orchestration layer."""

from __future__ import annotations

__all__ = ["AnalysisService", "MarketService", "NewsService"]


def __getattr__(name: str):
    if name == "AnalysisService":
        from services.analysis_service import AnalysisService

        return AnalysisService
    if name == "MarketService":
        from services.market_service import MarketService

        return MarketService
    if name == "NewsService":
        from services.news_service import NewsService

        return NewsService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
