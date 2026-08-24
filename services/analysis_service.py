"""Full analysis orchestration — AI Trading Analyst entry point."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ai.explainer import build_explanation
from ai.registry import build_llm_provider
from indicators.calculator import apply_all_indicators
from market_calendar import format_market_context_for_llm, get_market_status
from market_intel import format_headlines_indexed_for_prompt
from prediction.engine import run_prediction_pipeline
from prediction.history_store import PredictionHistoryStore
from services.market_service import MarketService
from services.news_service import NewsService
from utils.time_utils import ensure_ist_index


class AnalysisService:
    """Orchestrate context gathering, adaptive analyst, and persistence."""

    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.market = MarketService(settings)
        self.news = NewsService(settings)
        self.history = PredictionHistoryStore()

    def analyze(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "5m",
        use_genai: bool = True,
        include_world_news: bool = True,
    ) -> dict[str, Any]:
        ms = get_market_status()
        df = self.market.get_ohlcv(symbol, period, interval)
        if df.empty:
            return {"error": "No market data available.", "market_status": ms}

        df = apply_all_indicators(df)
        df_ist = ensure_ist_index(df)
        latest = float(df["Close"].iloc[-1])

        equity_news, world_news = self.news.gather(symbol, include_world_news)
        headline_block, _ = format_headlines_indexed_for_prompt(equity_news, world_news)
        market_context = format_market_context_for_llm(ms)

        llm = build_llm_provider(self.settings) if use_genai else None
        primary, rule_result, projection, extras = run_prediction_pipeline(
            symbol=symbol,
            df=df,
            df_ist=df_ist,
            ms=ms,
            llm=llm,
            settings=self.settings,
            use_genai=use_genai and llm is not None,
            headline_block=headline_block,
            market_context=market_context,
            market=self.market,
            equity_news=equity_news,
            world_news=world_news,
            history=self.history,
        )

        self.history.update_actual_prices(symbol, latest)
        self.history.save_prediction(symbol, primary, market_price=latest)
        explanation = build_explanation(primary, primary.indicator_snapshot)

        today = ms.now_ist.date()
        today_slice = df_ist.loc[df_ist.index.map(lambda t: t.date()) == today]
        live_line = today_slice["Close"] if not today_slice.empty else pd.Series(dtype=float)

        return {
            "symbol": symbol,
            "market_status": ms,
            "df": df,
            "df_ist": df_ist,
            "live_line": live_line,
            "latest_price": latest,
            "primary": primary,
            "rule_result": rule_result,
            "projection": projection,
            "explanation": explanation,
            "equity_news": equity_news,
            "world_news": world_news,
            "headline_block": headline_block,
            "analyst": extras.get("analyst"),
            "indicator_flags": extras.get("indicator_flags"),
            "scenarios": extras.get("scenarios"),
            "report": extras.get("report"),
            "factors": extras.get("factors"),
            "news_impacts": extras.get("news_impacts"),
            "regime": extras.get("regime"),
            "risk_plan": (primary.raw or {}).get("risk_plan"),
            "agent_trace": (primary.raw or {}).get("agent_trace"),
        }
