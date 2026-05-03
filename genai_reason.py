"""LLM helpers — backends wired via providers.registry (see config/defaults.json)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def build_indicators_summary(df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    return (
        f"Close={float(last['Close']):.2f}, RSI={float(last['RSI']):.1f}, "
        f"EMA9={float(last['EMA9']):.2f}, EMA20={float(last['EMA20']):.2f}, "
        f"MACD={float(last['MACD']):.4f}, VWAP={float(last['VWAP']):.2f}"
    )


def enrich_with_llm(
    signal: str,
    confidence: int,
    reasons: str,
    indicators_summary: str,
    llm: Any | None,
    settings: dict[str, Any] | None,
    market_context: str | None = None,
) -> str | None:
    if llm is None:
        return None
    sec = (settings or {}).get("llm", {}).get("openai") or {}
    max_tokens = int(sec.get("max_tokens_chat") or 220)
    temperature = float(sec.get("temperature_chat") or 0.4)
    user = (
        f"Rule-based signal: {signal} (confidence score shown as {confidence}%). "
        f"Factors: {reasons}. Latest metrics: {indicators_summary}. "
        + (f" Market session context: {market_context}" if market_context else "")
        + " Summarize what this suggests for intraday context and key risks."
    )
    return llm.chat_text(
        system=(
            "You are a concise market-structure assistant. Respond in 2–4 short sentences. "
            "Do not guarantee outcomes; mention uncertainty and that this is not financial advice."
        ),
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def full_chart_intel_analysis(
    signal: str,
    confidence: int,
    reasons: str,
    indicators_summary: str,
    market_context: str | None,
    buy_sell_block: str,
    headline_indexed_block: str,
    reference_levels_json: str,
    llm: Any | None,
    settings: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Structured intel: cited headlines by ID, detailed strategy mapping, conditional playbook with prices,
    chart_reference_levels for horizontal guides.
    """
    if llm is None:
        return None
    sec = (settings or {}).get("llm", {}).get("openai") or {}
    max_tokens = int(sec.get("max_tokens_json") or 2400)
    temperature = float(sec.get("temperature_json") or 0.35)

    schema_hint = """
Reply with ONLY valid JSON (no markdown fences). Use EXACTLY these top-level keys:

1) "strategy_title": short name you choose that matches the rule signal + TA stack.

2) "strategy_step_by_step": array of strings — each step explains WHAT rule/threshold you are reasoning from (EMA vs EMA, RSI band, MACD sign, VWAP side, ATR stops/targets). Be explicit.

3) "prediction_mapping": string — explain in plain English how to read THIS app's chart layers:
   - Blue solid line = actual closes over the loaded window (updates when auto-refresh runs — nearest thing to \"live trail\" here).
   - Orange dashed = mathematical straight-line projection from session anchor toward the RULE-BASED target from indicators (not a forecast).
   - Purple dotted = same grid but rule-target nudged slightly by bounded sentiment_tilt from headlines/macro tone (still illustrative).

4) "technical_rules_detail": array of strings tying chart behaviour to indicator algebra (reference numbers from indicators_snapshot).

5) "news_items_cited": array of objects {\"headline_id\":\"E1\" or \"W3\",\"why_it_matters\":\"...\"}.
   ONLY cite headline_id values that appear in HEADLINES_INDEXED. If unsure, cite fewer items.

6) "news_macro_interpretation": string — qualitative synthesis; no fabricated facts beyond headlines.

7) "conditional_playbook": object with keys:
   - "disclaimer": must say educational hypothetical scenarios only; not recommendations; derivatives risky.
   - "bullish_path": object keys:
        \"trigger_above_price\" (number, prefer tying to VWAP/last/trigger logic),
        \"if_price_never_reaches_above\" (string — what patience/wait means),
        \"objective_reference_price\" (number — typically align toward rule_target unless justified),
        \"invalidation_reference_price\" (number — align toward rule_stop),
        \"educational_derivatives_note\" (string — explain index/options analogy WITHOUT naming strikes as guaranteed)
   - "bearish_path": object keys:
        \"trigger_below_price\", \"if_price_never_reaches_below\", \"objective_reference_price\",
        \"invalidation_reference_price\", \"educational_derivatives_note\"
   - "neutral_wait_zone": object keys \"lower_bound\", \"upper_bound\" (numbers), \"behaviour\" (string)

Anchor playbook numbers primarily from REFERENCE_LEVELS_JSON (last_close, vwap, atr, rule_stop, rule_target).
Keep numbers realistic vs those anchors (avoid random far-away strikes).

8) "chart_reference_levels": array of objects {\"price\":number,\"label\":string,\"kind\":string}
   Include rule_stop and rule_target labels plus any playbook triggers you emphasize.

9) "sentiment_tilt": number between -1 and +1 for bounded purple overlay math only.

10) "key_risks": string.

11) "limitations": string — include that headlines are incomplete/delayed and overlay is not predictive OHLC.
""".strip()

    user_body = (
        f"RULE_SIGNAL: {signal} (confidence shown {confidence}%)\n"
        f"RULE_REASONS: {reasons}\n"
        f"INDICATORS_SNAPSHOT: {indicators_summary}\n"
        f"SESSION_CALENDAR_CONTEXT: {market_context or 'N/A'}\n"
        f"POSITIONING_CONTEXT:\n{buy_sell_block}\n\n"
        f"REFERENCE_LEVELS_JSON:\n{reference_levels_json}\n\n"
        "HEADLINES_INDEXED (cite using headline_id only):\n"
        f"{headline_indexed_block}\n\n"
        "Remember: no promises; scenarios are educational; derivatives carry gap/event risk."
    )

    data = llm.chat_json(
        system=(
            "You are a disciplined trading-education analyst. Output ONLY JSON per schema. "
            "Never invent headline IDs. Tie playbook prices to REFERENCE_LEVELS_JSON. "
            "Use cautious language — geopolitical/news shocks are nonlinear."
        ),
        user=schema_hint + "\n\n" + user_body,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not data:
        return None
    if "sentiment_tilt" in data:
        try:
            data["sentiment_tilt"] = float(data["sentiment_tilt"])
        except (TypeError, ValueError):
            data["sentiment_tilt"] = 0.0
    return data
