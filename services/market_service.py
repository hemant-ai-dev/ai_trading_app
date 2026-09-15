"""Market data service with caching and Yahoo-safe timeframe handling."""

from __future__ import annotations

import pandas as pd

from config.loader import load_settings
from config.timeframes import FETCH_FALLBACKS, PERIOD_INTERVALS, default_interval, intervals_for_period
from data.cache import APP_CACHE
from data.provider_registry import build_market_data_provider
from utils.logging import get_logger

logger = get_logger(__name__)


class MarketService:
    """Fetch and cache OHLCV market data."""

    def __init__(self, settings: dict | None = None) -> None:
        self.settings = settings or load_settings()
        self._provider = build_market_data_provider(self.settings)

    @staticmethod
    def normalize_period_interval(period: str, interval: str) -> tuple[str, str]:
        """Keep the user's period when possible; swap interval if Yahoo cannot serve it."""
        period = (period or "5d").strip()
        interval = (interval or "5m").strip()
        allowed = PERIOD_INTERVALS.get(period)
        if allowed and interval not in allowed:
            interval = default_interval(period)
        if period not in PERIOD_INTERVALS:
            # Unknown period: keep interval if we know it, else 5m / 5d
            if interval in intervals_for_period("5d"):
                period = "5d"
            else:
                period, interval = "1mo", "1d"
        return period, interval

    def _cache_ttl(self, interval: str) -> int:
        base = int(self.settings.get("market_data", {}).get("yfinance", {}).get("cache_ttl_seconds", 45))
        if interval in ("1m", "2m"):
            return min(base, 20)
        if interval == "5m":
            return min(base, 30)
        return base

    def get_ohlcv(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "5m",
        *,
        clip_to_session: bool | None = None,
    ) -> pd.DataFrame:
        requested_period, interval = self.normalize_period_interval(period, interval)
        clip = (
            bool(clip_to_session)
            if clip_to_session is not None
            else (requested_period == "1d" and interval != "1d")
        )
        cache_key = f"ohlcv|{symbol}|{requested_period}|{interval}|clip={int(clip)}"

        def _fetch() -> pd.DataFrame:
            attempts = [(requested_period, interval)] + FETCH_FALLBACKS.get(
                (requested_period, interval), []
            )
            df = pd.DataFrame()
            used_period, used_interval = requested_period, interval
            for p, iv in attempts:
                try:
                    candidate = self._provider.download(symbol, p, iv)
                except Exception as exc:
                    logger.error("Data fetch error for %s (%s/%s): %s", symbol, p, iv, exc)
                    continue
                if candidate is None or candidate.empty:
                    logger.warning("No data for %s (%s/%s)", symbol, p, iv)
                    continue
                df = candidate
                used_period, used_interval = p, iv
                break

            if df.empty:
                from data.stooq_provider import fetch_stooq_daily

                logger.warning("Yahoo Finance empty for %s — trying Stooq daily fallback", symbol)
                fallback = fetch_stooq_daily(symbol, requested_period)
                if fallback is not None and not fallback.empty:
                    df = fallback
                    used_period, used_interval = requested_period, "1d"
                    df.attrs["fallback_api"] = "stooq"
                    df.attrs["unavailable_note"] = (
                        "Yahoo Finance returned no bars. Showing Stooq daily CSV "
                        "(intraday charts are unavailable from this fallback)."
                    )

            if df.empty:
                return df

            df = _ensure_datetime_index(df)
            df = clip_to_requested_window(df, requested_period, interval, force_session=clip)
            df.attrs["resolved_period"] = used_period
            df.attrs["resolved_interval"] = used_interval
            df.attrs["requested_period"] = requested_period
            return df

        return APP_CACHE.get_or_set(cache_key, self._cache_ttl(interval), _fetch)

    def get_analysis_ohlcv(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        """Longer lookback for indicators when the visible chart window is too short."""
        period, interval = self.normalize_period_interval(period, interval)
        lookback = {
            "1m": "5d",
            "2m": "5d",
            "5m": "5d",
            "15m": "1mo",
            "30m": "1mo",
            "1h": "1mo",
            "1d": "1y",
        }.get(interval, "5d")
        return self.get_ohlcv(symbol, lookback, interval, clip_to_session=False)

    def get_latest_price(self, symbol: str) -> float | None:
        return self._provider.get_latest_price(symbol)


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)
    return out.sort_index()


def _slice_last_session(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the last trading session so a 1-day request paints one session, not a week."""
    if df is None or df.empty:
        return df
    last_day = pd.Timestamp(df.index[-1]).date()
    mask = [pd.Timestamp(t).date() == last_day for t in df.index]
    sliced = df.loc[mask]
    return sliced if not sliced.empty else df


_PERIOD_CALENDAR_DAYS = {
    "1d": 1,
    "5d": 8,
    "1mo": 32,
    "3mo": 95,
    "6mo": 190,
    "1y": 370,
}


def clip_to_requested_window(
    df: pd.DataFrame,
    period: str,
    interval: str,
    *,
    force_session: bool | None = None,
) -> pd.DataFrame:
    """Trim extra Yahoo/fallback bars so the chart matches the selected date filter."""
    if df is None or df.empty:
        return df
    attrs = dict(getattr(df, "attrs", {}) or {})
    period = (period or "5d").strip()
    interval = (interval or "5m").strip()
    clip_session = (
        bool(force_session)
        if force_session is not None
        else (period == "1d" and interval != "1d")
    )
    if clip_session:
        out = _slice_last_session(df)
        out.attrs.update(attrs)
        return out
    if period == "5d":
        uniq = sorted({pd.Timestamp(t).date() for t in df.index})
        keep = set(uniq[-5:])
        out = df.loc[[pd.Timestamp(t).date() in keep for t in df.index]]
        if out.empty:
            out = df
        out.attrs.update(attrs)
        return out
    days = _PERIOD_CALENDAR_DAYS.get(period)
    if not days:
        df.attrs.update(attrs)
        return df
    last = pd.Timestamp(df.index[-1])
    cutoff = last - pd.Timedelta(days=int(days))
    out = df.loc[df.index >= cutoff]
    if out.empty:
        out = df
    out.attrs.update(attrs)
    return out
