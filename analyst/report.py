"""Step 11 — Detailed final analyst report."""

from __future__ import annotations

from typing import Any

from analyst.models import AnalystReport, AnalystResult, EvidenceFactor, MarketRegimeState, ScenarioPath


def build_analyst_report(
    *,
    symbol: str,
    result: AnalystResult,
    indicator_ctx: dict[str, Any],
    market_ctx: dict[str, Any],
) -> AnalystReport:
    """Compose a beginner-friendly but complete trading analyst report."""
    close = float((indicator_ctx.get("ohlcv") or {}).get("close") or market_ctx.get("live_price") or 0)
    regime: MarketRegimeState | None = result.regime
    accepted = result.accepted_factors
    rejected = result.rejected_factors

    tech_bits = [f.reason for f in accepted if f.category in ("technical", "volume", "fibonacci", "structure")]
    news_bits = [f.reason for f in accepted if f.category == "news"]
    pattern_bits = [f.reason for f in accepted if f.category in ("pattern", "candle")]

    scenarios = result.scenarios
    prob_line = ", ".join(
        f"{s.name.title()} {s.probability * 100:.0f}% (₹{s.target_price:,.2f})" for s in scenarios
    )

    invalidation = []
    if result.signal == "BUY":
        invalidation.append(f"Close below stop ₹{result.stop_loss:,.2f} would invalidate the bullish case.")
        invalidation.append("A high-volume breakdown through nearest support would flip bias to bearish.")
    elif result.signal == "SELL":
        invalidation.append(f"Close above stop ₹{result.stop_loss:,.2f} would invalidate the bearish case.")
        invalidation.append("A high-volume breakout through nearest resistance would flip bias to bullish.")
    else:
        invalidation.append("A decisive breakout with volume beyond the current range would end the HOLD stance.")
        invalidation.append("Major headline shock can override technical balance quickly.")

    if regime and regime.regime == "volatile":
        invalidation.append("Volatility regime — expect wider swings; size risk carefully.")

    report = AnalystReport(
        market_summary=(
            f"{symbol} last traded near ₹{close:,.2f}. "
            f"Regime: {(regime.regime if regime else result.market_regime).replace('_', ' ')}. "
            f"ADX {float(indicator_ctx.get('adx') or 0):.0f}, "
            f"RSI {float(indicator_ctx.get('rsi') or 50):.0f}, "
            f"volume {float(indicator_ctx.get('vol_ratio') or 1):.2f}× average."
        ),
        current_trend=(
            f"Trend bias is **{result.trend}**. "
            + (" ".join(regime.notes) if regime and regime.notes else "")
        ),
        technical_analysis=" ".join(tech_bits[:5]) if tech_bits else "Technical signals are mixed.",
        news_analysis=" ".join(news_bits) if news_bits else "No dominant news driver after impact scoring.",
        pattern_analysis=" ".join(pattern_bits[:4]) if pattern_bits else "No high-conviction pattern dominating.",
        risk_analysis=(
            f"Risk level: **{result.risk_level}**. "
            f"Suggested stop ₹{result.stop_loss:,.2f}. "
            f"Expected range ₹{result.price_low:,.2f} – ₹{result.price_high:,.2f}."
            + (
                f" Risk/Reward 1:{result.risk_plan.get('risk_reward_ratio')}. "
                f"Suggested position ~{result.risk_plan.get('position_size_pct')}% of capital."
                if result.risk_plan
                else ""
            )
        ),
        probability_analysis=prob_line or "Scenario probabilities unavailable.",
        prediction=result.signal,
        confidence=result.confidence,
        why=[f.reason for f in accepted[:8]],
        rejected=[
            f"{f.name}: {f.reject_reason or 'De-emphasized in current market context.'}"
            for f in rejected[:8]
        ],
        invalidation=invalidation,
        targets=[
            f"Primary target ₹{result.target_price:,.2f}",
            f"Predicted waypoint ₹{result.predicted_price:,.2f}",
            f"Upside bound ₹{result.price_high:,.2f}",
            f"Downside bound ₹{result.price_low:,.2f}",
        ],
        stop_loss=f"₹{result.stop_loss:,.2f}",
        alternative_scenarios=[s.summary for s in scenarios],
        sections={
            "preferred_techniques": regime.preferred_techniques if regime else [],
            "de_emphasized": regime.de_emphasized if regime else [],
            "memory": result.memory_adjustment,
            "unavailable_sources": market_ctx.get("unavailable_sources") or {},
        },
    )
    return report
