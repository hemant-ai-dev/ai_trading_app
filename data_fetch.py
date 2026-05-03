import streamlit as st
import pandas as pd

from config.loader import load_settings
from providers.registry import build_market_data_provider


def _cache_ttl_seconds() -> int:
    try:
        s = load_settings()
        return int(s.get("market_data", {}).get("yfinance", {}).get("cache_ttl_seconds", 45))
    except Exception:
        return 45


_TTL = _cache_ttl_seconds()


@st.cache_data(ttl=_TTL)
def _download_stock(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Pure fetch for caching — implementation comes from config market_data.provider."""
    provider = build_market_data_provider(load_settings())
    return provider.download(symbol, period, interval)


def get_stock_data(symbol="RELIANCE.NS", period="5d", interval="5m"):
    try:
        df = _download_stock(symbol, period, interval)
        if df.empty:
            st.error("No data found. Check symbol, period/interval combo, or try again.")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Data fetch error: {e}")
        return pd.DataFrame()
