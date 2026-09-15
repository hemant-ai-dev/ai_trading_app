"""Dedicated login, sign-up, and forgot-password screens."""

from __future__ import annotations

import streamlit as st

from auth.captcha import captcha_matches, captcha_svg, generate_captcha_text
from auth.session import auth_view, login_user, logout_user, set_auth_view
from auth.users import authenticate, create_user, init_user_store, request_password_reset

_MAX_FAILURES = 8


def current_user():
    from auth.session import current_user as _current_user

    return _current_user()


def logout() -> None:
    logout_user()


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


def render_auth_gate() -> None:
    init_user_store()
    st.markdown(
        """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
section.main .block-container {
    max-width: 1080px !important;
    padding-top: 1.6rem !important;
    padding-bottom: 3rem !important;
}
html, body, .stApp { overflow-x: hidden !important; }
@media (max-width: 640px) {
  section.main .block-container { padding-top: 0.8rem !important; }
}
</style>
""",
        unsafe_allow_html=True,
    )
    view = auth_view()
    left, right = st.columns([1.12, 1.0], gap="large")
    with left:
        st.markdown(
            """
<div class="auth-hero">
  <div class="auth-kicker">AI TRADING TERMINAL</div>
  <div class="auth-brand">Angad</div>
  <p class="auth-lead">Open the desk and see the AI signal first — BUY, SELL, or HOLD — with entry, target, stop, confidence, and risk from live market data.</p>
  <div class="auth-pills">
    <span>NIFTY 50</span><span>BANK NIFTY</span><span>SENSEX</span><span>Smart Box</span>
  </div>
  <ul class="auth-points">
    <li>Accounts live in a hashed Excel workbook — not SQL Server and not your PC database.</li>
    <li>Hashed passwords. Sessions expire after 12 hours. Logout stays on the header.</li>
    <li>Educational analysis only — not financial advice and not a profit guarantee.</li>
  </ul>
</div>
""",
            unsafe_allow_html=True,
        )
    with right:
        if _lockout():
            st.error("Too many failed attempts. Refresh the page and try again later.")
            return
        if view == "signup":
            _render_signup()
        elif view == "forgot":
            _render_forgot()
        else:
            _render_login()


def _captcha_block(session_key: str, input_key: str) -> str:
    code = _ensure_captcha(session_key)
    st.markdown(f'<div class="captcha-wrap">{captcha_svg(code)}</div>', unsafe_allow_html=True)
    st.caption("Type the 6-character security code. Letters are case-insensitive.")
    return st.text_input("Security code", max_chars=6, key=input_key, placeholder="ABC123")


def _render_login() -> None:
    st.markdown('<div class="auth-card-title">Sign in</div>', unsafe_allow_html=True)
    st.caption(
        "Use your username or email. Cloud logins are not copied from your PC — "
        "Sign up on this site if you have not created an account here yet."
    )
    show_pw = st.toggle("Show password", value=False, key="login_show_pw")
    with st.form("login_form", clear_on_submit=False):
        ident = st.text_input("Username or email", placeholder="trader or you@email.com")
        password = st.text_input(
            "Password",
            type="default" if show_pw else "password",
            placeholder="Your password",
        )
        captcha = _captcha_block("login_captcha", "login_captcha_in")
        submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")
    if st.button("New security code", key="login_captcha_refresh"):
        _refresh_captcha("login_captcha")
        st.rerun()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Sign up", use_container_width=True, key="go_signup"):
            set_auth_view("signup")
            st.rerun()
    with c2:
        if st.button("Forgot password?", use_container_width=True, key="go_forgot"):
            set_auth_view("forgot")
            st.rerun()
    if not submitted:
        return
    if not ident.strip() or not password:
        st.error("Enter both username/email and password.")
        return
    if not captcha_matches(captcha, st.session_state.get("login_captcha", "")):
        _note_failure()
        _refresh_captcha("login_captcha")
        st.error("Security code did not match. Try the new code.")
        return
    with st.spinner("Signing you in…"):
        user, err = authenticate(ident, password)
    _refresh_captcha("login_captcha")
    if err or user is None:
        _note_failure()
        st.error(err or "Login failed. Check your username and password.")
        return
    login_user(user)
    st.rerun()


def _render_signup() -> None:
    st.markdown('<div class="auth-card-title">Create account</div>', unsafe_allow_html=True)
    st.caption(
        "Creates a hashed row in data/users.xlsx. The first account becomes Admin. "
        "This cloud site does not use a local SQL Server."
    )
    show_pw = st.toggle("Show password", value=False, key="signup_show_pw")
    with st.form("signup_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="3–32 letters, numbers, . _ -")
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input(
            "Password",
            type="default" if show_pw else "password",
            help="At least 8 characters, with a letter and a number.",
        )
        confirm = st.text_input("Confirm password", type="default" if show_pw else "password")
        captcha = _captcha_block("signup_captcha", "signup_captcha_in")
        submitted = st.form_submit_button("Sign up", use_container_width=True, type="primary")
    if st.button("New security code", key="signup_captcha_refresh"):
        _refresh_captcha("signup_captcha")
        st.rerun()
    if st.button("Back to login", use_container_width=True, key="signup_back"):
        set_auth_view("login")
        st.rerun()
    if not submitted:
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    if not captcha_matches(captcha, st.session_state.get("signup_captcha", "")):
        _note_failure()
        _refresh_captcha("signup_captcha")
        st.error("Security code did not match. Try the new code.")
        return
    with st.spinner("Creating your account…"):
        user, err = create_user(username, email, password)
    _refresh_captcha("signup_captcha")
    if err or user is None:
        st.error(err or "Could not create account.")
        return
    login_user(user)
    st.success("Account created. Opening your desk…")
    st.rerun()


def _render_forgot() -> None:
    st.markdown('<div class="auth-card-title">Forgot password</div>', unsafe_allow_html=True)
    st.caption(
        "We never display or recover your current password. Request a reset; "
        "an administrator sets a one-time temporary password in User Management."
    )
    with st.form("reset_form", clear_on_submit=False):
        ident = st.text_input("Username or email", key="reset_ident", placeholder="trader or you@email.com")
        captcha = _captcha_block("reset_captcha", "reset_captcha_in")
        submitted = st.form_submit_button("Request password reset", use_container_width=True, type="primary")
    if st.button("New security code", key="reset_captcha_refresh"):
        _refresh_captcha("reset_captcha")
        st.rerun()
    if st.button("Back to login", use_container_width=True, key="forgot_back"):
        set_auth_view("login")
        st.rerun()
    if not submitted:
        return
    if not ident.strip():
        st.error("Enter your username or email.")
        return
    if not captcha_matches(captcha, st.session_state.get("reset_captcha", "")):
        _refresh_captcha("reset_captcha")
        st.error("Security code did not match. Try the new code.")
        return
    request_password_reset(ident)
    _refresh_captcha("reset_captcha")
    st.info("If that account exists, an administrator can complete the reset from User Management.")
    st.caption("You will never see the old password. After an admin reset, sign in with the temporary password and change it.")
