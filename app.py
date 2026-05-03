import os

import streamlit as st
import plotly.graph_objects as go

from data_fetch import get_stock_data
from genai_reason import build_indicators_summary, enrich_with_llm
from indicators import apply_indicators
from signal_engine import get_signal


def _openai_key() -> str | None:
    k = os.getenv("OPENAI_API_KEY")
    if k:
        return k
    try:
        return str(st.secrets["OPENAI_API_KEY"])
    except (KeyError, FileNotFoundError, TypeError):
        return None

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
st.warning(
    "Educational prototype only — not financial advice. Markets involve substantial risk."
)

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
latest_price = float(df["Close"].iloc[-1])

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

col5.metric(
    "🛑 Stop / resistance",
    f'₹ {result["stop_loss"]}',
    help="For SELL context this level acts as a stop above price; for BUY, stop below.",
)
col6.metric(
    "🚀 Target",
    f'₹ {result["target"]}',
    help="Profit objective aligned with signal direction where applicable.",
)

# -----------------------------------
# AI Reason
# -----------------------------------
st.info(f'📐 Rule-based factors: {result["reason"]}')

summary = build_indicators_summary(df)
ai_text = enrich_with_llm(
    result["signal"],
    result["confidence"],
    result["reason"],
    summary,
    _openai_key(),
)
if ai_text:
    st.success(f"🤖 GenAI summary: {ai_text}")
else:
    st.caption(
        "Add `OPENAI_API_KEY` (environment or Streamlit Cloud secrets) and `pip install openai` "
        "to enable optional narrative summaries."
    )

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