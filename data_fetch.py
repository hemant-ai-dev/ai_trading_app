import streamlit as st
import pandas as pd

from config.loader import load_settings
from providers.registry import build_market_data_provider

# Yahoo Finance period limits per interval (approximate)
_INTERVAL_PERIOD_HINTS = {
    "1m": ("1d", "5d", "7d"),
    "2m": ("1d", "5d", "7d"),
    "5m": ("1d", "5d", "1mo"),
    "15m": ("5d", "1mo", "3mo"),
    "30m": ("5d", "1mo", "3mo"),
    "1h": ("1mo", "3mo", "6mo"),
    "1d": ("1mo", "3mo", "6mo", "1y", "2y", "5y"),
}


def _cache_ttl_seconds(interval: str) -> int:
    try:
        s = load_settings()
        base = int(s.get("market_data", {}).get("yfinance", {}).get("cache_ttl_seconds", 45))
    except Exception:
        base = 45
    if interval in ("1m", "2m"):
        return min(base, 20)
    if interval == "5m":
        return min(base, 30)
    return base


def normalize_period_interval(period: str, interval: str) -> tuple[str, str]:
    """Avoid invalid yfinance combos that return empty frames."""
    allowed = _INTERVAL_PERIOD_HINTS.get(interval)
    if allowed and period not in allowed:
        return allowed[0], interval
    return period, interval


@st.cache_data(ttl=30, show_spinner=False)
def _download_stock(symbol: str, period: str, interval: str) -> pd.DataFrame:
    period, interval = normalize_period_interval(period, interval)
    provider = build_market_data_provider(load_settings())
    return provider.download(symbol, period, interval)


def get_stock_data(symbol="RELIANCE.NS", period="5d", interval="5m"):
    period, interval = normalize_period_interval(period, interval)
    try:
        df = _download_stock(symbol, period, interval)
        if df.empty:
            st.error(
                f"No data for {symbol} ({period}/{interval}). "
                "Try 5d+5m for indices, or 1d+1m only for last 7 days."
            )
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Data fetch error: {e}")
        return pd.DataFrame()


def today_live_series(df_ist: pd.DataFrame, ms) -> pd.Series:
    """Intraday closes for the current IST session (live line)."""
    if df_ist is None or df_ist.empty:
        return pd.Series(dtype=float)
    today = ms.now_ist.date()
    mask = df_ist.index.map(lambda t: t.date()) == today
    today_df = df_ist.loc[mask]
    if today_df.empty:
        return pd.Series(dtype=float)
    return today_df["Close"].copy()
