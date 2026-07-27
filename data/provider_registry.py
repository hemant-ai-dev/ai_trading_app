"""Factory for market data providers."""

from __future__ import annotations

from data.contracts import MarketDataProvider
from data.yfinance_provider import YfinanceMarketData


def build_market_data_provider(settings: dict) -> MarketDataProvider:
    name = (settings.get("market_data") or {}).get("provider") or "yfinance"
    if name == "yfinance":
        opts = (settings.get("market_data") or {}).get("yfinance") or {}
        return YfinanceMarketData(opts)
    raise ValueError(f"Unknown market_data.provider: {name}")
