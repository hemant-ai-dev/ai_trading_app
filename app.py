"""
Angad — AI Trading Terminal

Educational desk: daily bars, local analysis, BUY / SELL / HOLD.
Not financial advice and not a live broker.
"""

from __future__ import annotations

import inspect

import streamlit as st

from api.serve import start_background_server
from auth.session import current_user, history_store_path, logout_user
from config.loader import load_settings, reload_settings
from db.bootstrap import initialize
from db.database import db_path
from prediction.history_store import PredictionHistoryStore
from services.analysis_service import AnalysisService
from ui.admin_users import render_user_management
from ui.ai_chat import render_ai_trading_chat
from ui.api_status import render_api_management
from ui.auth import clear_login_form_state, render_auth_gate
from ui.auth.gate import try_complete_login
from ui.options.portal import render_options_workspace
from ui.portal_workers import render_workers_portal
from ui.shell import render_app_chrome
from ui.strategy.desk import render_strategy_workspace
from ui.styles import hide_stale_login_markup, inject_responsive_css


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

user = current_user()
if not user:
    try_complete_login()
    user = current_user()

auth_slot = st.empty()
if not user:
    inject_responsive_css("dark")
    with auth_slot.container():
        render_auth_gate()
    st.stop()

# Signed in: never keep the login tree in this slot, and drop leftover form keys
# so Streamlit cannot reuse sign-in widgets on the desk.
auth_slot.empty()
clear_login_form_state()
hide_stale_login_markup()
st.session_state.pop("auth_error", None)
try:
    if str(st.query_params.get("auth") or "") in ("login", "signup", "forgot"):
        del st.query_params["auth"]
except Exception:
    pass

initialize()
try:
    from auth.users import ensure_sqlite_user

    ensure_sqlite_user(
        int(user["user_id"]),
        username=str(user.get("username") or ""),
        email=str(user.get("email") or ""),
        role=str(user.get("role") or "User"),
    )
except Exception:
    pass
start_background_server()
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

store_path = history_store_path(int(user["user_id"]))
if st.session_state.get("history_user_id") != user["user_id"]:
    st.session_state["history_store"] = PredictionHistoryStore(store_path)
    st.session_state["history_user_id"] = user["user_id"]
elif "history_store" not in st.session_state:
    st.session_state["history_store"] = PredictionHistoryStore(store_path)

st.session_state["analysis"].history = st.session_state["history_store"]

workspace = render_app_chrome(user)

with st.sidebar:
    st.markdown("### Account")
    st.write(f"**{user['username']}**")
    st.caption(user.get("email") or "")
    if st.button("Logout", type="primary", use_container_width=True, key="logout_sidebar", on_click=logout_user):
        pass
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
    st.caption("Educational analysis — not financial advice and not a profit guarantee.")
    if st.session_state.get("settings_reloaded"):
        st.success("Settings reloaded")

if user.get("must_change_password"):
    st.warning("You must set a new password before using the desk (admin reset).")
    st.stop()

if theme_name != theme_guess:
    inject_responsive_css(theme_name)

if workspace in ("APIs", "API Management"):
    render_api_management(user)
    st.stop()
if workspace in ("AI Chat",):
    render_ai_trading_chat(user)
    st.stop()
if workspace in ("Users", "User Management"):
    render_user_management(user)
    st.stop()
if workspace in ("Options",):
    render_options_workspace(user, theme_name=theme_name)
    st.stop()
if workspace in ("Workers", "AI Workers Portal"):
    render_workers_portal(user)
    st.stop()

render_strategy_workspace(user, theme_name=theme_name)
