"""
Angad — AI Trading Terminal

Professional Streamlit desk with candlestick charts, explainable analysis,
and a Smart Box for BUY / SELL / HOLD. Educational use only — not financial advice.
"""

from __future__ import annotations

from datetime import timedelta
import inspect

import streamlit as st

from auth.session import current_user, history_store_path, logout_user
from db.database import db_path
from db.bootstrap import initialize
from config.loader import load_settings, reload_settings
from config.timeframes import PERIODS, TIMEFRAME_PRESETS, default_interval, intervals_for_period, label_for
from prediction.history_store import PredictionHistoryStore
from services.analysis_service import AnalysisService
from ui.admin_users import render_user_management
from ui.api_status import render_api_management
from ui.auth_pages import render_auth_gate
from ui.chat_panel import render_desk_chat, render_task_composer
from ui.portal_workers import render_workers_portal
from ui.dashboard import (
    collect_indicator_flags,
    merge_auto_indicators,
    render_agent_trace,
    render_ai_explanation_panel,
    render_ai_signal_hero,
    render_accuracy_section,
    render_compare_card,
    render_confidence_meter,
    render_fibonacci_panel,
    render_indicator_snapshot,
    render_main_chart,
    render_market_overview,
    render_news_panel,
    render_performance_strip,
    render_prediction_history,
    render_recent_analysis,
    render_risk_meter,
    render_risk_plan_panel,
    render_scenarios_panel,
    render_sentiment_card,
    render_strategy_master_panel,
    render_volume_analysis,
    render_what_to_do_now,
)
from ui.shell import render_app_chrome
from ui.styles import inject_responsive_css


def _want_compact_chart() -> bool:
    try:
        headers = getattr(st.context, "headers", {}) or {}
        ua = str(headers.get("User-Agent") or headers.get("user-agent") or "").lower()
    except Exception:
        ua = ""
    return any(tok in ua for tok in ("iphone", "ipod", "android")) and "ipad" not in ua

st.set_page_config(
    page_title="Angad AI Trading Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "settings" not in st.session_state:
    st.session_state["settings"] = load_settings()
initialize()
ANALYSIS_SERVICE_VERSION = 2
if (
    "analysis" not in st.session_state
    or st.session_state.get("analysis_version") != ANALYSIS_SERVICE_VERSION
    or "user_id" not in inspect.signature(st.session_state["analysis"].analyze).parameters
):
    st.session_state["analysis"] = AnalysisService(st.session_state["settings"])
    st.session_state["analysis_version"] = ANALYSIS_SERVICE_VERSION

theme_guess = st.session_state.get("chart_theme", "dark")
inject_responsive_css(theme_guess)

user = current_user()
if not user:
    render_auth_gate()
    st.stop()

store_path = history_store_path(int(user["user_id"]))
if st.session_state.get("history_user_id") != user["user_id"]:
    st.session_state["history_store"] = PredictionHistoryStore(store_path)
    st.session_state["history_user_id"] = user["user_id"]
elif "history_store" not in st.session_state:
    st.session_state["history_store"] = PredictionHistoryStore(store_path)

HISTORY = st.session_state["history_store"]
st.session_state["analysis"].history = HISTORY

workspace = render_app_chrome(user)

with st.sidebar:
    st.markdown("### Account")
    st.write(f"**{user['username']}**")
    st.caption(user.get("email") or "")
    if st.button("Logout", type="primary", use_container_width=True, key="logout_sidebar"):
        logout_user()
        st.rerun()
    with st.expander("Change password", expanded=bool(user.get("must_change_password"))):
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
    st.markdown("### Display")
    theme_name = st.selectbox("Chart theme", ["dark", "light"], index=0)
    st.session_state["chart_theme"] = theme_name
    if "mobile_mode" not in st.session_state:
        st.session_state.mobile_mode = _want_compact_chart()
    st.toggle(
        "Phone / compact chart",
        key="mobile_mode",
        help="Shorter chart, larger tap targets, no scroll-zoom hijack. Auto-on for iPhone/Android.",
    )
    if st.button("Reload settings"):
        st.session_state["settings"] = reload_settings()
        st.session_state["analysis"] = AnalysisService(st.session_state["settings"])
        st.session_state["analysis_version"] = ANALYSIS_SERVICE_VERSION
        st.session_state["settings_reloaded"] = True
    st.caption(f"SQLite: `{db_path().name}`")
    st.caption(
        "Educational analysis — not financial advice and not a profit guarantee."
    )
    if st.session_state.get("settings_reloaded"):
        st.success("Settings reloaded")

if user.get("must_change_password"):
    st.warning("You must set a new password before using the desk (admin reset).")
    st.stop()

if workspace in ("APIs", "API Management"):
    render_api_management(user)
    st.stop()
if workspace in ("Users", "User Management"):
    render_user_management(user)
    st.stop()
if workspace in ("Workers", "AI Workers Portal"):
    render_workers_portal(user)
    st.stop()

if theme_name != theme_guess:
    inject_responsive_css(theme_name)

INDEX_PRESETS = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Sensex": "^BSESN",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "Custom": "custom",
}

st.markdown('<div class="desk-toolbar-label">Market filters</div>', unsafe_allow_html=True)
t1, t2, t3, t4, t5 = st.columns([1.35, 1.55, 1.1, 1.0, 1.0])
with t1:
    preset = st.selectbox("Symbol", list(INDEX_PRESETS.keys()), key="desk_symbol_preset")
with t2:
    if preset == "Custom":
        stock = st.text_input("Ticker", "INFY.NS", key="desk_custom_ticker")
    else:
        stock = INDEX_PRESETS[preset]
        st.text_input("Ticker", stock, disabled=True, key="desk_ticker_view")
with t3:
    preset_labels = [row["label"] for row in TIMEFRAME_PRESETS]
    tf_choice = st.selectbox("Timeframe", preset_labels, index=1, key="desk_timeframe")
    tf_row = next(row for row in TIMEFRAME_PRESETS if row["label"] == tf_choice)
with t4:
    auto_refresh = st.toggle("Auto-refresh ~60s", value=True, key="desk_auto_refresh")
with t5:
    include_world = st.toggle("World news", value=True, key="desk_world_news")

use_advanced = st.toggle("Advanced period / interval", value=False, key="desk_advanced_tf")
if use_advanced:
    a1, a2 = st.columns(2)
    with a1:
        period = st.selectbox(
            "Period",
            PERIODS,
            index=PERIODS.index(tf_row["period"]) if tf_row["period"] in PERIODS else 1,
            key="desk_period",
        )
    allowed_iv = intervals_for_period(period)
    default_iv = tf_row["interval"] if tf_row["interval"] in allowed_iv else default_interval(period)
    iv_index = allowed_iv.index(default_iv) if default_iv in allowed_iv else 0
    with a2:
        interval = st.selectbox("Interval", allowed_iv, index=iv_index, key=f"desk_interval_{period}")
else:
    period, interval = tf_row["period"], tf_row["interval"]

with st.expander("Chart indicator filters", expanded=False):
    indicator_flags = collect_indicator_flags(sidebar=False)
    auto_indicators = st.toggle(
        "Auto-select indicators for the current regime",
        value=False,
        key="desk_auto_indicators",
        help="Let the analysis emphasize tools that fit the current market regime.",
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
            user_id=int(user["user_id"]),
        )

    if result.get("error"):
        st.warning(result["error"] + " Try another timeframe (weekends often have no 1-day session).")
        return
    if result.get("fallback_note"):
        st.info(result["fallback_note"])

    from workers.orchestrator import tick_open_tasks

    tick_open_tasks(
        int(user["user_id"]),
        {
            "market": st.session_state["analysis"].market,
            "analysis": st.session_state["analysis"],
            "default_symbol": stock,
        },
    )

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
    news_agg = (primary.raw or {}).get("news_aggregate") or {}
    risk_plan = (primary.raw or {}).get("risk_plan")
    agent_trace = (primary.raw or {}).get("agent_trace")
    chart_flags = merge_auto_indicators(
        indicator_flags, result.get("indicator_flags"), use_auto=auto_indicators
    )
    bars = 0 if df_ist is None else len(df_ist)
    if df_ist is not None and bars:
        t0, t1 = df_ist.index[0], df_ist.index[-1]
        start_txt = t0.strftime("%d %b %Y %H:%M") if hasattr(t0, "strftime") else str(t0)
        end_txt = t1.strftime("%d %b %Y %H:%M") if hasattr(t1, "strftime") else str(t1)
        window_label = (
            f"Date filter: {label_for(period, interval)} · "
            f"{start_txt} → {end_txt} IST · {bars} candles"
        )
    else:
        window_label = f"Date filter: {label_for(period, interval)} · no candles"

    st.markdown("##### Market overview")
    render_market_overview(ms, latest, primary, stock, bars, window_label)

    hero, side = st.columns([1.7, 1.0], gap="medium")
    with hero:
        render_ai_signal_hero(primary, latest, explanation)
        render_what_to_do_now(explanation, primary)
    with side:
        render_sentiment_card(news_agg, news_impacts)
        atr = float(ctx.get("atr") or 0)
        render_risk_meter(primary.risk_level, atr, latest)
        render_risk_plan_panel(risk_plan, primary)

    st.markdown("##### Performance")
    render_performance_strip(HISTORY, stock)

    tab_quick, tab_chart, tab_detail, tab_chat, tab_history, tab_accuracy = st.tabs(
        [
            "Quick view",
            "Trading screen",
            "Detailed analysis",
            "AI Chat & Tasks",
            "Prediction history",
            "Accuracy",
        ]
    )

    with tab_quick:
        q1, q2 = st.columns([1.35, 1.0], gap="medium")
        with q1:
            render_ai_explanation_panel(primary, explanation)
            render_strategy_master_panel(primary)
        with q2:
            render_news_panel(news_impacts, result.get("equity_news"))
            render_recent_analysis(HISTORY, stock)
            render_confidence_meter(primary.confidence, primary.signal)

    with tab_chart:
        st.caption("Candles = traded market. Gold dashed line = guessed path from now, not extra history.")
        chart_id = f"chart_{stock}_{period}_{interval}_{theme_name}_{bars}"
        with st.container(border=True):
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
                interval=interval,
                window_label=window_label,
            )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Predicted price", f"₹{primary.predicted_price:,.2f}")
        m2.metric("Target", f"₹{primary.target_price:,.2f}")
        m3.metric("Stop-loss", f"₹{primary.stop_loss:,.2f}")
        m4.metric("Range", f"₹{primary.price_low:,.2f} – ₹{primary.price_high:,.2f}")

    with tab_detail:
        d1, d2 = st.columns([1.2, 1.0], gap="medium")
        with d1:
            latest_eval = HISTORY.latest_evaluated(stock)
            render_compare_card(primary, latest, latest_eval)
            render_scenarios_panel(scenarios)
            render_agent_trace(agent_trace)
            render_indicator_snapshot(ctx)
            render_volume_analysis(ctx)
            render_fibonacci_panel(fib)
        with d2:
            st.markdown("##### Market trend")
            st.write(f"**{(ctx.get('trend_dir') or primary.trend).title()}** · Regime: `{primary.market_regime}`")
            candle_pats = (primary.raw or {}).get("candle_patterns") or ctx.get("patterns") or []
            chart_pats = (primary.raw or {}).get("chart_patterns") or []
            if candle_pats or chart_pats:
                st.markdown("##### Pattern recognition")
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
            render_news_panel(news_impacts, result.get("equity_news"))

    with tab_chat:
        render_desk_chat(user, result, stock)
        st.divider()
        render_task_composer(user, stock)

    with tab_history:
        st.markdown("#### Prediction history")
        st.caption(
            "Each row stores timestamp, market price, AI signal, confidence, "
            "actual outcome, accuracy, and simulated P/L for this account."
        )
        render_prediction_history(stock, HISTORY)
        from prediction import archive as pred_archive

        sql_rows = pred_archive.list_predictions(int(user["user_id"]), stock, limit=40)
        if sql_rows:
            st.markdown("##### Append-only SQLite archive (TPrediction)")
            st.dataframe(
                [
                    {
                        "When": r["CreatedAt"],
                        "Price": r["MarketPrice"],
                        "Signal": r["Signal"],
                        "Predicted": r["PredictedPrice"],
                        "Range": f"{r['PriceLow']}–{r['PriceHigh']}",
                        "Conf": r["Confidence"],
                        "Regime": r["MarketRegime"],
                        "Actual": r["ActualPrice"],
                    }
                    for r in sql_rows
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab_accuracy:
        st.markdown("#### Accuracy statistics")
        render_accuracy_section(stock, HISTORY, theme_name=theme_name)


render_dashboard()
