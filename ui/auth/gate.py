"""Login, sign-up, and password-reset screens."""

from __future__ import annotations

import html

import streamlit as st

from auth.captcha import captcha_matches, captcha_svg, generate_captcha_text
from auth.session import auth_view, login_user, logout_user, set_auth_view
from auth.users import authenticate, create_user, init_user_store, request_password_reset
from ui.auth.copy import PORTAL_FLOW, PORTAL_MODELS
from ui.auth.look import LOGIN_CSS
from ui.auth.preview import render_login_preview_charts

_MAX_FAILURES = 8
_LOGIN_SUBMIT = "FormSubmitter:login_form-Enter the desk"
_SIGNUP_SUBMIT = "FormSubmitter:signup_form-Create account"


def current_user():
    from auth.session import current_user as _current_user

    return _current_user()


def logout() -> None:
    logout_user()


def try_complete_login() -> bool:
    """Return True if this run signed the user in (caller should stop; rerun is triggered)."""
    from auth.session import current_user as session_user

    if session_user():
        st.session_state.pop("auth_error", None)
        return False
    submitted = bool(st.session_state.get(_LOGIN_SUBMIT))
    if not submitted:
        for key, val in st.session_state.items():
            if val is True and "login_form" in str(key) and "FormSubmitter" in str(key):
                submitted = True
                break
    if not submitted:
        return False
    ident = str(st.session_state.get("login_ident") or "")
    password = str(st.session_state.get("login_password") or "")
    if not ident.strip() or not password:
        st.session_state["auth_error"] = "Enter both username/email and password."
        return False
    failures = int(st.session_state.get("auth_failures") or 0)
    if failures >= _MAX_FAILURES:
        st.session_state["auth_error"] = "Too many failed attempts. Refresh the page and try again later."
        return False
    entered = str(st.session_state.get("login_security_in") or "")
    expected = str(st.session_state.get("login_security") or "")
    if not captcha_matches(entered, expected):
        _note_failure()
        _refresh_code("login_security")
        st.session_state["auth_error"] = "Security code did not match. A new code is shown."
        return False
    init_user_store()
    user, err = authenticate(ident, password)
    if err or user is None:
        _note_failure()
        _refresh_code("login_security")
        st.session_state["auth_error"] = err or "Invalid username or password."
        return False
    login_user(user)
    _clear_login_form_state()
    st.rerun()
    return True


def clear_login_form_state() -> None:
    """Drop login widget keys so Streamlit cannot redraw the sign-in form on the desk."""
    for key in list(st.session_state.keys()):
        name = str(key)
        if (
            name.startswith("FormSubmitter:login_form")
            or name.startswith("FormSubmitter:signup_form")
            or name.startswith("FormSubmitter:reset_form")
            or name in (
                "login_ident",
                "login_password",
                "login_security_in",
                "login_security",
                "auth_error",
            )
        ):
            st.session_state.pop(key, None)


def _clear_login_form_state() -> None:
    clear_login_form_state()


def _ensure_code(key: str) -> str:
    if key not in st.session_state:
        st.session_state[key] = generate_captcha_text()
    return st.session_state[key]


def _refresh_code(key: str) -> None:
    prev = str(st.session_state.get(key) or "")
    nxt = generate_captcha_text()
    while nxt == prev:
        nxt = generate_captcha_text()
    st.session_state[key] = nxt
    st.session_state.pop("login_security_in", None)


def _lockout() -> bool:
    return int(st.session_state.get("auth_failures") or 0) >= _MAX_FAILURES


def _note_failure() -> None:
    st.session_state["auth_failures"] = int(st.session_state.get("auth_failures") or 0) + 1


def _portal_story_html() -> str:
    chips = "".join(f"<span>{html.escape(step)}</span>" for step in PORTAL_FLOW)
    cards = []
    for item in PORTAL_MODELS:
        cards.append(
            "<article class='model-card'>"
            f"<div class='model-code'>{html.escape(item['code'])}</div>"
            f"<h3>{html.escape(item['name'])}</h3>"
            f"<p>{html.escape(item['blurb'])}</p>"
            "</article>"
        )
    return f"""
<div class="auth-stage">
  <div class="auth-kicker">Angad portal</div>
  <h1 class="auth-brand">See the call. Understand the path.</h1>
  <p class="auth-lead">
    Educational AI desk: daily bars, local analysis, then BUY, SELL, or HOLD you can inspect.
    Not a broker and not a profit promise. Paper workers only. Passwords are hashed.
  </p>
  <div class="auth-flow">{chips}</div>
  <div class="model-grid">{"".join(cards)}</div>
</div>
"""


def render_auth_gate() -> None:
    if current_user():
        return
    init_user_store()
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    view = auth_view()
    left, right = st.columns([1.45, 0.9], gap="large")
    with left:
        st.markdown(_portal_story_html(), unsafe_allow_html=True)
    with right:
        st.markdown('<div class="auth-login-shift" aria-hidden="true"></div>', unsafe_allow_html=True)
        err = st.session_state.pop("auth_error", None)
        if err:
            st.error(err)
        if _lockout():
            st.error("Too many failed attempts. Refresh the page and try again later.")
        elif view == "signup":
            _render_signup()
        elif view == "forgot":
            _render_forgot()
        else:
            _render_login()

    render_login_preview_charts()


def _security_block(session_key: str, input_key: str) -> None:
    code = _ensure_code(session_key)
    st.markdown(
        f'<div class="captcha-wrap">{captcha_svg(code)}</div>',
        unsafe_allow_html=True,
    )
    st.text_input(
        "Security code",
        max_chars=6,
        key=input_key,
        placeholder="Enter security code",
        autocomplete="off",
    )


def _render_login() -> None:
    st.markdown('<div class="auth-card-title">Sign in</div>', unsafe_allow_html=True)
    st.markdown('<p class="auth-card-hint">Use your desk username or email.</p>', unsafe_allow_html=True)
    st.markdown(
        '<p style="position:absolute;left:-10000px;height:0;overflow:hidden;">'
        '<input type="text" name="fakeuser" autocomplete="username"/>'
        '<input type="password" name="fakepass" autocomplete="current-password"/>'
        "</p>",
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=True, border=False):
        st.text_input(
            "Username or email",
            placeholder="trader or you@email.com",
            key="login_ident",
            autocomplete="off",
        )
        st.text_input(
            "Password",
            type="password",
            placeholder="Your password",
            key="login_password",
            autocomplete="new-password",
        )
        _security_block("login_security", "login_security_in")
        st.form_submit_button("Enter the desk", use_container_width=True, type="primary")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create account", use_container_width=True, key="go_signup"):
            set_auth_view("signup")
            st.rerun()
    with c2:
        if st.button("Forgot password?", use_container_width=True, key="go_forgot"):
            set_auth_view("forgot")
            st.rerun()


def _render_signup() -> None:
    st.markdown('<div class="auth-card-title">Create account</div>', unsafe_allow_html=True)
    st.markdown('<p class="auth-card-hint">Stores a hashed row in the local user workbook.</p>', unsafe_allow_html=True)
    with st.form("signup_form", clear_on_submit=False, border=False):
        username = st.text_input("Username", placeholder="3–32 letters, numbers, . _ -", autocomplete="off")
        email = st.text_input("Email", placeholder="you@example.com", autocomplete="off")
        password = st.text_input(
            "Password",
            type="password",
            help="At least 8 characters, with a letter and a number.",
            autocomplete="new-password",
        )
        confirm = st.text_input("Confirm password", type="password", autocomplete="new-password")
        submitted = st.form_submit_button("Create account", use_container_width=True, type="primary")
    if st.button("Back to sign in", use_container_width=True, key="signup_back"):
        set_auth_view("login")
        st.rerun()
    if not submitted:
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    with st.spinner("Creating your account…"):
        user, err = create_user(username, email, password)
    if err or user is None:
        st.error(err or "Could not create account.")
        return
    login_user(user)
    st.rerun()


def _render_forgot() -> None:
    st.markdown('<div class="auth-card-title">Forgot password</div>', unsafe_allow_html=True)
    st.markdown('<p class="auth-card-hint">An administrator issues a one-time temporary password.</p>', unsafe_allow_html=True)
    with st.form("reset_form", clear_on_submit=False, border=False):
        ident = st.text_input("Username or email", key="reset_ident", placeholder="trader or you@email.com", autocomplete="off")
        submitted = st.form_submit_button("Request password reset", use_container_width=True, type="primary")
    if st.button("Back to sign in", use_container_width=True, key="forgot_back"):
        set_auth_view("login")
        st.rerun()
    if not submitted:
        return
    if not ident.strip():
        st.error("Enter your username or email.")
        return
    request_password_reset(ident)
    st.info("If that account exists, an administrator can complete the reset from User Management.")
    st.caption("After an admin reset, sign in with the temporary password and change it.")
