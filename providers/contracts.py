"""Protocols for swappable backends (LLM, OHLCV, news)."""

from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    """Historical/intraday OHLCV."""

    def download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        ...


class LLMProvider(Protocol):
    """Chat completion used for JSON intel / optional text."""

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any] | None:
        ...

    def chat_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> str | None:
        ...


class NewsIntelProvider(Protocol):
    """Symbol + macro headline bundles."""

    def gather(self, stock_symbol: str, include_world_rss: bool) -> tuple[list[Any], list[Any]]:
        ...
