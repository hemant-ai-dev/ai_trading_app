"""Plain-language explainable AI output for beginners."""

from __future__ import annotations

from prediction.models import PredictionResult


def _risk_label(confidence: float, atr_pct: float) -> str:
    if atr_pct > 2.5 or confidence < 55:
        return "High"
    if atr_pct > 1.2 or confidence < 70:
        return "Medium"
    return "Low"


def _trend_summary(signal: str, trend_dir: str) -> str:
    if signal == "BUY":
        return "Bullish — the analyst expects prices to move higher."
    if signal == "SELL":
        return "Bearish — the analyst expects prices to move lower."
    if trend_dir == "bullish":
        return "Neutral with bullish bias — wait for confirmation."
    if trend_dir == "bearish":
        return "Neutral with bearish bias — wait for confirmation."
    return "Neutral — no clear direction yet."


def _action_hint(signal: str, risk: str) -> str:
    if signal == "BUY":
        return (
            "Consider buying on dips with a stop-loss below support."
            if risk != "High"
            else "Wait for clearer confirmation before buying."
        )
    if signal == "SELL":
        return (
            "Consider reducing exposure or selling rallies with a stop above resistance."
            if risk != "High"
            else "High risk — avoid aggressive selling; use tight risk controls."
        )
    return "Hold and watch — no strong trade setup right now."


def build_explanation(result: PredictionResult, indicator_ctx: dict) -> dict[str, str | list[str]]:
    """Build beginner-friendly explanation blocks from a prediction / analyst result."""
    close = indicator_ctx["ohlcv"]["close"]
    atr_pct = (indicator_ctx["atr"] / close * 100) if close else 0
    risk = _risk_label(result.confidence, atr_pct)

    simple_reasons = list(result.reasons_simple) if result.reasons_simple else []
    if not simple_reasons:
        simple_reasons = [r for r in result.reasons[:8]]

    raw = result.raw or {}
    rejected = list(raw.get("rejected_signals") or [])
    preferred = list(raw.get("preferred_techniques") or [])
    news_agg = raw.get("news_aggregate") or {}

    return {
        "prediction": f"{result.signal} — target ₹{result.target_price:,.2f}",
        "confidence_text": f"{result.confidence:.0f}% confidence",
        "risk_level": risk,
        "trend_summary": _trend_summary(result.signal, result.trend),
        "suggested_action": _action_hint(result.signal, risk),
        "price_range": f"Expected range: ₹{result.price_low:,.2f} – ₹{result.price_high:,.2f}",
        "reasons": simple_reasons,
        "rejected_signals": rejected,
        "preferred_techniques": preferred,
        "news_summary": news_agg.get("summary") or "",
        "bullish_bearish": result.trend.capitalize(),
        "regime": result.market_regime,
        "report_markdown": raw.get("report_markdown") or "",
    }


def format_reasons_markdown(explanation: dict) -> str:
    """Format explanation as markdown bullet list."""
    lines = [f"**{explanation['prediction']}** ({explanation['confidence_text']})"]
    lines.append(f"**Risk:** {explanation['risk_level']} · **Trend:** {explanation['trend_summary']}")
    if explanation.get("regime"):
        lines.append(f"**Regime:** {explanation['regime']}")
    lines.append(f"**Suggested action:** {explanation['suggested_action']}")
    lines.append(f"**{explanation['price_range']}**")
    lines.append("")
    lines.append("**Why this prediction?**")
    for reason in explanation["reasons"]:
        lines.append(f"- {reason}")
    if explanation.get("rejected_signals"):
        lines.append("")
        lines.append("**Rejected / de-emphasized signals**")
        for r in explanation["rejected_signals"]:
            lines.append(f"- {r}")
    return "\n".join(lines)
