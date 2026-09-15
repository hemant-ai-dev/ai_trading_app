"""Logged-in chrome: greeting, workspace nav, account menu, logout."""

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
    """Always-visible header with Logout. Returns selected workspace name."""
    _legacy = {
        "AI Strategy Portal": "Strategy",
        "AI Workers Portal": "Workers",
        "API Management": "APIs",
        "User Management": "Users",
        "Trading Desk": "Strategy",
    }
    if st.session_state.get("workspace_nav") in _legacy:
        st.session_state["workspace_nav"] = _legacy[st.session_state["workspace_nav"]]

    nav_opts = ["Strategy", "Workers", "APIs"]
    if user.get("role") == "Admin":
        nav_opts.append("Users")

    brand, greet, account = st.columns([1.1, 2.0, 1.5])
    with brand:
        st.markdown(
            '<div class="brand-mark">ANGAD AI</div>'
            '<div class="brand-sub">Two-portal desk</div>',
            unsafe_allow_html=True,
        )
    with greet:
        st.markdown(
            f'<div class="hello-line">{_greeting(user["username"])}</div>'
            f'<div class="hello-sub">{user.get("role", "User")} · educational analysis, not financial advice</div>',
            unsafe_allow_html=True,
        )
    with account:
        b1, b2 = st.columns(2)
        with b1:
            with st.popover("Account"):
                st.caption(user.get("email") or "")
                st.write(f"Signed in as **{user['username']}**")
                st.caption(f"Role: {user.get('role', 'User')}")
                if st.button("Logout", type="primary", use_container_width=True, key="logout_popover"):
                    logout_user()
                    st.rerun()
        with b2:
            if st.button("Logout", type="primary", use_container_width=True, key="logout_header"):
                logout_user()
                st.rerun()

    workspace = st.radio(
        "Portal",
        nav_opts,
        horizontal=True,
        key="workspace_nav",
        help="Strategy = market AI desk. Workers = task control center.",
    )
    return workspace
