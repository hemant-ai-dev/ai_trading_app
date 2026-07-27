"""Main prediction orchestrator — combines rule and Gen AI models."""

from __future__ import annotations

from typing import Any

import pandas as pd

from indicators.calculator import build_indicator_context, indicator_summary_text
from intraday_forecast import build_comparison_series
from market_calendar import MarketStatus
from prediction.genai_engine import predict_genai
from prediction.models import PredictionResult
from prediction.rule_engine import predict_rule_based


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
) -> tuple[PredictionResult, PredictionResult, pd.Series | None]:
    """
    Run full prediction pipeline.

    Returns (primary_result, rule_result, projection_series).
    """
    indicator_ctx = build_indicator_context(df)
    rule_result = predict_rule_based(df, indicator_ctx)

    genai_result: PredictionResult | None = None
    if use_genai and llm is not None:
        genai_result = predict_genai(
            stock=symbol,
            df=df,
            rule_result=rule_result,
            indicator_summary=indicator_summary_text(indicator_ctx),
            indicator_ctx=indicator_ctx,
            market_context=market_context,
            headline_block=headline_block,
            ms=ms,
            llm=llm,
            settings=settings,
        )

    primary = genai_result if genai_result else rule_result

    if primary.projection_series is None or len(primary.projection_series) == 0:
        _, proj, _ = build_comparison_series(df_ist, primary.target_price, ms, session_anchor)
        primary.projection_series = proj

    return primary, rule_result, primary.projection_series
