"""Step 6 continued — Fuse evidence with dynamic weights; accept/reject signals."""

from __future__ import annotations

from typing import Any

from analyst.models import EvidenceFactor, MarketRegimeState
from indicators.fibonacci import fibonacci_signal_contribution


def _dir_from_sign(x: float) -> str:
    if x > 0.05:
        return "bullish"
    if x < -0.05:
        return "bearish"
    return "neutral"


def build_evidence_factors(
    *,
    indicator_ctx: dict[str, Any],
    regime: MarketRegimeState,
    weights: dict[str, float],
    news_aggregate: dict[str, Any],
    news_items: list,
    chart_patterns: list[dict],
    candle_patterns: list[dict],
    market_ctx: dict[str, Any],
    strategy_bundle: dict[str, Any] | None = None,
) -> list[EvidenceFactor]:
    """Create weighted evidence factors from all analyst inputs."""
    factors: list[EvidenceFactor] = []
    close = float((indicator_ctx.get("ohlcv") or {}).get("close") or 0)
    ema9 = float(indicator_ctx.get("ema9") or close)
    ema20 = float(indicator_ctx.get("ema20") or close)
    ema50 = float(indicator_ctx.get("ema50") or close)
    rsi = float(indicator_ctx.get("rsi") or 50)
    macd = float(indicator_ctx.get("macd") or 0)
    macd_signal = float(indicator_ctx.get("macd_signal") or 0)
    vwap = float(indicator_ctx.get("vwap") or close)
    atr = float(indicator_ctx.get("atr") or max(close * 0.01, 1))
    adx = float(indicator_ctx.get("adx") or 0)
    vol_ratio = float(indicator_ctx.get("vol_ratio") or 1)
    bb_upper = float(indicator_ctx.get("bb_upper") or close)
    bb_lower = float(indicator_ctx.get("bb_lower") or close)

    def add(
        name: str,
        category: str,
        weight_key: str,
        signed_strength: float,
        reason: str,
        *,
        force_reject: bool = False,
        reject_reason: str = "",
    ) -> None:
        strength = min(1.0, abs(signed_strength))
        direction = _dir_from_sign(signed_strength)
        w = float(weights.get(weight_key, 1.0))
        # Regime rejection: mean-reversion tools in strong trends
        accepted = True
        why_reject = reject_reason
        if force_reject:
            accepted = False
        elif weight_key in ("momentum", "bollinger") and regime.regime.startswith("trending") and strength < 0.85:
            # Soft signals against the trend get rejected
            if (regime.regime == "trending_up" and signed_strength < 0) or (
                regime.regime == "trending_down" and signed_strength > 0
            ):
                accepted = False
                why_reject = "Trend is dominant — counter-trend oscillator signal de-emphasized."
        elif weight_key == "trend" and regime.regime == "sideways":
            if strength < 0.7:
                accepted = False
                why_reject = "Market is sideways — weak trend signals are less reliable."

        contribution = (signed_strength * w) if accepted else 0.0
        factors.append(
            EvidenceFactor(
                name=name,
                category=category,
                direction=direction,
                strength=strength,
                weight=w,
                contribution=contribution,
                reason=reason,
                accepted=accepted,
                reject_reason=why_reject,
            )
        )

    # --- Trend / EMA ---
    if ema9 > ema20 > ema50:
        add("EMA stack", "technical", "trend", 0.9, "EMA 9 > 20 > 50 — trend remains bullish.")
    elif ema9 < ema20 < ema50:
        add("EMA stack", "technical", "trend", -0.9, "EMA 9 < 20 < 50 — trend remains bearish.")
    elif ema9 > ema20:
        add("EMA cross", "technical", "trend", 0.45, "EMA 20 crossed / sits above slower average — short-term bullish.")
    else:
        add("EMA cross", "technical", "trend", -0.45, "Short-term averages lean bearish.")

    # --- RSI ---
    if rsi <= 30:
        add("RSI", "technical", "momentum", 0.85, "RSI is oversold — selling pressure may be exhausted.")
    elif rsi >= 70:
        add("RSI", "technical", "momentum", -0.85, "RSI is overbought — rally may be stretched.")
    elif rsi >= 55:
        add("RSI", "technical", "momentum", 0.35, f"RSI at {rsi:.0f} supports mild bullish momentum.")
    elif rsi <= 45:
        add("RSI", "technical", "momentum", -0.35, f"RSI at {rsi:.0f} shows mild bearish momentum.")
    else:
        add(
            "RSI",
            "technical",
            "momentum",
            0.05,
            f"RSI near neutral ({rsi:.0f}).",
            force_reject=True,
            reject_reason="RSI is neutral — not actionable right now.",
        )

    # --- MACD ---
    if macd > macd_signal and macd > 0:
        add("MACD", "technical", "macd", 0.8, "MACD bullish crossover above zero — momentum turning up.")
    elif macd < macd_signal and macd < 0:
        add("MACD", "technical", "macd", -0.8, "MACD bearish crossover below zero — momentum turning down.")
    elif macd > macd_signal:
        add("MACD", "technical", "macd", 0.4, "MACD above signal line — improving momentum.")
    else:
        add("MACD", "technical", "macd", -0.4, "MACD below signal line — weakening momentum.")

    # --- VWAP ---
    dist = (close - vwap) / max(atr, 1e-9)
    if dist > 0.3:
        add("VWAP", "technical", "vwap", 0.55, "Price is above VWAP — buyers control the session.")
    elif dist < -0.3:
        add("VWAP", "technical", "vwap", -0.55, "Price is below VWAP — sellers control the session.")
    else:
        add("VWAP", "technical", "vwap", 0.0, "Price is near VWAP — balanced session.", force_reject=True,
            reject_reason="Too close to VWAP to call a side.")

    # --- Bollinger ---
    if close <= bb_lower:
        add("Bollinger", "technical", "bollinger", 0.6, "Price at lower Bollinger Band — possible bounce zone.")
    elif close >= bb_upper:
        add("Bollinger", "technical", "bollinger", -0.6, "Price at upper Bollinger Band — possible pullback zone.")
    else:
        add("Bollinger", "technical", "bollinger", 0.0, "Price inside Bollinger Band mid-range.",
            force_reject=True, reject_reason="No band extreme — Bollinger not decisive.")

    # --- Volume / breakout ---
    if vol_ratio >= 1.5:
        signed = 0.55 if close >= ema20 else -0.55
        add("Volume surge", "volume", "volume", signed,
            "Volume increased above average — move has real participation.")
    elif vol_ratio <= 0.7:
        add("Volume", "volume", "volume", 0.0, "Volume is below average — conviction is weak.",
            force_reject=True, reject_reason="Low volume weakens breakout/trend confidence.")

    # --- ADX ---
    if adx >= 25:
        signed = 0.4 if ema9 > ema20 else -0.4
        add("ADX", "technical", "adx", signed, f"ADX {adx:.0f} confirms a strong trend.")
    else:
        add("ADX", "technical", "adx", 0.0, f"ADX {adx:.0f} — trend strength is modest.",
            force_reject=True, reject_reason="ADX below threshold — trend not confirmed.")

    # --- Fibonacci ---
    fib = indicator_ctx.get("fibonacci")
    if fib is not None:
        fib_score, fib_reasons = fibonacci_signal_contribution(fib, close)
        if fib_reasons:
            add("Fibonacci", "fibonacci", "fibonacci", max(-1.0, min(1.0, fib_score)),
                fib_reasons[0])
        else:
            add("Fibonacci", "fibonacci", "fibonacci", 0.0, "No key Fibonacci touch right now.",
                force_reject=True, reject_reason="Price not reacting to key Fib levels.")

    # --- Support / Resistance ---
    sr = indicator_ctx.get("support_resistance") or {}
    supports = sr.get("support") or []
    resistances = sr.get("resistance") or []
    if supports and abs(close - float(supports[0])) / max(close, 1) < 0.004:
        add("Support", "structure", "support_resistance", 0.55,
            f"Price is bouncing near support ₹{float(supports[0]):,.2f}.")
    elif resistances and abs(close - float(resistances[0])) / max(close, 1) < 0.004:
        add("Resistance", "structure", "support_resistance", -0.55,
            f"Price is stalling near resistance ₹{float(resistances[0]):,.2f}.")
    else:
        add("S/R", "structure", "support_resistance", 0.0, "Not tightly interacting with nearest S/R.",
            force_reject=True, reject_reason="Support/resistance not the main driver at this tick.")

    # --- Candles ---
    for p in candle_patterns:
        signed = 0.55 if p["direction"] == "bullish" else (-0.55 if p["direction"] == "bearish" else 0.0)
        if p["direction"] == "neutral":
            add(p["name"], "candle", "candlestick", 0.0, p["reason"],
                force_reject=True, reject_reason="Neutral candle — wait for direction.")
        else:
            add(p["name"], "candle", "candlestick", signed * float(p.get("strength", 0.5)), p["reason"])

    # --- Chart patterns ---
    for p in chart_patterns:
        signed = 0.65 if p["direction"] == "bullish" else (-0.65 if p["direction"] == "bearish" else 0.0)
        if p["direction"] == "neutral":
            add(p["name"], "pattern", "chart_pattern", 0.15 * float(p.get("strength", 0.5)),
                p["reason"] + " Direction still undecided.")
        else:
            add(p["name"], "pattern", "chart_pattern", signed * float(p.get("strength", 0.5)), p["reason"])

    # --- News ---
    net = float(news_aggregate.get("net_score") or 0)
    if abs(net) < 0.2:
        add("News", "news", "news", 0.0, news_aggregate.get("summary") or "News is mixed.",
            force_reject=True, reject_reason="News impact too weak to drive the call.")
    else:
        # Cap news contribution
        signed = max(-1.0, min(1.0, net / 2.0))
        top = ""
        if news_items:
            top = f" Top story: {news_items[0].headline[:90]}"
        add("News impact", "news", "news", signed,
            (news_aggregate.get("summary") or "News lean detected.") + top)

    # --- Macro / relative strength ---
    rs = market_ctx.get("relative_strength_vs_nifty_pct")
    if rs is not None:
        if rs > 0.4:
            add("Relative strength", "macro", "relative_strength", 0.4,
                f"Stock is outperforming Nifty (~{rs:+.2f}% recently).")
        elif rs < -0.4:
            add("Relative strength", "macro", "relative_strength", -0.4,
                f"Stock is underperforming Nifty (~{rs:+.2f}% recently).")
        else:
            add("Relative strength", "macro", "relative_strength", 0.0,
                "Moving roughly in line with the index.",
                force_reject=True, reject_reason="No meaningful relative-strength edge.")

    vix = market_ctx.get("india_vix")
    if vix is not None and float(vix) >= 18:
        add("India VIX", "macro", "macro", -0.25,
            f"India VIX elevated ({float(vix):.1f}) — risk of sharp swings.")
    elif vix is not None and float(vix) <= 12:
        add("India VIX", "macro", "macro", 0.15,
            f"India VIX calm ({float(vix):.1f}) — smoother tape.")

    # --- Master strategies Alpha / Beta / Gamma ---
    if strategy_bundle:
        primary_name = strategy_bundle.get("primary_strategy") or "Alpha"
        for key in ("Alpha", "Beta", "Gamma"):
            st = (strategy_bundle.get("strategies") or {}).get(key) or strategy_bundle.get(key.lower())
            if not st:
                continue
            signed = float(st.get("signed_strength") or 0)
            is_primary = key == primary_name
            # Boost primary strategy; Gamma always counts when divergence/active
            boost = 1.25 if is_primary else (1.1 if key == "Gamma" and st.get("active") else 0.85)
            w_key = "trend" if key == "Alpha" else ("bollinger" if key == "Beta" else "news")
            # Temporarily scale weight
            old_w = weights.get(w_key, 1.0)
            weights[w_key] = old_w * boost
            if abs(signed) < 0.05:
                add(
                    f"Strategy {key}",
                    "strategy",
                    w_key,
                    0.0,
                    st.get("rationale") or f"{key} FLAT.",
                    force_reject=True,
                    reject_reason=f"{key} filter inactive for current tape.",
                )
            else:
                add(
                    f"Strategy {key}",
                    "strategy",
                    w_key,
                    signed,
                    st.get("rationale") or f"{key} signal {st.get('prediction')}.",
                )
            weights[w_key] = old_w

    return factors


def decide_from_factors(factors: list[EvidenceFactor]) -> tuple[str, float, float, list[str], list[str]]:
    """
    Aggregate accepted factor contributions into BUY/SELL/HOLD + confidence.

    Returns signal, confidence, score, primary_reasons, rejected_reasons.
    """
    score = sum(f.contribution for f in factors if f.accepted)
    accepted = sorted(
        [f for f in factors if f.accepted and abs(f.contribution) > 0.05],
        key=lambda f: abs(f.contribution),
        reverse=True,
    )
    rejected = [f for f in factors if not f.accepted]

    buy_cut, sell_cut = 1.8, -1.8
    if score >= buy_cut:
        signal = "BUY"
    elif score <= sell_cut:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Confidence from agreement + magnitude
    if accepted:
        dirs = [f.direction for f in accepted if f.direction != "neutral"]
        if dirs:
            majority = max(dirs, key=dirs.count)
            agreement = dirs.count(majority) / len(dirs)
        else:
            agreement = 0.5
    else:
        agreement = 0.4

    magnitude = min(abs(score) / 5.0, 1.0)
    if signal == "HOLD":
        confidence = round(42 + (1 - magnitude) * 22 + agreement * 8, 1)
    else:
        confidence = round(55 + magnitude * 28 + agreement * 12, 1)
        confidence = max(48.0, min(94.0, confidence))

    primary = [f.reason for f in accepted[:7]]
    rejected_txt = []
    for f in rejected[:8]:
        msg = f"{f.name}: {f.reject_reason or 'Not important in current regime.'}"
        rejected_txt.append(msg)

    return signal, confidence, round(score, 3), primary, rejected_txt
