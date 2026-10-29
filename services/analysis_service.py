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
from services.market_service import MarketService, clip_to_requested_window
from services.news_service import NewsService
from utils.logging import get_logger
from utils.time_utils import ensure_ist_index

logger = get_logger(__name__)


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
        period: str = "3mo",
        interval: str = "1d",
        use_genai: bool = True,
        include_world_news: bool = True,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        ms = get_market_status()
        df_chart = self.market.get_ohlcv(symbol, period, interval)
        if df_chart.empty:
            return {"error": "No market data available.", "market_status": ms}

        fallback_note = str((df_chart.attrs or {}).get("unavailable_note") or "")

        analysis_raw = df_chart
        if len(df_chart) < 40:
            longer = self.market.get_analysis_ohlcv(symbol, period, interval)
            if longer is not None and len(longer) > len(df_chart):
                analysis_raw = longer

        df = apply_all_indicators(analysis_raw)
        from services.api_monitor import log_usage

        log_usage("local_ta", operation="apply_indicators", success=True, endpoint="local://indicators.technical")
        if analysis_raw is df_chart:
            df_ist = ensure_ist_index(df)
        else:
            df_ist = ensure_ist_index(apply_all_indicators(df_chart))
        df_ist = clip_to_requested_window(df_ist, period, interval)
        latest = float(df_ist["Close"].iloc[-1]) if len(df_ist) else float(df["Close"].iloc[-1])
        session_ist = pd.DataFrame()
        try:
            session_raw = self.market.get_session_ohlcv(symbol)
            if session_raw is not None and not session_raw.empty:
                session_ist = ensure_ist_index(session_raw)
                latest = float(session_ist["Close"].iloc[-1])
        except Exception:
            session_ist = pd.DataFrame()

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

        if user_id:
            from prediction import archive

            # Chart refresh evaluates forecasts that are already due. It does not
            # insert a new prediction — that job belongs to the scheduler, keyed
            # by user, symbol, horizon, and minute.
            archive.backfill_actuals(int(user_id), symbol, latest)
            eval_bars = session_ist if not session_ist.empty else df_ist
            try:
                archive.evaluate_due(int(user_id), symbol, eval_bars)
            except Exception as exc:
                logger.warning("evaluate_due failed for %s: %s", symbol, exc)
            horizon_key = {
                "1m": "1m",
                "2m": "1m",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "60m": "60m",
                "1h": "60m",
                "1d": "eod",
            }.get(str(interval))
            try:
                pred_meta = archive.chart_series(int(user_id), symbol, horizon=horizon_key)
            except Exception as exc:
                logger.warning("chart_series failed for %s: %s", symbol, exc)
                pred_meta = pd.DataFrame()
        else:
            pred_meta = pd.DataFrame()
        if pred_meta is not None and not pred_meta.empty:
            pred_track = pd.Series(
                pred_meta["predicted_price"].astype(float).to_numpy(),
                index=pd.DatetimeIndex(pred_meta["target_time"]),
                name="ai_predicted",
            )
        else:
            pred_track = pd.Series(dtype=float)
            pred_meta = pd.DataFrame()
        explanation = build_explanation(primary, primary.indicator_snapshot)
        snap = primary.indicator_snapshot or {}
        from analyst.memory import similar_setups

        similar = similar_setups(
            symbol,
            {
                "rsi": snap.get("rsi"),
                "adx": snap.get("adx"),
                "trend": snap.get("trend_dir") or primary.trend,
                "regime": primary.market_regime,
            },
            user_id=user_id,
        )
        if isinstance(primary.raw, dict):
            primary.raw["similar_setups"] = similar

        last_session = df_ist.index[-1].date()
        session_slice = df_ist.loc[df_ist.index.map(lambda t: t.date()) == last_session]
        if session_ist is not None and not session_ist.empty:
            live_line = session_ist["Close"]
        else:
            live_line = session_slice["Close"] if not session_slice.empty else df_ist["Close"]

        return {
            "symbol": symbol,
            "market_status": ms,
            "df": df,
            "df_ist": df_ist,
            "live_line": live_line,
            "pred_track": pred_track,
            "pred_meta": pred_meta,
            "actual_track": None,
            "chart_period": period,
            "chart_interval": interval,
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
            "trade_plan": (primary.raw or {}).get("trade_plan"),
            "market_frames": (primary.raw or {}).get("market_frames"),
            "similar_setups": similar,
            "fallback_note": fallback_note,
        }
