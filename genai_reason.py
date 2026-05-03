"""Optional LLM narrative on top of rule-based signals. Set OPENAI_API_KEY locally or in Streamlit secrets."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
