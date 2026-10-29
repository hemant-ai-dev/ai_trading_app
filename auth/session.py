"""Central Streamlit session handling for Angad auth."""

from __future__ import annotations

import json
import threading
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
SESSION_TTL = timedelta(minutes=15)
_AUTH_KEYS = (SESSION_USER_KEY, SESSION_LOGIN_AT, SESSION_ID_KEY, "history_store", "history_user_id", "auth_db_check")
_SESS_PATH = Path("data/storage/auth_sessions.json")
_lock = threading.Lock()


def logout_user() -> None:
    sid = str(st.session_state.get(SESSION_ID_KEY) or st.query_params.get("sid") or "")
    if sid:
        _drop_persisted(sid)
    for key in _AUTH_KEYS:
        st.session_state.pop(key, None)
    st.session_state["auth_failures"] = 0
    st.session_state[AUTH_VIEW_KEY] = "login"
    try:
        st.query_params.clear()
        st.query_params["auth"] = "login"
    except Exception:
        pass


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
    payload = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
    }
    sid = uuid4().hex
    started = _now().isoformat()
    st.session_state[SESSION_USER_KEY] = payload
    st.session_state[SESSION_LOGIN_AT] = started
    st.session_state[SESSION_ID_KEY] = sid
    st.session_state["auth_failures"] = 0
    st.session_state[AUTH_VIEW_KEY] = "login"
    st.session_state["auth_db_check"] = _now().timestamp()
    st.session_state.pop("auth_error", None)
    _save_persisted(sid, {"user": payload, "login_at": started})
    try:
        if "auth" in st.query_params:
            del st.query_params["auth"]
        st.query_params["sid"] = sid
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        name = str(key)
        if name.startswith("FormSubmitter:login_form") or name.startswith("FormSubmitter:signup_form"):
            st.session_state.pop(key, None)


def current_user() -> dict[str, Any] | None:
    """Return the logged-in user after expiry check, else None."""
    raw = st.session_state.get(SESSION_USER_KEY)
    login_at = st.session_state.get(SESSION_LOGIN_AT)
    if not isinstance(raw, dict) or not raw.get("user_id"):
        raw, login_at = _hydrate_from_sid()
        if raw:
            st.session_state[SESSION_USER_KEY] = raw
            st.session_state[SESSION_LOGIN_AT] = login_at
    if not isinstance(raw, dict) or not raw.get("user_id"):
        return None
    if session_expired(login_at):
        logout_user()
        return None
    last = float(st.session_state.get("auth_db_check") or 0)
    if _now().timestamp() - last < 45:
        return raw
    try:
        record = get_user_by_id(int(raw["user_id"]))
    except Exception:
        return raw
    st.session_state["auth_db_check"] = _now().timestamp()
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


def _hydrate_from_sid() -> tuple[dict[str, Any] | None, str | None]:
    sid = str(st.session_state.get(SESSION_ID_KEY) or st.query_params.get("sid") or "")
    if not sid:
        return None, None
    row = _read_persisted().get(sid)
    if not isinstance(row, dict):
        return None, None
    login_at = str(row.get("login_at") or "")
    if session_expired(login_at):
        _drop_persisted(sid)
        return None, None
    user = row.get("user")
    if not isinstance(user, dict):
        return None, None
    st.session_state[SESSION_ID_KEY] = sid
    return user, login_at


def _read_persisted() -> dict[str, Any]:
    if not _SESS_PATH.is_file():
        return {}
    try:
        with _lock:
            return json.loads(_SESS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_persisted(sid: str, row: dict[str, Any]) -> None:
    _SESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        data = {}
        if _SESS_PATH.is_file():
            try:
                data = json.loads(_SESS_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        data[sid] = row
        cutoff = _now() - SESSION_TTL
        keep = {}
        for key, val in data.items():
            try:
                started = datetime.fromisoformat(str((val or {}).get("login_at") or ""))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                if started >= cutoff:
                    keep[key] = val
            except ValueError:
                continue
        _SESS_PATH.write_text(json.dumps(keep), encoding="utf-8")


def _drop_persisted(sid: str) -> None:
    with _lock:
        if not _SESS_PATH.is_file():
            return
        try:
            data = json.loads(_SESS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        data.pop(sid, None)
        _SESS_PATH.write_text(json.dumps(data), encoding="utf-8")
