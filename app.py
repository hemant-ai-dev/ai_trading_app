"""
Angad — AI Trading Terminal

Professional Streamlit desk with Kite-style candlestick charts,
explainable AI predictions, technical indicators, and accuracy tracking.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from config.loader import load_settings, reload_settings
from prediction.history_store import PredictionHistoryStore
from services.analysis_service import AnalysisService
from ui.dashboard import (
    collect_indicator_flags,
    render_ai_explanation_panel,
    render_accuracy_section,
    render_compare_card,
    render_confidence_meter,
    render_fibonacci_panel,
    render_indicator_snapshot,
    render_main_chart,
    render_prediction_history,
    render_risk_meter,
    render_top_bar,
    render_volume_analysis,
)
from ui.styles import inject_responsive_css
from ai.registry import resolve_openai_api_key

SETTINGS = load_settings()
ANALYSIS = AnalysisService(SETTINGS)
HISTORY = PredictionHistoryStore()

st.set_page_config(
    page_title="Angad AI Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar controls ---
st.sidebar.markdown("## Controls")
if st.sidebar.button("Reload settings"):
    st.session_state["settings"] = reload_settings()
    st.session_state["analysis"] = AnalysisService(st.session_state["settings"])
    st.session_state["settings_reloaded"] = True

if "settings" not in st.session_state:
    st.session_state["settings"] = SETTINGS
if "analysis" not in st.session_state:
    st.session_state["analysis"] = ANALYSIS

INDEX_PRESETS = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Sensex": "^BSESN",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "Custom": "custom",
}
preset = st.sidebar.selectbox("Symbol", list(INDEX_PRESETS.keys()))
stock = st.sidebar.text_input("Ticker", "INFY.NS") if preset == "Custom" else INDEX_PRESETS[preset]
period = st.sidebar.selectbox("Period", ["1d", "5d", "1mo"], index=1)
interval = st.sidebar.selectbox("Interval", ["1m", "5m", "15m", "1h"], index=1)
auto_refresh = st.sidebar.toggle("Auto-refresh ~60s", value=True)
use_genai = st.sidebar.toggle("Use Gen AI (requires API key)", value=False)
include_world = st.sidebar.toggle("World news", value=True)
theme_name = st.sidebar.selectbox("Chart theme", ["dark", "light"], index=0)
st.session_state.mobile_mode = st.sidebar.toggle("Compact chart", value=False)

inject_responsive_css(theme_name)

api_key = resolve_openai_api_key(st.session_state["settings"])
if use_genai and not api_key:
    st.sidebar.warning("Set OPENAI_API_KEY in config/local.json or environment.")

indicator_flags = collect_indicator_flags(sidebar=True)

st.sidebar.divider()
st.sidebar.caption("Storage: local JSON · Educational use only — not financial advice")
if st.session_state.get("settings_reloaded"):
    st.sidebar.success("Settings reloaded")

st.markdown('<div class="terminal-title">Angad — AI Trading Terminal</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="terminal-sub">Live candles · AI prediction path · Indicators · Explainable signals</div>',
    unsafe_allow_html=True,
)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_dashboard() -> None:
    with st.spinner("Fetching live market data and running AI analysis…"):
        result = st.session_state["analysis"].analyze(
            symbol=stock,
            period=period,
            interval=interval,
            use_genai=use_genai,
            include_world_news=include_world,
        )

    if result.get("error"):
        st.warning(result["error"])
        return

    ms = result["market_status"]
    primary = result["primary"]
    explanation = result["explanation"]
    df_ist = result["df_ist"]
    live_line = result["live_line"]
    projection = result["projection"]
    latest = result["latest_price"]
    today = ms.now_ist.date()
    ctx = primary.indicator_snapshot or {}
    fib = ctx.get("fibonacci")
    sr = ctx.get("support_resistance")

    render_top_bar(ms, latest, primary, stock)

    tab_desk, tab_history, tab_accuracy = st.tabs(
        ["Trading Desk", "Prediction History", "Accuracy Statistics"]
    )

    with tab_desk:
        left, right = st.columns([2.55, 1.0], gap="medium")

        with left:
            st.markdown("#### Candlestick Chart")
            render_main_chart(
                df_ist=df_ist,
                live_line=live_line,
                projection=projection,
                fib=fib,
                sr=sr,
                primary=primary,
                history=HISTORY,
                symbol=stock,
                today=today,
                mobile=st.session_state.get("mobile_mode", False),
                theme_name=theme_name,
                indicators=indicator_flags,
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Predicted Price", f"₹{primary.predicted_price:,.2f}")
            m2.metric("Target", f"₹{primary.target_price:,.2f}")
            m3.metric("Stop Loss", f"₹{primary.stop_loss:,.2f}")
            m4.metric("Range", f"₹{primary.price_low:,.2f} – ₹{primary.price_high:,.2f}")

            latest_eval = HISTORY.latest_evaluated(stock)
            render_compare_card(primary, latest, latest_eval)

        with right:
            render_ai_explanation_panel(primary, explanation)
            render_confidence_meter(primary.confidence, primary.signal)
            atr = float(ctx.get("atr") or 0)
            render_risk_meter(primary.risk_level, atr, latest)
            st.markdown("##### Market Trend")
            st.write(f"**{(ctx.get('trend_dir') or primary.trend).title()}** · Regime: `{primary.market_regime}`")
            render_indicator_snapshot(ctx)
            render_volume_analysis(ctx)
            render_fibonacci_panel(fib)
            if ctx.get("patterns"):
                st.markdown("##### Candlestick Patterns")
                for p in ctx["patterns"]:
                    st.markdown(f"• {p}")

    with tab_history:
        st.markdown("#### Prediction History")
        st.caption(
            "Each row stores timestamp, market price, AI signal, confidence, "
            "actual outcome, accuracy, and simulated P/L."
        )
        render_prediction_history(stock, HISTORY)

    with tab_accuracy:
        st.markdown("#### Accuracy Statistics")
        render_accuracy_section(stock, HISTORY, theme_name=theme_name)


render_dashboard()
