"""Main prediction orchestrator — adaptive Analyst + optional Gen AI narrative."""

from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.calculator import build_indicator_context, indicator_summary_text
from intraday_forecast import build_comparison_series
from market_calendar import MarketStatus
from prediction.genai_engine import predict_genai
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult
from prediction.rule_engine import predict_rule_based
from services.market_service import MarketService


def run_prediction_pipeline(
    *,
    symbol: str,
    df: pd.DataFrame,
    df_ist: pd.DataFrame,
    ms: MarketStatus,
    llm: Any,
    settings: dict,
    use_genai: bool,
    headline_block: str = "",
    market_context: str = "",
    session_anchor: dict | None = None,
    market: MarketService | None = None,
    equity_news: list | None = None,
    world_news: list | None = None,
    history: PredictionHistoryStore | None = None,
) -> tuple[PredictionResult, PredictionResult, pd.Series | None, dict[str, Any]]:
    """
    Run adaptive AI Trading Analyst pipeline.

    Returns (primary, rule_reference, projection, extras) where extras contains
    analyst metadata, preferred indicator flags, scenarios, and report.
    """
    from analyst.pipeline import run_analyst_pipeline

    indicator_ctx = build_indicator_context(df)
    rule_result = predict_rule_based(df, indicator_ctx)

    market_svc = market or MarketService(settings)
    analyst, analyst_pred, indicator_flags = run_analyst_pipeline(
        symbol=symbol,
        df=df,
        indicator_ctx=indicator_ctx,
        ms=ms,
        market=market_svc,
        equity_news=equity_news,
        world_news=world_news,
        history=history,
    )

    primary = analyst_pred

    # Optional Gen AI: refine narrative / may adjust signal using analyst brief
    if use_genai and llm is not None:
        brief = {
            "analyst_signal": analyst.signal,
            "analyst_confidence": analyst.confidence,
            "regime": analyst.market_regime,
            "preferred_techniques": analyst.preferred_indicators,
            "primary_reasons": primary.reasons[:6],
            "rejected": (primary.raw or {}).get("rejected_signals", [])[:5],
            "news_tilt": (primary.raw or {}).get("news_aggregate", {}),
        }
        genai_result = predict_genai(
            stock=symbol,
            df=df,
            rule_result=primary,  # pass analyst as reference
            indicator_summary=indicator_summary_text(indicator_ctx) + f"\nANALYST_BRIEF: {brief}",
            indicator_ctx=indicator_ctx,
            market_context=market_context,
            headline_block=headline_block,
            ms=ms,
            llm=llm,
            settings=settings,
        )
        if genai_result is not None:
            # Keep analyst structure; merge GenAI narrative into raw/reasons
            merged_raw = dict(primary.raw or {})
            merged_raw["genai"] = genai_result.raw
            merged_raw["market_read"] = genai_result.raw.get("market_read") or genai_result.reasons
            # If GenAI strongly disagrees with high confidence, blend toward GenAI
            if abs(genai_result.confidence - primary.confidence) < 25:
                primary.signal = genai_result.signal
                primary.confidence = round((primary.confidence + genai_result.confidence) / 2, 1)
                primary.predicted_price = genai_result.predicted_price
                primary.target_price = genai_result.target_price
                primary.stop_loss = genai_result.stop_loss
                primary.price_low = genai_result.price_low
                primary.price_high = genai_result.price_high
                if genai_result.reasons_simple or genai_result.reasons:
                    primary.reasons_simple = genai_result.reasons_simple or genai_result.reasons
                    primary.reasons = genai_result.reasons
                if genai_result.projection_series is not None and len(genai_result.projection_series):
                    primary.projection_series = genai_result.projection_series
            else:
                # Keep analyst decision; attach GenAI as alternative view
                merged_raw["genai_alternative"] = {
                    "signal": genai_result.signal,
                    "confidence": genai_result.confidence,
                    "reasons": genai_result.reasons_simple or genai_result.reasons,
                }
            primary.raw = merged_raw
            primary.source = "ANALYST+GENAI"
            # Refresh report prediction fields if present
            if primary.raw.get("report"):
                primary.raw["report"]["prediction"] = primary.signal
                primary.raw["report"]["confidence"] = primary.confidence

    if primary.projection_series is None or len(primary.projection_series) == 0:
        _, proj, _ = build_comparison_series(df_ist, primary.target_price, ms, session_anchor)
        primary.projection_series = proj

    extras = {
        "analyst": analyst,
        "indicator_flags": indicator_flags,
        "scenarios": analyst.scenarios,
        "report": analyst.report,
        "factors": analyst.factors,
        "news_impacts": analyst.news_impacts,
        "regime": analyst.regime,
    }
    return primary, rule_result, primary.projection_series, extras
