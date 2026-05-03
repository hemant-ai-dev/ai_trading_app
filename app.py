import hashlib
import os
import time
from datetime import timedelta

import streamlit as st
import plotly.graph_objects as go

from data_fetch import get_stock_data
from genai_reason import (
    build_indicators_summary,
    full_chart_intel_analysis,
)
from indicators import apply_indicators
from intraday_forecast import (
    build_comparison_series,
    ensure_ist_index,
    qualitative_scenario_line,
)
from market_calendar import format_market_context_for_llm, get_market_status
from market_intel import format_intel_for_prompt, gather_intel, news_digest_for_cache
from signal_engine import get_signal


def _openai_key() -> str | None:
    k = os.getenv("OPENAI_API_KEY")
    if k:
        return k
    try:
        return str(st.secrets["OPENAI_API_KEY"])
    except (KeyError, FileNotFoundError, TypeError):
        return None


def _load_intel_cached(symbol: str, include_world_rss: bool, ttl_sec: float = 600.0):
    """Throttle RSS/Yahoo hits across Streamlit reruns."""
    key = f"intel_v1|{symbol.upper()}|{include_world_rss}"
    entry = st.session_state.get(key)
    now = time.time()
    if entry and (now - entry["ts"]) < ttl_sec:
        return entry["equity"], entry["world"]
    equity, world = gather_intel(symbol.strip(), include_world_rss=include_world_rss)
    st.session_state[key] = {"ts": now, "equity": equity, "world": world}
    return equity, world


def _cached_intel_analysis(cache_key: str, fetch_fn) -> dict | None:
    if st.session_state.get("intel_ai_key") == cache_key and st.session_state.get("intel_ai_val") is not None:
        return st.session_state.intel_ai_val
    data = fetch_fn()
    st.session_state.intel_ai_key = cache_key
    st.session_state.intel_ai_val = data
    return data


st.set_page_config(
    page_title="GenAI Trading Tool — Intraday (India)",
    page_icon="📈",
    layout="wide",
)

st.title("📈 GenAI Intraday Dashboard (NSE)")
st.caption("Rule-based signals + GenAI commentary (news/macro) + comparable projection paths (IST).")
st.warning(
    "Educational prototype — not financial advice. "
    "No model can reliably predict prices from headlines or charts. "
    "The purple line is a qualitative scenario tilt only (bounded math), not a forecast of real OHLC. "
    "Verify holidays on official NSE circulars."
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
include_world_rss = st.sidebar.toggle(
    "Include world RSS headlines (macro/war/geopolitical)",
    value=True,
    help="Fetches public RSS (BBC/NYT world); may add latency.",
)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_board():
    ms = get_market_status()

    st.subheader("🇮🇳 NSE session (XNSE calendar)")
    mcol1, mcol2, mcol3 = st.columns(3)
    mcol1.metric("IST now", ms.now_ist.strftime("%Y-%m-%d %H:%M"))
    mcol2.metric("Calendar phase", ms.phase.value.replace("_", " "))
    mcol3.metric("Next session date", str(ms.next_session_date))
    st.caption(ms.reason)

    with st.spinner("Fetching market data & headlines…"):
        df = get_stock_data(stock, period, interval)
        equity_news, world_news = _load_intel_cached(stock, include_world_rss)

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
    news_prompt = format_intel_for_prompt(equity_news, world_news)
    digest = news_digest_for_cache(equity_news, world_news)
    digest_hash = hashlib.sha256(digest.encode("utf-8")).hexdigest()[:32]

    buy_sell_block = (
        f"Signal {result['signal']} at {result['confidence']}% confidence. "
        f"Reference stop/resistance: ₹{result['stop_loss']}; reference target: ₹{result['target']}. "
        f"Rule factors: {result['reason']}."
    )

    api_key = _openai_key()
    ai_cache_key = (
        f"{stock}|{result['signal']}|{latest_price:.4f}|{ms.phase}|{digest_hash}|{summary[:120]}"
    )

    def _fetch_intel():
        return full_chart_intel_analysis(
            result["signal"],
            result["confidence"],
            result["reason"],
            summary,
            market_ctx,
            buy_sell_block,
            news_prompt,
            api_key,
        )

    intel = _cached_intel_analysis(ai_cache_key, _fetch_intel) if api_key else None

    st.subheader("🧠 GenAI — strategy, inputs & chart rationale")
    if intel:
        tilt = float(intel.get("sentiment_tilt") or 0.0)
        with st.container():
            st.markdown(f"**Summary:** {intel.get('strategy_summary', '—')}")
            tm = intel.get("technical_methods") or []
            ds = intel.get("data_sources_used") or []
            if tm:
                st.markdown("**Technical angles (aligned with rules):** " + "; ".join(tm))
            if ds:
                st.markdown("**Data & feeds used:** " + "; ".join(ds))
            st.markdown(f"**News / macro (qualitative):** {intel.get('news_macro_interpretation', '—')}")
            st.markdown(f"**How paths were built:** {intel.get('how_the_chart_was_built', '—')}")
            st.markdown(f"**Risks:** {intel.get('key_risks', '—')}")
            st.caption(intel.get("limitations", ""))
            st.caption(f"Scenario sentiment tilt (bounded overlay input): **{tilt:.2f}** (−1 bearish … +1 bullish).")
    elif api_key:
        st.caption("GenAI analysis unavailable this run (API error or empty response). Charts still show rule-based paths.")
    else:
        st.caption("Set `OPENAI_API_KEY` for GenAI strategy box, news-aware tilt, and purple scenario path.")

    proj_qual = None
    if intel is not None and len(proj_cmp) > 0:
        proj_qual = qualitative_scenario_line(
            proj_cmp,
            float(result["target"]),
            float(intel.get("sentiment_tilt") or 0.0),
        )

    st.subheader("📊 Live vs projections (compare paths)")
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
            name="Rule projection → target",
            line=dict(color="#f39c12", width=2, dash="dash"),
            connectgaps=False,
        )
    )
    if proj_qual is not None and len(proj_qual) > 0:
        fig.add_trace(
            go.Scatter(
                x=proj_qual.index,
                y=proj_qual.values,
                name="GenAI qualitative scenario (news tilt; illustrative)",
                line=dict(color="#9b59b6", width=2, dash="dot"),
                connectgaps=False,
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=560,
        xaxis_title="Time (IST)",
        yaxis_title="Price (₹)",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(t=80),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📰 Headlines fed into GenAI (truncated in prompt if long)"):
        st.markdown("**Symbol / index (Yahoo Finance)**")
        for n in equity_news[:12]:
            st.markdown(f"- [{n.source}] {n.title}")
        st.markdown("**World RSS**")
        for n in world_news[:12]:
            st.markdown(f"- [{n.source}] {n.title}")

    st.subheader("📉 Context: recent closes + projections")
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=df_ist.index,
            y=df_ist["Close"],
            name="Recent closes (window)",
            line=dict(color="#3498db", width=1),
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=proj_cmp.index,
            y=proj_cmp.values,
            name="Rule projection",
            line=dict(color="#f39c12", width=2, dash="dash"),
        )
    )
    if proj_qual is not None and len(proj_qual) > 0:
        fig2.add_trace(
            go.Scatter(
                x=proj_qual.index,
                y=proj_qual.values,
                name="GenAI scenario (illustrative)",
                line=dict(color="#9b59b6", width=2, dash="dot"),
            )
        )
    fig2.update_layout(template="plotly_dark", height=480, xaxis_title="Time (IST)", yaxis_title="Price")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Indicator snapshot")
    st.dataframe(df.tail(12), use_container_width=True)


render_board()

st.caption(
    "Built with Python + Streamlit — holidays: pandas_market_calendars (XNSE). "
    "Headlines via Yahoo Finance + optional RSS; timing and completeness vary."
)
