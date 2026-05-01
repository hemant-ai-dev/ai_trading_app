import streamlit as st
import plotly.graph_objects as go

from data_fetch import get_stock_data
from indicators import apply_indicators
from signal_engine import get_signal

# -----------------------------------
# Page Config
# -----------------------------------
st.set_page_config(
    page_title="GenAI Trading Tool",
    page_icon="📈",
    layout="wide"
)

# -----------------------------------
# Title
# -----------------------------------
st.title("📈 GenAI Trading Dashboard")
st.caption("AI Powered Stock Analysis Tool")

# -----------------------------------
# Sidebar
# -----------------------------------
st.sidebar.header("⚙ Settings")

stock = st.sidebar.text_input(
    "Enter Stock Symbol",
    "RELIANCE.NS"
)

period = st.sidebar.selectbox(
    "Select Period",
    ["1d", "5d", "1mo", "3mo"],
    index=1
)

interval = st.sidebar.selectbox(
    "Select Interval",
    ["1m", "5m", "15m", "1h", "1d"],
    index=1
)

# -----------------------------------
# Load Data
# -----------------------------------
with st.spinner("Fetching Market Data..."):
    df = get_stock_data(stock, period, interval)

if df.empty:
    st.warning("No Data Available")
    st.stop()

# -----------------------------------
# Apply Indicators
# -----------------------------------
df = apply_indicators(df)

# -----------------------------------
# Get Signal Data
# -----------------------------------
result = get_signal(df)

# -----------------------------------
# Latest Price
# -----------------------------------
latest_price = df["Close"].squeeze().iloc[-1].item()

# -----------------------------------
# Top Metrics
# -----------------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("📌 Stock", stock)
col2.metric("💰 Price", f"₹ {latest_price:.2f}")
col3.metric("📢 Signal", result["signal"])
col4.metric("🎯 Confidence", f'{result["confidence"]}%')

# -----------------------------------
# SL / Target
# -----------------------------------
col5, col6 = st.columns(2)

col5.metric("🛑 Stop Loss", f'₹ {result["stop_loss"]}')
col6.metric("🚀 Target", f'₹ {result["target"]}')

# -----------------------------------
# AI Reason
# -----------------------------------
st.info(f'🤖 Reason: {result["reason"]}')

# -----------------------------------
# Chart
# -----------------------------------
st.subheader("📊 Price Chart")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df.index,
    y=df["Close"],
    name="Close Price",
    line=dict(width=2)
))

fig.add_trace(go.Scatter(
    x=df.index,
    y=df["EMA9"],
    name="EMA9"
))

fig.add_trace(go.Scatter(
    x=df.index,
    y=df["EMA20"],
    name="EMA20"
))

fig.add_trace(go.Scatter(
    x=df.index,
    y=df["VWAP"],
    name="VWAP"
))

fig.update_layout(
    template="plotly_dark",
    height=550,
    xaxis_title="Time",
    yaxis_title="Price"
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------
# Latest Data
# -----------------------------------
st.subheader("📋 Latest Data")

st.dataframe(
    df.tail(10),
    use_container_width=True
)

# -----------------------------------
# Footer
# -----------------------------------
st.caption("Built with Python + Streamlit + GenAI")