import yfinance as yf
import streamlit as st
import pandas as pd

@st.cache_data(ttl=60)
def get_stock_data(symbol="RELIANCE.NS", period="5d", interval="5m"):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False
        )

        if df.empty:
            st.error("No data found. Check stock symbol.")
            return pd.DataFrame()

        # Remove missing rows
        df.dropna(inplace=True)

        # Clean multi-index columns if any
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df

    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return pd.DataFrame()