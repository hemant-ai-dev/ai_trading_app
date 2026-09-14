"""Input data integrity checks (trading_prompt_master.md §1 & §4)."""

from __future__ import annotations

from typing import Any

import pandas as pd

REQUIRED_OHLCV = ("Open", "High", "Low", "Close", "Volume")


def validate_ohlcv_frame(df: pd.DataFrame | None, *, min_bars: int = 20) -> tuple[bool, str]:
    """
    Validate candle bar schema and basic integrity.

    Accepts Title-case columns used throughout the app (Open/High/Low/Close/Volume).
    Returns (ok, reason).
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return False, "Error: Insufficient or malformed data feed provided."
    missing = [c for c in REQUIRED_OHLCV if c not in df.columns]
    if missing:
        return False, f"Error: Insufficient or malformed data feed provided. Missing: {', '.join(missing)}."
    if len(df) < min_bars:
        return False, "Error: Insufficient or malformed data feed provided."
    # Volume must be present (NaN-heavy volume is treated as bad)
    vol = df["Volume"]
    if vol.isna().mean() > 0.4:
        return False, "Error: Insufficient or malformed data feed provided."
    close = df["Close"]
    if close.isna().mean() > 0.1:
        return False, "Error: Insufficient or malformed data feed provided."
    # Timestamp / index sanity
    if not isinstance(df.index, pd.DatetimeIndex) and "timestamp" not in df.columns and "Datetime" not in df.columns:
        # Yahoo frames usually have DatetimeIndex — allow RangeIndex only if length ok
        if not isinstance(df.index, pd.RangeIndex):
            return False, "Error: Insufficient or malformed data feed provided."
    return True, ""


def validate_sentiment_items(items: list | None) -> list[dict[str, Any]]:
    """Normalize alternative/sentiment records to {timestamp, headline, source}."""
    out: list[dict[str, Any]] = []
    for raw in items or []:
        if isinstance(raw, dict):
            headline = str(raw.get("title") or raw.get("headline") or raw.get("text_content") or "")
            source = str(raw.get("source") or raw.get("publisher") or "news")
            ts = raw.get("timestamp") or raw.get("published") or raw.get("pubDate")
        else:
            headline = str(getattr(raw, "title", "") or getattr(raw, "headline", "") or "")
            source = str(getattr(raw, "source", "news") or "news")
            ts = getattr(raw, "timestamp", None)
        if not headline.strip():
            continue
        out.append({"timestamp": ts, "headline": headline.strip(), "source": source, "text_content": headline.strip()})
    return out
