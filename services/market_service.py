"""Market data service with caching."""

from __future__ import annotations

import pandas as pd

from config.loader import load_settings
from data.cache import APP_CACHE
from data.provider_registry import build_market_data_provider
from utils.logging import get_logger

logger = get_logger(__name__)

_INTERVAL_PERIOD_HINTS = {
    "1m": ("1d", "5d", "7d"),
    "2m": ("1d", "5d", "7d"),
    "5m": ("1d", "5d", "1mo"),
    "15m": ("5d", "1mo", "3mo"),
    "30m": ("5d", "1mo", "3mo"),
    "1h": ("1mo", "3mo", "6mo"),
    "1d": ("1mo", "3mo", "6mo", "1y", "2y", "5y"),
}


class MarketService:
    """Fetch and cache OHLCV market data."""

    def __init__(self, settings: dict | None = None) -> None:
        self.settings = settings or load_settings()
        self._provider = build_market_data_provider(self.settings)

    @staticmethod
    def normalize_period_interval(period: str, interval: str) -> tuple[str, str]:
        allowed = _INTERVAL_PERIOD_HINTS.get(interval)
        if allowed and period not in allowed:
            return allowed[0], interval
        return period, interval

    def _cache_ttl(self, interval: str) -> int:
        base = int(self.settings.get("market_data", {}).get("yfinance", {}).get("cache_ttl_seconds", 45))
        if interval in ("1m", "2m"):
            return min(base, 20)
        if interval == "5m":
            return min(base, 30)
        return base

    def get_ohlcv(self, symbol: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
        period, interval = self.normalize_period_interval(period, interval)
        cache_key = f"ohlcv|{symbol}|{period}|{interval}"

        def _fetch() -> pd.DataFrame:
            try:
                df = self._provider.download(symbol, period, interval)
                if df.empty:
                    logger.warning("No data for %s (%s/%s)", symbol, period, interval)
                return df
            except Exception as exc:
                logger.error("Data fetch error for %s: %s", symbol, exc)
                return pd.DataFrame()

        return APP_CACHE.get_or_set(cache_key, self._cache_ttl(interval), _fetch)

    def get_latest_price(self, symbol: str) -> float | None:
        return self._provider.get_latest_price(symbol)
