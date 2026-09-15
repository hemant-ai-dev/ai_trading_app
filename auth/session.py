"""Central Streamlit session handling for Angad auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from auth.users import UserRecord, get_user_by_id

SESSION_USER_KEY = "auth_user"
SESSION_LOGIN_AT = "auth_login_at"
SESSION_ID_KEY = "auth_session_id"
AUTH_VIEW_KEY = "auth_view"
SESSION_TTL = timedelta(hours=12)

_KEEP_ON_LOGOUT = {"settings"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def set_auth_view(view: str) -> None:
    name = view if view in ("login", "signup", "forgot") else "login"
    st.session_state[AUTH_VIEW_KEY] = name
    st.query_params["auth"] = name


def auth_view() -> str:
    qp = str(st.query_params.get("auth") or "")
    if qp in ("login", "signup", "forgot"):
        st.session_state[AUTH_VIEW_KEY] = qp
        return qp
    return str(st.session_state.get(AUTH_VIEW_KEY) or "login")


def session_expired(login_at_iso: str | None, *, ttl: timedelta = SESSION_TTL) -> bool:
    if not login_at_iso:
        return True
    try:
        started = datetime.fromisoformat(login_at_iso)
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return _now() - started > ttl


def login_user(user: UserRecord) -> None:
    st.session_state[SESSION_USER_KEY] = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
    }
    st.session_state[SESSION_LOGIN_AT] = _now().isoformat()
    st.session_state[SESSION_ID_KEY] = uuid4().hex
    st.session_state["auth_failures"] = 0
    st.session_state[AUTH_VIEW_KEY] = "login"
    if "auth" in st.query_params:
        del st.query_params["auth"]


def logout_user() -> None:
    """Destroy the auth session and user-scoped UI state."""
    for key in list(st.session_state.keys()):
        if key in _KEEP_ON_LOGOUT:
            continue
        del st.session_state[key]
    st.session_state["auth_failures"] = 0
    st.session_state[AUTH_VIEW_KEY] = "login"
    st.query_params.clear()
    st.query_params["auth"] = "login"


def current_user() -> dict[str, Any] | None:
    """Return the logged-in user after expiry and DB revalidation, else None."""
    raw = st.session_state.get(SESSION_USER_KEY)
    if not isinstance(raw, dict) or not raw.get("user_id"):
        return None
    if session_expired(st.session_state.get(SESSION_LOGIN_AT)):
        logout_user()
        return None
    try:
        record = get_user_by_id(int(raw["user_id"]))
    except Exception:
        logout_user()
        return None
    if record is None or not record.is_active:
        logout_user()
        return None
    fresh = {
        "user_id": record.user_id,
        "username": record.username,
        "email": record.email,
        "role": record.role,
        "is_active": record.is_active,
        "must_change_password": record.must_change_password,
    }
    st.session_state[SESSION_USER_KEY] = fresh
    return fresh


def history_store_path(user_id: int) -> Path:
    return Path("data/storage") / f"predictions_u{int(user_id)}.json"
