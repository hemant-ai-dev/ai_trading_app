"""Login layout from the last UI pass, with the current dark purple / neon colors."""

LOGIN_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"] {
    background: #060714 !important;
    color: #ece9ff !important;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(900px 420px at 8% -20%, rgba(124,92,255,0.28), transparent 55%),
        radial-gradient(800px 380px at 100% 0%, rgba(46,230,255,0.10), transparent 48%),
        radial-gradient(700px 500px at 50% 120%, rgba(192,132,252,0.10), transparent 50%),
        #060714 !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
section.main .block-container {
    max-width: 1180px !important;
    padding-top: 1.1rem !important;
    padding-bottom: 1.4rem !important;
}
[data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: 0.7rem !important; }

.auth-stage { padding: 0.15rem 0.1rem 0; }
.auth-kicker {
    font-size: 0.68rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #8b7cff;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.auth-brand {
    font-size: 2.05rem;
    font-weight: 780;
    letter-spacing: -0.04em;
    line-height: 1.12;
    margin: 0 0 0.55rem;
    background: linear-gradient(92deg, #f4f2ff 12%, #9d8cff 52%, #5ce1ff 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent !important;
    -webkit-text-fill-color: transparent;
}
.auth-lead {
    color: #9aa0c7;
    font-size: 0.92rem;
    line-height: 1.5;
    max-width: 38rem;
    margin: 0 0 0.75rem;
}
.auth-flow { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0 0 0.85rem; }
.auth-flow span {
    font-size: 0.72rem;
    padding: 0.22rem 0.62rem;
    border-radius: 999px;
    border: 1px solid rgba(139,124,255,0.22);
    background: rgba(139,124,255,0.12);
    color: #ece9ff;
    font-weight: 600;
}
.model-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.55rem;
}
.model-card {
    background: linear-gradient(180deg, rgba(28,24,68,0.94), rgba(14,16,40,0.94));
    border: 1px solid rgba(139,124,255,0.22);
    border-radius: 14px;
    padding: 0.72rem 0.78rem 0.7rem;
    box-shadow: 0 12px 32px rgba(5,4,20,0.4);
    min-height: 108px;
}
.model-code {
    font-size: 0.62rem;
    letter-spacing: 0.14em;
    color: #7cf0ff;
    font-weight: 700;
    margin-bottom: 0.22rem;
}
.model-card h3 { margin: 0 0 0.2rem; font-size: 0.9rem; color: #ece9ff; }
.model-card p { margin: 0; color: #9aa0c7; font-size: 0.74rem; line-height: 1.35; }

.auth-card-title {
    font-size: 1.35rem;
    font-weight: 750;
    color: #ece9ff;
    margin: 0.15rem 0 0.15rem;
}
.auth-card-hint { color: #9aa0c7; font-size: 0.82rem; margin: 0 0 0.55rem; }
.auth-login-shift {
    height: 2.6rem;
}
div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
    gap: 0.55rem !important;
}
.captcha-wrap {
    display: flex;
    justify-content: center;
    margin: 0.15rem 0 0.1rem;
}
.captcha-wrap svg {
    max-width: 100%;
    height: 52px !important;
    width: auto !important;
}

div[data-testid="stForm"] {
    background: linear-gradient(180deg, rgba(28,24,68,0.96), rgba(14,16,40,0.96)) !important;
    border: 1px solid rgba(139,124,255,0.22) !important;
    border-radius: 18px !important;
    padding: 0.85rem 1rem 1rem !important;
    box-shadow: 0 18px 50px rgba(5,4,20,0.45) !important;
}
.stTextInput label { color: #c9c6ff !important; font-weight: 600 !important; }
.stTextInput input {
    background: rgba(8,10,28,0.65) !important;
    color: #ece9ff !important;
    border: 1px solid rgba(139,124,255,0.22) !important;
    border-radius: 12px !important;
}
.stTextInput input::placeholder { color: #6b7194 !important; }

button[kind="primary"], [data-testid="baseButton-primary"] {
    background: linear-gradient(90deg, #ff5d7a, #ff7a4d) !important;
    color: #fff !important;
    border: 0 !important;
    border-radius: 12px !important;
    min-height: 44px !important;
    font-weight: 700 !important;
    box-shadow: 0 10px 22px rgba(255, 93, 122, 0.22) !important;
}
[data-testid="baseButton-secondary"] {
    background: rgba(12,14,40,0.92) !important;
    color: #ece9ff !important;
    border: 1px solid rgba(139,124,255,0.22) !important;
    border-radius: 12px !important;
    min-height: 42px !important;
    font-weight: 600 !important;
}

.security-code-chip {
    font-family: ui-monospace, monospace;
    letter-spacing: 0.16em;
    text-align: center;
    padding: 0.5rem 0.65rem;
    border-radius: 12px;
    border: 1px solid rgba(139,124,255,0.22);
    background: rgba(8,10,28,0.75);
    margin: 0.2rem 0 0.4rem;
    color: #ece9ff;
}
.glass-kicker {
    font-size: 0.68rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #8b7cff;
    font-weight: 700;
    margin-top: 0.35rem;
}
.preview-wrap {
    background: linear-gradient(180deg, rgba(28,24,68,0.55), rgba(14,16,40,0.35));
    border: 1px solid rgba(139,124,255,0.22);
    border-radius: 16px;
    padding: 0.65rem 0.7rem 0.2rem;
    box-shadow: 0 12px 32px rgba(5,4,20,0.35);
}

input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear,
input[type="password"]::-webkit-credentials-auto-fill-button,
input[type="password"]::-webkit-strong-password-auto-fill-button {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
}
div[data-testid="stForm"] [data-testid="stTextInput"] button {
    display: none !important;
}

@media (max-width: 980px) {
    .auth-brand { font-size: 1.55rem; }
    .model-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .auth-login-shift { height: 0.4rem; }
}
</style>
"""
