"""
Central Orchestrator — coordinates independent analyst agents.

Agent flow (matches Prompt.txt):
  Market Research → News Intelligence → Technical Analysis →
  Pattern Recognition → Decision (with dynamic weights) →
  Risk Management → Explainable AI → Learning feedback
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from analyst.candles import detect_candlestick_patterns_rich, patterns_as_strings
from analyst.chart_patterns import detect_chart_patterns
from analyst.context_gatherer import gather_market_context
from analyst.decision_engine import build_evidence_factors, decide_from_factors
from analyst.memory import load_memory_feedback
from analyst.models import AnalystResult
from analyst.news_impact import analyze_news_impact
from analyst.regime import auto_indicator_flags, detect_regime
from analyst.report import build_analyst_report
from analyst.risk import build_risk_plan
from analyst.scenarios import build_scenarios
from analyst.weight_engine import compute_dynamic_weights
from market_calendar import MarketStatus
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult
from services.market_service import MarketService


def _trace(agent: str, summary: str, **extra: Any) -> dict[str, Any]:
    row = {"agent": agent, "summary": summary}
    row.update(extra)
    return row


def run_analyst_pipeline(
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
    """
    Orchestrator entry point for the Agentic AI Trading Assistant.

    Returns (analyst_result, prediction_result_for_compat, preferred_indicator_flags).
    """
    history = history or PredictionHistoryStore()
    agent_trace: list[dict[str, Any]] = []

    # --- 1. Market Research Agent ---
    market_ctx = gather_market_context(
        symbol=symbol, df=df, market=market, indicator_ctx=indicator_ctx
    )
    agent_trace.append(
        _trace(
            "Market Research Agent",
            f"Collected OHLCV ({market_ctx.get('ohlcv_bars')} bars) + macro proxies.",
            live_price=market_ctx.get("live_price"),
            unavailable=list((market_ctx.get("unavailable_sources") or {}).keys()),
        )
    )

    # --- 2. News Intelligence Agent ---
    news_items, news_agg = analyze_news_impact(equity_news, world_news)
    agent_trace.append(
        _trace(
            "News Intelligence Agent",
            news_agg.get("summary") or "No news scored.",
            tilt=news_agg.get("tilt"),
            count=news_agg.get("count"),
        )
    )

    # --- 3. Technical Analysis Agent (regime + technique selection) ---
    regime = detect_regime(indicator_ctx, market_ctx)
    indicator_flags = auto_indicator_flags(regime)
    agent_trace.append(
        _trace(
            "Technical Analysis Agent",
            f"Regime={regime.regime}; emphasizing {', '.join(regime.preferred_techniques[:5]) or 'mixed tools'}.",
            preferred=regime.preferred_techniques,
            de_emphasized=regime.de_emphasized,
        )
    )

    # --- 4. Pattern Recognition Agent ---
    chart_patterns = detect_chart_patterns(df)
    candle_patterns = detect_candlestick_patterns_rich(df)
    agent_trace.append(
        _trace(
            "Pattern Recognition Agent",
            f"{len(chart_patterns)} chart + {len(candle_patterns)} candle patterns.",
            chart=[p["name"] for p in chart_patterns],
            candles=[p["name"] for p in candle_patterns],
        )
    )

    # --- 8. Learning Agent (memory before weights) ---
    memory = load_memory_feedback(symbol, history)
    agent_trace.append(
        _trace(
            "Learning Agent",
            (memory.get("notes") or ["No calibration yet."])[0],
            nudges=memory.get("weight_nudges") or {},
        )
    )

    # --- 5. Decision Agent (dynamic weights + evidence fusion) ---
    weights = compute_dynamic_weights(regime, news_agg, memory)
    factors = build_evidence_factors(
        indicator_ctx=indicator_ctx,
        regime=regime,
        weights=weights,
        news_aggregate=news_agg,
        news_items=news_items,
        chart_patterns=chart_patterns,
        candle_patterns=candle_patterns,
        market_ctx=market_ctx,
    )
    signal, confidence, score, primary, rejected = decide_from_factors(factors)
    agent_trace.append(
        _trace(
            "Decision Agent",
            f"{signal} @ {confidence:.0f}% confidence (score {score:+.2f}).",
            accepted=len([f for f in factors if f.accepted]),
            rejected=len([f for f in factors if not f.accepted]),
        )
    )

    close = float((indicator_ctx.get("ohlcv") or {}).get("close") or df["Close"].iloc[-1])
    atr = float(indicator_ctx.get("atr") or max(close * 0.01, 1))
    trend = str(indicator_ctx.get("trend_dir") or "neutral")

    # --- 6. Risk Management Agent ---
    risk_plan = build_risk_plan(
        close=close,
        atr=atr,
        signal=signal,
        confidence=confidence,
        regime=regime.regime,
    )
    agent_trace.append(
        _trace(
            "Risk Management Agent",
            f"{risk_plan.risk_level} risk · R:R 1:{risk_plan.risk_reward_ratio} · "
            f"stop ₹{risk_plan.stop_loss:,.2f}.",
            risk_reward=risk_plan.risk_reward_ratio,
            position_size_pct=risk_plan.position_size_pct,
        )
    )

    # --- Scenarios (probability paths) ---
    scenarios = build_scenarios(
        last_close=close,
        atr=atr,
        signal=signal,
        confidence=confidence,
        target_price=risk_plan.target_price,
        stop_loss=risk_plan.stop_loss,
        price_low=risk_plan.price_low,
        price_high=risk_plan.price_high,
        ms=ms,
    )
    base_series = next((s.series for s in scenarios if s.name == "base"), None)

    analyst = AnalystResult(
        signal=signal,
        confidence=confidence,
        predicted_price=risk_plan.predicted_price,
        target_price=risk_plan.target_price,
        stop_loss=risk_plan.stop_loss,
        price_low=risk_plan.price_low,
        price_high=risk_plan.price_high,
        trend=trend,
        risk_level=risk_plan.risk_level,
        score=score,
        market_regime=regime.regime,
        regime=regime,
        factors=factors,
        news_impacts=news_items,
        scenarios=scenarios,
        context={
            "market": market_ctx,
            "news_aggregate": news_agg,
            "weights": weights,
        },
        preferred_indicators=regime.preferred_techniques,
        chart_patterns=[p["name"] + " — " + p["reason"] for p in chart_patterns],
        candle_patterns=patterns_as_strings(candle_patterns),
        memory_adjustment=memory,
        risk_plan=risk_plan.to_dict(),
        agent_trace=agent_trace,
        source="ANALYST",
    )

    # --- 7. Explainable AI Agent ---
    analyst.report = build_analyst_report(
        symbol=symbol,
        result=analyst,
        indicator_ctx=indicator_ctx,
        market_ctx=market_ctx,
    )
    # Enrich risk section with position guidance
    if analyst.report and risk_plan.notes:
        analyst.report.risk_analysis = (
            (analyst.report.risk_analysis or "") + " " + " ".join(risk_plan.notes)
        ).strip()
    agent_trace.append(
        _trace(
            "Explainable AI Agent",
            f"Report ready: {signal} with {len(primary)} supporting reasons.",
        )
    )

    # Compatibility PredictionResult for existing UI / history
    prediction = PredictionResult(
        signal=signal,
        confidence=confidence,
        predicted_price=risk_plan.predicted_price,
        target_price=risk_plan.target_price,
        stop_loss=risk_plan.stop_loss,
        price_low=risk_plan.price_low,
        price_high=risk_plan.price_high,
        trend=trend,
        risk_level=risk_plan.risk_level,
        score=score,
        market_regime=regime.regime,
        reasons=primary,
        reasons_simple=primary,
        projection_series=base_series,
        indicator_snapshot=indicator_ctx,
        source="ANALYST",
        raw={
            "analyst": True,
            "rejected_signals": rejected,
            "preferred_techniques": regime.preferred_techniques,
            "de_emphasized": regime.de_emphasized,
            "weights": weights,
            "news_aggregate": news_agg,
            "news_impacts": [n.to_dict() for n in news_items[:10]],
            "chart_patterns": chart_patterns,
            "candle_patterns": candle_patterns,
            "scenarios": [s.to_dict() for s in scenarios],
            "report": analyst.report.to_dict() if analyst.report else {},
            "report_markdown": analyst.report.to_markdown() if analyst.report else "",
            "memory": memory,
            "risk_plan": risk_plan.to_dict(),
            "agent_trace": agent_trace,
            "market_context": {
                k: v
                for k, v in market_ctx.items()
                if k not in ("unavailable_sources",)
            },
            "unavailable_sources": market_ctx.get("unavailable_sources"),
            "factors": [f.to_dict() for f in factors],
        },
    )
    return analyst, prediction, indicator_flags
