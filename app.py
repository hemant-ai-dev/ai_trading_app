import os
from datetime import timedelta

import streamlit as st
import plotly.graph_objects as go

from data_fetch import get_stock_data
from genai_reason import build_indicators_summary, enrich_with_llm
from indicators import apply_indicators
from intraday_forecast import build_comparison_series, ensure_ist_index
from market_calendar import format_market_context_for_llm, get_market_status
from signal_engine import get_signal


def _openai_key() -> str | None:
    k = os.getenv("OPENAI_API_KEY")
    if k:
        return k
    try:
        return str(st.secrets["OPENAI_API_KEY"])
    except (KeyError, FileNotFoundError, TypeError):
        return None


def _cached_ai_reply(
    cache_key: str,
    signal: str,
    confidence: int,
    reasons: str,
    summary: str,
    market_ctx: str,
    api_key: str | None,
) -> str | None:
    if not api_key:
        return None
    if st.session_state.get("ai_cache_key") == cache_key and st.session_state.get("ai_cache_val") is not None:
        return st.session_state.ai_cache_val
    text = enrich_with_llm(signal, confidence, reasons, summary, api_key, market_context=market_ctx)
    st.session_state.ai_cache_key = cache_key
    st.session_state.ai_cache_val = text
    return text


st.set_page_config(
    page_title="GenAI Trading Tool — Intraday (India)",
    page_icon="📈",
    layout="wide",
)

st.title("📈 GenAI Intraday Dashboard (NSE)")
st.caption("Rule-based signals + session-aware projection vs live prices (IST).")
st.warning(
    "Educational prototype — not financial advice. Projections are straight-line paths to a rule-based "
    "target, not a forecast of real prices. Verify holidays on official NSE circulars."
)


st.sidebar.header("⚙ Settings")
stock = st.sidebar.text_input("Enter Stock Symbol", "RELIANCE.NS")
period = st.sidebar.selectbox(
    "Select Period",
    ["1d", "5d", "1mo", "3mo"],
    index=1,
    help="Shorter windows refresh faster for intraday.",
)
interval = st.sidebar.selectbox(
    "Select Interval",
    ["1m", "5m", "15m", "1h", "1d"],
    index=1,
)
auto_refresh = st.sidebar.toggle("Auto-refresh ~60s (intraday)", value=True)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_board():
    ms = get_market_status()

    st.subheader("🇮🇳 NSE session (XNSE calendar)")
    mcol1, mcol2, mcol3 = st.columns(3)
    mcol1.metric("IST now", ms.now_ist.strftime("%Y-%m-%d %H:%M"))
    mcol2.metric("Calendar phase", ms.phase.value.replace("_", " "))
    mcol3.metric("Next session date", str(ms.next_session_date))
    st.caption(ms.reason)

    with st.spinner("Fetching market data…"):
        df = get_stock_data(stock, period, interval)

    if df.empty:
        st.warning("No data available.")
        return

    df = apply_indicators(df)
    df_ist = ensure_ist_index(df)

    result = get_signal(df)
    latest_price = float(df["Close"].iloc[-1])

    today = ms.now_ist.date()
    anchor_key = f"nse_anchor_v1|{stock}|{today.isoformat()}"
    today_mask = df_ist.index.map(lambda t: t.date()) == today
    today_slice = df_ist.loc[today_mask]
    session_anchor = None
    if anchor_key not in st.session_state and len(today_slice) > 0:
        st.session_state[anchor_key] = {"anchor_price": float(today_slice["Close"].iloc[0])}
    if anchor_key in st.session_state:
        session_anchor = st.session_state[anchor_key]

    actual_cmp, proj_cmp, cmp_note = build_comparison_series(
        df_ist,
        float(result["target"]),
        ms,
        session_anchor,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📌 Stock", stock)
    col2.metric("💰 Last close (series)", f"₹ {latest_price:.2f}")
    col3.metric("📢 Signal", result["signal"])
    col4.metric("🎯 Confidence", f'{result["confidence"]}%')

    col5, col6 = st.columns(2)
    col5.metric(
        "🛑 Stop / resistance",
        f'₹ {result["stop_loss"]}',
        help="Stop level derived from ATR; validate against your own risk rules.",
    )
    col6.metric("🚀 Rule-based target", f'₹ {result["target"]}')

    st.info(f"📐 Rule-based factors: {result['reason']}")

    summary = build_indicators_summary(df)
    market_ctx = format_market_context_for_llm(ms)
    api_key = _openai_key()
    ai_cache_key = f"{stock}|{result['signal']}|{latest_price:.4f}|{ms.phase}|{summary[:80]}"
    ai_text = _cached_ai_reply(
        ai_cache_key,
        result["signal"],
        result["confidence"],
        result["reason"],
        summary,
        market_ctx,
        api_key,
    )
    if ai_text:
        st.success(f"🤖 GenAI summary: {ai_text}")
    else:
        st.caption(
            "Set `OPENAI_API_KEY` (env or Streamlit secrets) for GenAI session-aware commentary."
        )

    st.subheader("📊 Live vs projection (compare paths)")
    st.caption(cmp_note)

    fig = go.Figure()
    if len(actual_cmp) > 0:
        fig.add_trace(
            go.Scatter(
                x=actual_cmp.index,
                y=actual_cmp.values,
                name="Live / actual (session)",
                line=dict(color="#2ecc71", width=2),
                connectgaps=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=proj_cmp.index,
            y=proj_cmp.values,
            name="Projection → target (rule-based)",
            line=dict(color="#f39c12", width=2, dash="dash"),
            connectgaps=False,
        )
    )
    fig.update_layout(
        template="plotly_dark",
        height=520,
        xaxis_title="Time (IST)",
        yaxis_title="Price (₹)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📉 Context: recent closes + same projection window")
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=df_ist.index,
            y=df_ist["Close"],
            name="Recent closes (all bars in window)",
            line=dict(color="#3498db", width=1),
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=proj_cmp.index,
            y=proj_cmp.values,
            name="Projection window (same as above)",
            line=dict(color="#f39c12", width=2, dash="dash"),
        )
    )
    fig2.update_layout(template="plotly_dark", height=480, xaxis_title="Time (IST)", yaxis_title="Price")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Indicator snapshot")
    st.dataframe(df.tail(12), use_container_width=True)


render_board()

st.caption("Built with Python + Streamlit — NSE holidays via pandas_market_calendars (XNSE).")
