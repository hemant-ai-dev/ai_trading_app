"""Optional LLM narrative on top of rule-based signals. Set OPENAI_API_KEY locally or in Streamlit secrets."""

from __future__ import annotations

import json
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
    api_key: str | None,
    market_context: str | None = None,
) -> str | None:
    if not api_key or not api_key.strip():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=api_key.strip())
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise market-structure assistant. Respond in 2–4 short sentences. "
                        "Do not guarantee outcomes; mention uncertainty and that this is not financial advice."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Rule-based signal: {signal} (confidence score shown as {confidence}%). "
                        f"Factors: {reasons}. Latest metrics: {indicators_summary}. "
                        + (
                            f" Market session context: {market_context}"
                            if market_context
                            else ""
                        )
                        + " Summarize what this suggests for intraday context and key risks."
                    ),
                },
            ],
            max_tokens=220,
            temperature=0.4,
        )
        choice = resp.choices[0].message.content
        return choice.strip() if choice else None
    except Exception:
        return None


def full_chart_intel_analysis(
    signal: str,
    confidence: int,
    reasons: str,
    indicators_summary: str,
    market_context: str | None,
    buy_sell_block: str,
    news_block: str,
    api_key: str | None,
) -> dict[str, Any] | None:
    """
    Structured GenAI output: strategies, data used, news interpretation, sentiment_tilt for overlay.
    Returns dict or None on failure / missing key.
    """
    if not api_key or not api_key.strip():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=api_key.strip())
    schema_hint = (
        'Reply with ONLY valid JSON (no markdown fences) with exactly these keys: '
        '"strategy_summary" (string), '
        '"technical_methods" (array of strings — which TA ideas align with the rule-based signal), '
        '"data_sources_used" (array of strings — e.g. Yahoo headlines, RSS, calendar, OHLCV), '
        '"news_macro_interpretation" (string — qualitative links between headlines/geopolitics and risk tone; no certainty), '
        '"how_the_chart_was_built" (string — explain orange rule-based path vs qualitative overlay; state limitations), '
        '"sentiment_tilt" (number from -1 bearish to +1 bullish — small magnitude for scenario line only), '
        '"key_risks" (string), '
        '"limitations" (string — must say overlay is illustrative not a price prediction)."'
    )
    user_body = (
        f"Symbol context / rule signal: {signal}, confidence {confidence}%.\n"
        f"Rule factors: {reasons}\n"
        f"Indicators snapshot: {indicators_summary}\n"
        f"Session/calendar: {market_context or 'N/A'}\n"
        f"Buy/sell detail block:\n{buy_sell_block}\n\n"
        f"Public headlines (may be incomplete or delayed):\n{news_block}\n\n"
        "You cannot predict prices. The app draws a rule-based straight-line path to a technical target; "
        "your sentiment_tilt only nudges an illustrative second path. Never promise returns."
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You assist with qualitative trading education. Output compact JSON only. "
                        "Do not fabricate specific facts not implied by the headlines. "
                        "Emphasize uncertainty, conflicts, and that war/news impacts are complex."
                    ),
                },
                {"role": "user", "content": schema_hint + "\n\n" + user_body},
            ],
            response_format={"type": "json_object"},
            max_tokens=900,
            temperature=0.35,
        )
        raw = resp.choices[0].message.content
        if not raw:
            return None
        data = json.loads(raw)
        if "sentiment_tilt" in data:
            try:
                data["sentiment_tilt"] = float(data["sentiment_tilt"])
            except (TypeError, ValueError):
                data["sentiment_tilt"] = 0.0
        return data
    except Exception:
        return None
