"""Login / signup / forgot-password screens with CAPTCHA."""

from __future__ import annotations

import streamlit as st

from auth.captcha import captcha_matches, captcha_svg, generate_captcha_text
from auth.users import UserRecord, authenticate, create_user, init_user_store, request_password_reset

SESSION_USER_KEY = "auth_user"
_MAX_FAILURES = 8


def current_user() -> dict | None:
    return st.session_state.get(SESSION_USER_KEY)


def logout() -> None:
    for key in (SESSION_USER_KEY, "login_captcha", "signup_captcha", "reset_captcha"):
        st.session_state.pop(key, None)
    st.session_state["auth_failures"] = 0


def _ensure_captcha(key: str) -> str:
    if key not in st.session_state:
        st.session_state[key] = generate_captcha_text()
    return st.session_state[key]


def _refresh_captcha(key: str) -> None:
    st.session_state[key] = generate_captcha_text()


def _lockout() -> bool:
    return int(st.session_state.get("auth_failures") or 0) >= _MAX_FAILURES


def _note_failure() -> None:
    st.session_state["auth_failures"] = int(st.session_state.get("auth_failures") or 0) + 1


def _login_ok(user: UserRecord) -> None:
    st.session_state[SESSION_USER_KEY] = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
    }
    st.session_state["auth_failures"] = 0
    for key in ("login_captcha", "signup_captcha", "reset_captcha"):
        _refresh_captcha(key)


def render_auth_gate() -> None:
    init_user_store()
    st.markdown(
        """
        <div class="auth-shell">
          <div class="auth-brand">Angad</div>
          <div class="auth-tag">AI trading desk · educational analysis, not financial advice</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if _lockout():
        st.error("Too many failed attempts. Refresh the page and try again later.")
        return

    tab_login, tab_signup, tab_reset = st.tabs(["Log in", "Sign up", "Forgot password"])
    with tab_login:
        _render_login()
    with tab_signup:
        _render_signup()
    with tab_reset:
        _render_forgot()


def _captcha_block(session_key: str, input_key: str, refresh_key: str) -> tuple[str, bool]:
    code = _ensure_captcha(session_key)
    st.markdown(f'<div class="captcha-wrap">{captcha_svg(code)}</div>', unsafe_allow_html=True)
    value = st.text_input("CAPTCHA (6 characters)", max_chars=6, key=input_key)
    return value, False


def _render_login() -> None:
    st.caption("Sign in with username or email. Passwords are never stored in plain text.")
    with st.form("login_form", clear_on_submit=False):
        ident = st.text_input("Username or email")
        password = st.text_input("Password", type="password")
        captcha, _ = _captcha_block("login_captcha", "login_captcha_in", "login_captcha_refresh")
        submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")
    if st.button("New CAPTCHA", key="login_captcha_refresh"):
        _refresh_captcha("login_captcha")
        st.rerun()
    if not submitted:
        return
    if not captcha_matches(captcha, st.session_state.get("login_captcha", "")):
        _note_failure()
        _refresh_captcha("login_captcha")
        st.error("CAPTCHA did not match. Try the new code.")
        return
    user, err = authenticate(ident, password)
    _refresh_captcha("login_captcha")
    if err or user is None:
        _note_failure()
        st.error(err or "Login failed.")
        return
    _login_ok(user)
    st.rerun()


def _render_signup() -> None:
    st.caption("The first account created on a new database becomes an administrator.")
    with st.form("signup_form", clear_on_submit=False):
        username = st.text_input("Username", help="3–32 characters: letters, numbers, . _ -")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password", help="At least 8 characters, with a letter and a number.")
        confirm = st.text_input("Confirm password", type="password")
        captcha, _ = _captcha_block("signup_captcha", "signup_captcha_in", "signup_captcha_refresh")
        submitted = st.form_submit_button("Sign up", use_container_width=True, type="primary")
    if st.button("New CAPTCHA", key="signup_captcha_refresh"):
        _refresh_captcha("signup_captcha")
        st.rerun()
    if not submitted:
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    if not captcha_matches(captcha, st.session_state.get("signup_captcha", "")):
        _note_failure()
        _refresh_captcha("signup_captcha")
        st.error("CAPTCHA did not match. Try the new code.")
        return
    user, err = create_user(username, email, password)
    _refresh_captcha("signup_captcha")
    if err or user is None:
        st.error(err or "Could not create account.")
        return
    _login_ok(user)
    st.success("Account created. Opening your desk…")
    st.rerun()


def _render_forgot() -> None:
    st.caption(
        "Request a reset. An administrator must set a new temporary password — "
        "the original password cannot be recovered."
    )
    with st.form("reset_form", clear_on_submit=False):
        ident = st.text_input("Username or email", key="reset_ident")
        captcha, _ = _captcha_block("reset_captcha", "reset_captcha_in", "reset_captcha_refresh")
        submitted = st.form_submit_button("Request password reset", use_container_width=True)
    if st.button("New CAPTCHA", key="reset_captcha_refresh"):
        _refresh_captcha("reset_captcha")
        st.rerun()
    if not submitted:
        return
    if not captcha_matches(captcha, st.session_state.get("reset_captcha", "")):
        _refresh_captcha("reset_captcha")
        st.error("CAPTCHA did not match. Try the new code.")
        return
    request_password_reset(ident)
    _refresh_captcha("reset_captcha")
    st.info("If that account exists, an administrator can complete the reset from User Management.")
