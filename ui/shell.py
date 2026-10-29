"""Logged-in chrome: greeting, workspace nav, logout."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from auth.session import logout_user

IST = ZoneInfo("Asia/Kolkata")


def _greeting(username: str) -> str:
    hour = datetime.now(IST).hour
    if hour < 12:
        hi = "Good morning"
    elif hour < 17:
        hi = "Good afternoon"
    else:
        hi = "Good evening"
    return f"{hi}, {username}"


def render_app_chrome(user: dict) -> str:
    """Compact header. Returns selected workspace name."""
    _legacy = {
        "AI Strategy Portal": "Strategy",
        "AI Workers Portal": "Workers",
        "API Management": "APIs",
        "User Management": "Users",
        "Trading Desk": "Strategy",
    }
    if st.session_state.get("workspace_nav") in _legacy:
        st.session_state["workspace_nav"] = _legacy[st.session_state["workspace_nav"]]

    nav_opts = ["Strategy", "Options", "AI Chat", "Workers", "APIs"]
    if user.get("role") == "Admin":
        nav_opts.append("Users")

    brand, greet, nav, out = st.columns([1.05, 1.7, 3.1, 0.85])
    with brand:
        st.markdown(
            '<div class="brand-mark">ANGAD</div>'
            '<div class="brand-sub">AI trading desk</div>',
            unsafe_allow_html=True,
        )
    with greet:
        st.markdown(
            f'<div class="hello-line">{_greeting(user["username"])}</div>'
            f'<div class="hello-sub">{user.get("role", "User")} · educational only</div>',
            unsafe_allow_html=True,
        )
    with nav:
        workspace = st.radio(
            "Portal",
            nav_opts,
            horizontal=True,
            key="workspace_nav",
            label_visibility="collapsed",
        )
    with out:
        st.button(
            "Logout",
            type="primary",
            use_container_width=True,
            key="logout_header",
            on_click=logout_user,
        )
    return workspace
