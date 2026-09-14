"""
Central Orchestrator — coordinates independent analyst agents.

Agent flow (matches Prompt.txt + trading_prompt_master.md):
  Data integrity → Market Research → News → Technical → Patterns →
  Strategies Alpha/Beta/Gamma → Learning → Decision → Risk → Explain
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from analyst.candles import detect_candlestick_patterns_rich, patterns_as_strings
from analyst.chart_patterns import detect_chart_patterns
from analyst.context_gatherer import gather_market_context
from analyst.data_schema import validate_ohlcv_frame
from analyst.decision_engine import build_evidence_factors, decide_from_factors
from analyst.master_output import build_master_output, flat_error_output, master_output_json_string
from analyst.memory import load_memory_feedback
from analyst.models import AnalystResult, MarketRegimeState
from analyst.news_impact import analyze_news_impact
from analyst.regime import auto_indicator_flags, detect_regime
from analyst.report import build_analyst_report
from analyst.risk import build_risk_plan
from analyst.scenarios import build_scenarios
from analyst.strategies import select_active_strategies
from analyst.weight_engine import compute_dynamic_weights
from market_calendar import MarketStatus
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult
from services.market_service import MarketService


def _trace(agent: str, summary: str, **extra: Any) -> dict[str, Any]:
    row = {"agent": agent, "summary": summary}
    row.update(extra)
    return row


def _empty_flags() -> dict[str, bool]:
    return {
        "ema": True,
        "sma": False,
        "vwap": True,
        "bollinger": False,
        "rsi": True,
        "macd": False,
        "volume": True,
        "atr": False,
        "adx": False,
        "support_resistance": True,
        "fibonacci": False,
        "fib_extension": False,
    }


def _flat_error_bundle(reason: str) -> tuple[AnalystResult, PredictionResult, dict[str, bool]]:
    """§4 guardrail — malformed feed → FLAT / HOLD."""
    master = flat_error_output()
    master["technical_rationale"] = reason
    analyst = AnalystResult(
        signal="HOLD",
        confidence=0.0,
        predicted_price=0.0,
        target_price=0.0,
        stop_loss=0.0,
        price_low=0.0,
        price_high=0.0,
        trend="neutral",
        risk_level="High",
        score=0.0,
        market_regime="sideways",
        regime=MarketRegimeState(
            regime="sideways", adx=0, atr_pct=0, vol_ratio=0, notes=[reason]
        ),
        context={"data_error": reason},
        agent_trace=[_trace("Data Integrity", reason)],
        source="ANALYST",
    )
    prediction = PredictionResult(
        signal="HOLD",
        confidence=0.0,
        predicted_price=0.0,
        target_price=0.0,
        stop_loss=0.0,
        price_low=0.0,
        price_high=0.0,
        trend="neutral",
        risk_level="High",
        score=0.0,
        market_regime="sideways",
        reasons=[reason],
        reasons_simple=[reason],
        source="ANALYST",
        raw={
            "data_error": True,
            "master_output": master,
            "master_output_json": master_output_json_string(master),
            "agent_trace": analyst.agent_trace,
        },
    )
    return analyst, prediction, _empty_flags()


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

    # --- 0. Data integrity (trading_prompt_master §1 / §4) ---
    ok, err = validate_ohlcv_frame(df)
    if not ok:
        agent_trace.append(_trace("Data Integrity", err))
        return _flat_error_bundle(err)

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

    # --- Strategy filters Alpha / Beta / Gamma (trading_prompt_master §2) ---
    strategy_bundle = select_active_strategies(
        df=df,
        indicator_ctx=indicator_ctx,
        regime_name=regime.regime,
        news_aggregate=news_agg,
        news_items=news_items,
    )
    agent_trace.append(
        _trace(
            "Strategy Filters",
            f"Primary={strategy_bundle['primary_strategy']} · "
            f"master regime={strategy_bundle['master_regime']} · "
            f"Alpha={strategy_bundle['alpha']['prediction']} "
            f"Beta={strategy_bundle['beta']['prediction']} "
            f"Gamma={strategy_bundle['gamma']['prediction']}.",
            primary=strategy_bundle["primary_strategy"],
            master_regime=strategy_bundle["master_regime"],
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
        strategy_bundle=strategy_bundle,
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
    # Beta guardrail: when Beta is primary and active, force 1.5× ATR stop
    beta = strategy_bundle.get("beta") or {}
    if (
        strategy_bundle.get("primary_strategy") == "Beta"
        and beta.get("active")
        and beta.get("stop_loss_level")
    ):
        risk_plan.stop_loss = float(beta["stop_loss_level"])
        if beta.get("take_profit_target"):
            risk_plan.target_price = float(beta["take_profit_target"])
        # Refresh R:R
        risk_abs = abs(close - risk_plan.stop_loss) or atr * 0.5
        reward_abs = abs(risk_plan.target_price - close) or atr * 0.5
        risk_plan.risk_reward_ratio = round(reward_abs / risk_abs, 2)
        risk_plan.notes = list(risk_plan.notes) + [
            "Beta mean-reversion guardrail: stop fixed at 1.5× ATR from entry pivot."
        ]

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

    # Master rationale (max two sentences)
    rationale_parts = list(primary[:2]) if primary else []
    if not rationale_parts:
        rationale_parts = [
            strategy_bundle["alpha"].get("rationale")
            or "Indicator alignment is mixed with no clear breakout confirmation."
        ]
    technical_rationale = " ".join(rationale_parts)

    master = build_master_output(
        market_regime=strategy_bundle["master_regime"],
        signal=signal,
        confidence=confidence,
        trigger_price=close,
        take_profit_target=risk_plan.target_price,
        stop_loss_level=risk_plan.stop_loss,
        technical_rationale=technical_rationale,
    )

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
            "strategies": strategy_bundle,
            "master_output": master,
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
            "strategies": {
                "master_regime": strategy_bundle["master_regime"],
                "primary_strategy": strategy_bundle["primary_strategy"],
                "alpha": strategy_bundle["alpha"],
                "beta": strategy_bundle["beta"],
                "gamma": strategy_bundle["gamma"],
            },
            "master_output": master,
            "master_output_json": master_output_json_string(master),
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
