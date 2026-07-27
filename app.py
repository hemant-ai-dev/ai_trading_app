"""
Angad — AI Trading Assistant
Educational market analysis with explainable predictions.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from ai.explainer import format_reasons_markdown
from ai.llm_openai import NullLLM
from ai.registry import build_llm_provider, resolve_openai_api_key
from charts.accuracy_dashboard import build_accuracy_dashboard
from charts.price_chart import build_trading_chart
from config.loader import load_settings, reload_settings
from level_plan import chart_y_range
from prediction.accuracy import compute_accuracy_metrics
from prediction.history_store import PredictionHistoryStore
from services.analysis_service import AnalysisService
from ui.styles import inject_responsive_css

SETTINGS = load_settings()
ANALYSIS = AnalysisService(SETTINGS)
HISTORY = PredictionHistoryStore()

st.set_page_config(
    page_title="Angad AI Trading Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_responsive_css()

st.title("📈 Angad — AI Trading Assistant")
st.caption("Live market data · Technical analysis · Explainable AI predictions · Educational use only")

# --- Sidebar ---
st.sidebar.header("⚙ Controls")
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
st.session_state.mobile_mode = st.sidebar.toggle("Compact chart", value=False)

api_key = resolve_openai_api_key(st.session_state["settings"])
if use_genai and not api_key:
    st.sidebar.warning("Set OPENAI_API_KEY in config/local.json or environment.")


def _signal_color(sig: str) -> str:
    return {"BUY": "#27ae60", "SELL": "#e74c3c", "HOLD": "#f39c12"}.get(sig, "#95a5a6")


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_dashboard():
    with st.spinner("Analyzing market data…"):
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IST Time", ms.now_ist.strftime("%H:%M"))
    c2.metric("Session", ms.phase.value.replace("_", " ").title())
    c3.metric("Live Price", f"₹{latest:,.2f}")
    c4.metric("Signal", primary.signal)

    tab_prediction, tab_chart, tab_history, tab_accuracy = st.tabs(
        ["🎯 Prediction", "📊 Chart", "📜 History", "📈 Accuracy"]
    )

    with tab_prediction:
        color = _signal_color(primary.signal)
        st.markdown(
            f"""
            <div style="border-left:6px solid {color}; padding:1rem 1.2rem;
            background:linear-gradient(135deg,#1a1a2e,#16213e); border-radius:8px; margin-bottom:1rem;">
            <h2 style="margin:0;color:{color};">{primary.signal}</h2>
            <p style="margin:0.5rem 0 0;font-size:1.1rem;">
            Confidence: <b>{primary.confidence:.0f}%</b> ·
            Risk: <b>{primary.risk_level}</b> ·
            Trend: <b>{primary.trend.title()}</b>
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Predicted Price", f"₹{primary.predicted_price:,.2f}")
        m2.metric("Target", f"₹{primary.target_price:,.2f}")
        m3.metric("Stop Loss", f"₹{primary.stop_loss:,.2f}")
        m4.metric("Price Range", f"₹{primary.price_low:,.2f} – ₹{primary.price_high:,.2f}")

        st.markdown("### Why this prediction?")
        st.markdown(format_reasons_markdown(explanation))

        st.markdown("### Suggested Action")
        st.info(explanation["suggested_action"])

        ctx = primary.indicator_snapshot
        fib = ctx.get("fibonacci")
        if fib:
            st.markdown("### Fibonacci Levels")
            fib_df = pd.DataFrame(
                [{"Level": k, "Price": f"₹{v:,.2f}"} for k, v in fib.retracements.items()]
            )
            st.dataframe(fib_df, use_container_width=True, hide_index=True)

        if ctx.get("patterns"):
            st.markdown("### Candlestick Patterns")
            for p in ctx["patterns"]:
                st.markdown(f"- {p}")

        if primary.source == "GENAI" and primary.raw.get("market_read"):
            st.markdown("### AI Market Read")
            st.markdown(primary.raw["market_read"])

    with tab_chart:
        fib = ctx.get("fibonacci") if ctx else None
        sr = ctx.get("support_resistance") if ctx else None
        hist = HISTORY.load_projection_history(stock, 30)
        fib_levels = list(fib.retracements.values()) if fib else []
        y0, y1 = chart_y_range(df_ist, projection, fib_levels)

        fig = build_trading_chart(
            df_ist=df_ist,
            live_line=live_line,
            current_pred=projection,
            hist_predictions=hist,
            fib=fib,
            support_resistance=sr,
            y0=y0,
            y1=y1,
            today=today,
            mobile=st.session_state.get("mobile_mode", False),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_history:
        history_df = HISTORY.to_dataframe(stock, limit=50)
        if history_df.empty:
            st.info("No predictions saved yet. They will appear here after each refresh.")
        else:
            display = history_df.rename(columns={
                "timestamp": "Time",
                "signal": "Signal",
                "predicted_price": "Predicted",
                "actual_price": "Actual",
                "error_pct": "Error %",
                "confidence": "Confidence",
                "win": "Win",
            })
            st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_accuracy:
        metrics = compute_accuracy_metrics(stock, HISTORY)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accuracy (±1%)", f"{metrics['accuracy_pct']}%")
        c2.metric("Win Rate", f"{metrics['win_rate_pct']}%")
        c3.metric("Avg Error", f"{metrics['avg_error_pct']}%")
        c4.metric("P/L Simulation", f"{metrics['profit_loss_sim_pct']}%")

        if metrics["evaluated"] > 0:
            fig = build_accuracy_dashboard(stock, HISTORY)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Accuracy metrics will appear after predictions are evaluated against actual prices.")


render_dashboard()

with st.sidebar:
    st.divider()
    st.caption("Storage: local JSON · No database required")
    if st.session_state.get("settings_reloaded"):
        st.success("Settings reloaded")
