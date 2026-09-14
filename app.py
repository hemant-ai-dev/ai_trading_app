"""
Angad — AI Trading Terminal

Professional Streamlit desk with candlestick charts, explainable analysis,
and a Smart Box for BUY / SELL / HOLD. Educational use only — not financial advice.
"""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from db.database import db_path
from db.bootstrap import initialize
from config.loader import load_settings, reload_settings
from config.timeframes import PERIODS, TIMEFRAME_PRESETS, default_interval, intervals_for_period, label_for
from prediction.history_store import PredictionHistoryStore
from services.analysis_service import AnalysisService
from ui.admin_users import render_user_management
from ui.api_status import render_api_management
from ui.auth_pages import current_user, logout, render_auth_gate
from ui.dashboard import (
    collect_indicator_flags,
    merge_auto_indicators,
    render_agent_trace,
    render_ai_explanation_panel,
    render_accuracy_section,
    render_compare_card,
    render_confidence_meter,
    render_fibonacci_panel,
    render_indicator_snapshot,
    render_main_chart,
    render_news_panel,
    render_prediction_history,
    render_risk_meter,
    render_risk_plan_panel,
    render_scenarios_panel,
    render_smart_box,
    render_strategy_master_panel,
    render_top_bar,
    render_volume_analysis,
    render_what_to_do_now,
)
from ui.styles import inject_responsive_css

st.set_page_config(
    page_title="Angad AI Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "settings" not in st.session_state:
    st.session_state["settings"] = load_settings()
initialize()
if "analysis" not in st.session_state:
    st.session_state["analysis"] = AnalysisService(st.session_state["settings"])
if "history_store" not in st.session_state:
    st.session_state["history_store"] = PredictionHistoryStore()

theme_guess = st.session_state.get("chart_theme", "dark")
inject_responsive_css(theme_guess)

user = current_user()
if not user:
    render_auth_gate()
    st.stop()

HISTORY = st.session_state["history_store"]

# --- Sidebar ---
st.sidebar.markdown(f"**Signed in as** `{user['username']}` · {user.get('role', 'User')}")
nav_opts = ["Trading Desk", "API Management"]
if user.get("role") == "Admin":
    nav_opts.append("User Management")
workspace = st.sidebar.radio("Workspace", nav_opts, index=0)
if st.sidebar.button("Log out", use_container_width=True):
    logout()
    st.rerun()

with st.sidebar.expander("Change password", expanded=bool(user.get("must_change_password"))):
    cur_pw = st.text_input("Current password", type="password", key="cur_pw")
    new_pw = st.text_input("New password", type="password", key="new_pw")
    confirm_pw = st.text_input("Confirm new password", type="password", key="confirm_pw")
    if st.button("Update password"):
        from auth.users import change_password

        if new_pw != confirm_pw:
            st.error("New passwords do not match.")
        else:
            err = change_password(int(user["user_id"]), cur_pw, new_pw)
            if err:
                st.error(err)
            else:
                st.session_state["auth_user"]["must_change_password"] = False
                st.success("Password updated.")

st.sidebar.caption(f"SQLite: `{db_path().name}`")

if user.get("must_change_password"):
    st.warning("You must set a new password before using the desk (admin reset).")
    st.stop()

if workspace == "API Management":
    render_api_management(user)
    st.stop()
if workspace == "User Management":
    render_user_management(user)
    st.stop()

st.sidebar.markdown("## Controls")
if st.sidebar.button("Reload settings"):
    st.session_state["settings"] = reload_settings()
    st.session_state["analysis"] = AnalysisService(st.session_state["settings"])
    st.session_state["settings_reloaded"] = True

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

preset_labels = [row["label"] for row in TIMEFRAME_PRESETS]
tf_choice = st.sidebar.selectbox("Chart timeframe", preset_labels, index=1)
tf_row = next(row for row in TIMEFRAME_PRESETS if row["label"] == tf_choice)

use_advanced = st.sidebar.toggle("Advanced period / interval", value=False)
if use_advanced:
    period = st.sidebar.selectbox("Period", PERIODS, index=PERIODS.index(tf_row["period"]) if tf_row["period"] in PERIODS else 1)
    allowed_iv = intervals_for_period(period)
    default_iv = tf_row["interval"] if tf_row["interval"] in allowed_iv else default_interval(period)
    iv_index = allowed_iv.index(default_iv) if default_iv in allowed_iv else 0
    interval = st.sidebar.selectbox("Interval", allowed_iv, index=iv_index, key=f"interval_{period}")
else:
    period, interval = tf_row["period"], tf_row["interval"]

st.sidebar.caption(f"Loading **{label_for(period, interval)}** ({period} / {interval})")

auto_refresh = st.sidebar.toggle("Auto-refresh ~60s", value=True)
include_world = st.sidebar.toggle("World news", value=True)
theme_name = st.sidebar.selectbox("Chart theme", ["dark", "light"], index=0)
st.session_state["chart_theme"] = theme_name
st.session_state.mobile_mode = st.sidebar.toggle(
    "iPhone / compact chart",
    value=False,
    help="Shorter chart and no scroll-zoom hijack — turn on for phones.",
)

if theme_name != theme_guess:
    inject_responsive_css(theme_name)

indicator_flags = collect_indicator_flags(sidebar=True)
auto_indicators = st.sidebar.toggle(
    "Auto-select indicators (regime)",
    value=True,
    help="Let the Technical Analysis Agent emphasize tools that fit the current market regime.",
)

st.sidebar.divider()
st.sidebar.caption(
    "SQLite file database (trading_tool.db). Hosts with ephemeral disks "
    "will lose this file on redeploy unless you attach persistent storage. "
    "Educational analysis — not financial advice and not a profit guarantee."
)
if st.session_state.get("settings_reloaded"):
    st.sidebar.success("Settings reloaded")

st.markdown('<div class="terminal-title">Angad — AI Trading Desk</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="terminal-sub">Smart Box for a quick read · charts, news, and indicators when you want depth</div>',
    unsafe_allow_html=True,
)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_dashboard() -> None:
    with st.spinner("Fetching live market data and running analysis…"):
        result = st.session_state["analysis"].analyze(
            symbol=stock,
            period=period,
            interval=interval,
            use_genai=False,
            include_world_news=include_world,
        )

    if result.get("error"):
        st.warning(result["error"] + " Try another timeframe (weekends often have no 1-day session).")
        return
    if result.get("fallback_note"):
        st.info(result["fallback_note"])

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
    scenarios = result.get("scenarios") or []
    news_impacts = result.get("news_impacts") or (primary.raw or {}).get("news_impacts")
    risk_plan = (primary.raw or {}).get("risk_plan")
    agent_trace = (primary.raw or {}).get("agent_trace")
    chart_flags = merge_auto_indicators(
        indicator_flags, result.get("indicator_flags"), use_auto=auto_indicators
    )
    bars = 0 if df_ist is None else len(df_ist)
    st.caption(
        f"{stock} · {label_for(period, interval)} · {bars} candles · "
        "Recommendations use technical indicators, volume, news scoring, and defined strategy filters."
    )

    render_top_bar(ms, latest, primary, stock)
    render_smart_box(primary, latest, theme_name)

    tab_desk, tab_history, tab_accuracy = st.tabs(
        ["Trading Desk", "Prediction History", "Accuracy Statistics"]
    )

    with tab_desk:
        left, right = st.columns([2.55, 1.0], gap="medium")

        with left:
            st.markdown("#### Candlestick Chart")
            chart_id = f"chart_{stock}_{period}_{interval}_{theme_name}"
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
                indicators=chart_flags,
                scenarios=scenarios,
                chart_key=chart_id,
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Predicted Price", f"₹{primary.predicted_price:,.2f}")
            m2.metric("Target", f"₹{primary.target_price:,.2f}")
            m3.metric("Stop Loss", f"₹{primary.stop_loss:,.2f}")
            m4.metric("Range", f"₹{primary.price_low:,.2f} – ₹{primary.price_high:,.2f}")

            latest_eval = HISTORY.latest_evaluated(stock)
            render_compare_card(primary, latest, latest_eval)
            render_scenarios_panel(scenarios)
            render_agent_trace(agent_trace)

        with right:
            render_ai_explanation_panel(primary, explanation)
            render_what_to_do_now(explanation, primary)
            render_confidence_meter(primary.confidence, primary.signal)
            atr = float(ctx.get("atr") or 0)
            render_risk_meter(primary.risk_level, atr, latest)
            render_risk_plan_panel(risk_plan, primary)
            render_strategy_master_panel(primary)
            st.markdown("##### Market Trend")
            st.write(f"**{(ctx.get('trend_dir') or primary.trend).title()}** · Regime: `{primary.market_regime}`")
            render_news_panel(news_impacts, result.get("equity_news"))
            render_indicator_snapshot(ctx)
            render_volume_analysis(ctx)
            render_fibonacci_panel(fib)
            candle_pats = (primary.raw or {}).get("candle_patterns") or ctx.get("patterns") or []
            chart_pats = (primary.raw or {}).get("chart_patterns") or []
            if candle_pats or chart_pats:
                st.markdown("##### Pattern Recognition")
                for p in candle_pats[:6]:
                    if isinstance(p, dict):
                        st.markdown(f"• {p.get('name')} — {p.get('reason', '')}")
                    else:
                        st.markdown(f"• {p}")
                for p in chart_pats[:6]:
                    if isinstance(p, dict):
                        st.markdown(f"• {p.get('name')} — {p.get('reason', '')}")
                    else:
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
