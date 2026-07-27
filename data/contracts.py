"""Data provider contracts."""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    """Interface for live and historical market data."""

    def download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Return OHLCV DataFrame indexed by datetime."""
        ...

    def get_latest_price(self, symbol: str) -> float | None:
        """Return the latest traded price, if available."""
        ...
