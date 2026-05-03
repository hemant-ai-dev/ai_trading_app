import yfinance as yf
import streamlit as st
import pandas as pd


@st.cache_data(ttl=45)
def _download_stock(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Pure fetch for caching — avoid Streamlit UI calls inside cached functions."""
    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        progress=False,
    )

    if df.empty:
        return pd.DataFrame()

    df = df.dropna()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df


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
