"""Trading-terminal CSS for Angad dashboard."""

from __future__ import annotations

import streamlit as st


def hide_stale_login_markup() -> None:
    """Only after sign-in: hide leftover login HTML if Streamlit left it in the tree."""
    st.markdown(
        """
        <style>
        .auth-stage, .auth-brand, .auth-lead, .auth-flow, .model-grid,
        .auth-card-title, .auth-card-hint, .auth-login-shift, .captcha-wrap,
        .auth-kicker, .preview-wrap { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_responsive_css(theme: str = "dark") -> None:
    """Inject terminal-style CSS. theme is 'dark' or 'light'."""
    dark = theme != "light"
    bg = "#060714" if dark else "#f4f6f9"
    panel = "#12142e" if dark else "#ffffff"
    text = "#ece9ff" if dark else "#0f172a"
    muted = "#9aa0c7" if dark else "#64748b"
    border = "rgba(139,124,255,0.22)" if dark else "rgba(15,23,42,0.08)"
    accent = "#8b7cff"

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: radial-gradient(900px 420px at 8% -20%, rgba(124,92,255,0.28), transparent 55%),
                        radial-gradient(800px 380px at 100% 0%, rgba(46,230,255,0.10), transparent 48%),
                        radial-gradient(700px 500px at 50% 120%, rgba(192,132,252,0.10), transparent 50%),
                        {bg} !important;
            color: {text};
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden !important;
            transition: background 0.2s ease;
        }}
        .stApp {{ overflow-x: hidden; }}
        [data-testid="stToolbar"], .stDeployButton, #MainMenu, footer {{
            visibility: hidden !important;
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
            height: 0 !important;
            min-height: 0 !important;
            pointer-events: none !important;
        }}
        .block-container {{
            padding-top: 0.45rem !important;
            padding-bottom: 1.1rem !important;
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
            max-width: 1600px;
        }}
        [data-testid="stMetric"] {{
            background: linear-gradient(180deg, rgba(139,124,255,0.12), rgba(18,20,46,0.9));
            padding: 0.75rem 0.9rem;
            border-radius: 16px;
            border: 1px solid {border};
            box-shadow: 0 10px 28px rgba(8,6,24,0.35);
            overflow: visible !important;
        }}
        [data-testid="stMetricValue"] {{
            overflow: visible !important;
            white-space: nowrap !important;
            text-overflow: clip !important;
            font-size: 0.98rem !important;
            font-variant-numeric: tabular-nums;
        }}
        [data-testid="stMetricLabel"] {{ color: {muted} !important; white-space: normal !important; }}
        div[role="radiogroup"] {{
            gap: 0.35rem !important;
            background: rgba(12,14,40,0.65);
            border: 1px solid {border};
            border-radius: 999px;
            padding: 0.28rem 0.4rem;
        }}
        div[role="radiogroup"] label {{
            background: transparent !important;
            border-radius: 999px !important;
            padding: 0.28rem 0.85rem !important;
        }}
        div[role="radiogroup"] label[data-checked="true"] {{
            background: linear-gradient(90deg, #6d5cff, #3ecbff) !important;
            color: #0b0a18 !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.35rem;
            background: rgba(12,14,40,0.55);
            border-radius: 14px;
            padding: 0.3rem;
            border: 1px solid {border};
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 10px;
            color: {muted};
        }}
        iframe[title="streamlit_plotly"] {{
            background: transparent !important;
        }}
        .glass-card {{
            background: linear-gradient(180deg, rgba(28,24,68,0.92), rgba(14,16,40,0.92));
            border: 1px solid {border};
            border-radius: 18px;
            padding: 0.85rem 0.95rem 0.75rem;
            box-shadow: 0 16px 40px rgba(5,4,20,0.45);
            margin-bottom: 0.75rem;
        }}
        .glass-kicker {{
            font-size: 0.68rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: {muted};
            margin-bottom: 0.35rem;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.55rem;
        }}
        .stat-tile {{
            background: rgba(255,255,255,0.03);
            border: 1px solid {border};
            border-radius: 14px;
            padding: 0.7rem 0.75rem;
        }}
        .stat-tile span {{
            display: block;
            color: {muted};
            font-size: 0.7rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }}
        .stat-tile b {{
            display: block;
            margin-top: 0.2rem;
            font-size: 1.05rem;
            color: {text};
        }}
        .top-nav {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.35rem 0 0.85rem;
        }}
        [data-testid="stMetricLabel"] {{ color: {muted} !important; }}
        [data-testid="stSidebar"] {{
            background: {panel} !important;
        }}
        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] .stSelectbox,
        [data-testid="stSidebar"] .stTextInput {{
            min-height: 2.6rem;
        }}
        .signal-strip {{
            height: 3px;
            border-bottom: 3px solid;
            margin: 0.35rem 0 0.9rem 0;
            border-radius: 2px;
        }}
        .ai-panel {{
            background: {panel};
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.75rem;
            border: 1px solid {border};
        }}
        .ai-panel-title {{
            font-size: 0.72rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: {muted};
            margin-bottom: 0.35rem;
        }}
        .ai-pred {{
            font-size: 1.75rem;
            font-weight: 700;
            line-height: 1.1;
        }}
        .ai-conf {{ margin-top: 0.25rem; color: {text}; }}
        .compare-card {{
            background: {panel};
            border: 1px solid {border};
            border-left-width: 4px;
            border-radius: 12px;
            padding: 0.85rem 1rem;
            line-height: 1.55;
            margin-bottom: 0.75rem;
        }}
        .conf-bar {{
            height: 6px;
            background: {border};
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.25rem;
        }}
        .conf-bar > div {{ height: 100%; border-radius: 4px; }}
        .terminal-title {{
            font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
            font-weight: 650;
            font-size: 1.4rem;
            margin-bottom: 0.1rem;
            color: {text};
        }}
        .terminal-sub {{
            color: {muted};
            font-size: 0.88rem;
            margin-bottom: 0.7rem;
        }}
        .smart-box {{
            border: 1px solid;
            border-left-width: 6px;
            border-radius: 16px;
            padding: 1rem 1.1rem 0.9rem;
            margin: 0.15rem 0 1rem 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        }}
        .smart-kicker {{
            font-size: 0.7rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            opacity: 0.7;
            margin-bottom: 0.2rem;
        }}
        .smart-signal {{
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            line-height: 1.05;
        }}
        .smart-summary {{
            margin: 0.45rem 0 0.85rem;
            line-height: 1.45;
            font-size: 0.95rem;
        }}
        .smart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
            gap: 0.55rem;
        }}
        .smart-grid div {{
            background: rgba(255,255,255,0.04);
            border-radius: 10px;
            padding: 0.55rem 0.65rem;
        }}
        .smart-grid span {{
            display: block;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            opacity: 0.65;
            margin-bottom: 0.15rem;
        }}
        .smart-grid b {{ font-size: 1.02rem; font-weight: 700; }}
        .smart-meta {{
            margin-top: 0.7rem;
            font-size: 0.75rem;
        }}
        .brand-mark {{
            font-weight: 800;
            letter-spacing: 0.18em;
            font-size: 1.05rem;
            background: linear-gradient(90deg, #9d8cff, #5ce1ff);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }}
        .brand-sub {{ color: {muted}; font-size: 0.75rem; }}
        .hello-line {{
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.15;
        }}
        .hello-sub {{ color: {muted}; font-size: 0.8rem; margin-top: 0.15rem; }}
        .signal-hero {{
            background: linear-gradient(180deg, rgba(28,24,68,0.95), rgba(14,16,40,0.92));
            border: 1px solid {border};
            border-left-width: 6px;
            border-radius: 16px;
            padding: 0.7rem 0.85rem 0.65rem;
            margin: 0 0 0.45rem;
            box-shadow: 0 10px 28px rgba(5,4,20,0.35);
        }}
        .kpi-strip {{
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.45rem;
            border-bottom: 3px solid;
            padding-bottom: 0.55rem;
            margin-bottom: 0.45rem;
        }}
        .kpi-strip div {{
            background: linear-gradient(180deg, rgba(28,24,68,0.9), rgba(14,16,40,0.9));
            border: 1px solid {border};
            border-radius: 12px;
            padding: 0.45rem 0.55rem;
        }}
        .kpi-strip span {{
            display: block;
            color: {muted};
            font-size: 0.65rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .kpi-strip b {{
            display: block;
            margin-top: 0.12rem;
            font-size: 0.92rem;
            color: {text};
            font-variant-numeric: tabular-nums;
            overflow-wrap: anywhere;
        }}
        .hero-tiles {{
            display: grid;
            grid-template-columns: repeat(5, minmax(7.2rem, 1fr));
            gap: 0.55rem;
            margin-top: 0.85rem;
        }}
        .hero-tile {{
            background: rgba(255,255,255,0.04);
            border: 1px solid {border};
            border-radius: 12px;
            padding: 0.55rem 0.6rem 0.5rem;
            min-width: 0;
        }}
        .hero-tile span {{
            display: block;
            color: {muted};
            font-size: 0.68rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }}
        .hero-tile b {{
            display: block;
            font-size: 0.98rem;
            font-weight: 700;
            color: {text};
            font-variant-numeric: tabular-nums;
            line-height: 1.3;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}
        .hero-why, .hero-note {{
            color: {muted};
            font-size: 0.8rem;
            line-height: 1.45;
            margin: 0.7rem 0 0;
        }}
        .sentiment-card {{
            text-align: center;
            padding: 0.4rem 0 0.2rem;
        }}
        .sentiment-score {{
            font-size: 2.4rem;
            font-weight: 800;
            line-height: 1;
        }}
        .sentiment-tilt {{
            letter-spacing: 0.12em;
            text-transform: uppercase;
            font-size: 0.78rem;
            font-weight: 700;
            margin: 0.25rem 0 0.45rem;
        }}
        .sentiment-copy {{
            color: {muted};
            font-size: 0.85rem;
            line-height: 1.45;
            text-align: left;
        }}
        .desk-hero {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.45rem;
        }}
        .desk-live-pill {{
            font-size: 0.68rem;
            letter-spacing: 0.14em;
            font-weight: 700;
            color: #0b1220;
            background: linear-gradient(90deg, #26a69a, #3b82f6);
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            white-space: nowrap;
        }}
        .desk-toolbar-label {{
            font-size: 0.72rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: {muted};
            margin: 0.35rem 0 0.15rem;
        }}
        .ticker-wrap {{
            overflow: hidden;
            border: 1px solid {border};
            border-radius: 10px;
            background: {panel};
            margin: 0.2rem 0 0.85rem;
            padding: 0.45rem 0;
        }}
        .ticker-tape {{
            display: inline-block;
            white-space: nowrap;
            color: {muted};
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            animation: ticker 28s linear infinite;
            padding-left: 100%;
        }}
        @keyframes ticker {{
            0% {{ transform: translateX(0); }}
            100% {{ transform: translateX(-100%); }}
        }}
        .auth-stage {{
            padding: 0;
        }}
        .auth-kicker {{
            font-size: 0.65rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: {accent};
            font-weight: 700;
            margin-bottom: 0.2rem;
        }}
        .auth-brand {{
            font-size: 1.72rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            line-height: 1.12;
            margin: 0 0 0.35rem;
            background: linear-gradient(92deg, #f4f2ff 12%, #9d8cff 52%, #5ce1ff 100%);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }}
        .auth-lead {{
            color: {muted};
            font-size: 0.82rem;
            line-height: 1.4;
            max-width: 40rem;
            margin: 0 0 0.45rem;
        }}
        .auth-flow {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            margin: 0 0 0.5rem;
        }}
        .auth-flow span {{
            font-size: 0.65rem;
            letter-spacing: 0.03em;
            padding: 0.18rem 0.5rem;
            border-radius: 999px;
            border: 1px solid {border};
            background: rgba(139,124,255,0.12);
            color: {text};
        }}
        .model-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.4rem;
        }}
        .model-card {{
            background: linear-gradient(180deg, rgba(28,24,68,0.88), rgba(14,16,40,0.88));
            border: 1px solid {border};
            border-radius: 12px;
            padding: 0.45rem 0.5rem 0.42rem;
            min-height: 0;
        }}
        .model-code {{
            font-size: 0.6rem;
            letter-spacing: 0.12em;
            color: #7cf0ff;
            margin-bottom: 0.12rem;
        }}
        .model-card h3 {{
            margin: 0 0 0.12rem;
            font-size: 0.82rem;
            color: {text};
        }}
        .model-card p {{
            margin: 0;
            color: {muted};
            font-size: 0.7rem;
            line-height: 1.3;
        }}
        .auth-foot {{
            margin: 0.45rem 0 0;
            color: {muted};
            font-size: 0.72rem;
        }}
        .auth-card-title {{
            font-size: 1.2rem;
            font-weight: 750;
            margin-bottom: 0.1rem;
        }}
        .auth-tag {{
            color: {muted};
            font-size: 0.78rem;
            line-height: 1.35;
            margin: 0 0 0.4rem;
        }}
        .security-code-chip {{
            font-family: ui-monospace, monospace;
            letter-spacing: 0.18em;
            text-align: center;
            padding: 0.45rem 0.6rem;
            border-radius: 10px;
            border: 1px solid {border};
            background: rgba(8,10,28,0.75);
            margin: 0.25rem 0 0.35rem;
            color: {text};
        }}
        input[type="password"]::-ms-reveal,
        input[type="password"]::-ms-clear {{
            display: none !important;
        }}
        .captcha-wrap {{
            display: flex;
            justify-content: center;
            margin: 0.4rem 0 0.2rem;
        }}
        .captcha-wrap svg {{ max-width: 100%; height: auto; }}
        div[data-testid="stTabs"] button {{
            font-weight: 600;
            min-height: 2.6rem;
        }}
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {{
            font-size: 16px !important;
        }}
        .js-plotly-plot, .plotly, .stPlotlyChart, [data-testid="stPlotlyChart"] {{
            max-width: 100% !important;
            width: 100% !important;
            overflow: hidden !important;
        }}
        [data-testid="stDataFrame"] {{
            overflow-x: auto;
            max-width: 100%;
        }}
        a {{ color: {accent} !important; }}
        .stCheckbox label span {{ color: {text} !important; }}
        [data-testid="stHorizontalBlock"] {{
            flex-wrap: wrap !important;
            row-gap: 0.55rem !important;
        }}
        [data-testid="stHorizontalBlock"] > div {{
            min-width: 0 !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
            flex-wrap: wrap;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        div[data-testid="stRadio"] [role="radiogroup"] {{
            flex-wrap: wrap !important;
            gap: 0.35rem 0.6rem !important;
        }}
        button, [data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {{
            min-height: 44px;
        }}
        [data-testid="stPopover"] button {{ min-height: 44px; }}

        @media (max-width: 1100px) {{
            .block-container {{ max-width: 100%; }}
            .hello-line {{ font-size: 1.15rem; }}
            .hero-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .kpi-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
            .model-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media (min-width: 641px) and (max-width: 1024px) {{
            .block-container {{
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }}
            [data-testid="stHorizontalBlock"] > div {{
                flex: 1 1 calc(50% - 0.5rem) !important;
                min-width: min(100%, 220px) !important;
            }}
            .smart-signal {{ font-size: 1.85rem; }}
        }}
        @media (max-width: 900px) {{
            .block-container {{
                padding: 0.55rem 0.7rem 5.5rem !important;
                max-width: 100%;
            }}
            .terminal-title {{ font-size: 1.15rem; }}
            .smart-signal {{ font-size: 1.7rem; }}
            .ai-pred {{ font-size: 1.35rem; }}
            .hello-line {{ font-size: 1.05rem; }}
            .hello-sub {{ display: none; }}
            .brand-mark {{ font-size: 0.82rem; letter-spacing: 0.1em; }}
            .stat-tile b, .hero-tile b {{
                font-size: 0.92rem;
            }}
            [data-testid="stHorizontalBlock"] {{
                gap: 0.5rem !important;
            }}
            div[data-testid="stTabs"] button {{
                padding: 0.4rem 0.65rem !important;
                min-height: 44px;
            }}
            .modebar {{ transform: scale(0.9); transform-origin: top right; }}
        }}
        @media (max-width: 640px) {{
            [data-testid="stHorizontalBlock"] > div {{
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }}
            .smart-grid {{ grid-template-columns: 1fr 1fr; }}
            .auth-brand {{ font-size: 1.25rem; }}
            .model-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .signal-hero {{ padding: 0.85rem 0.85rem 0.2rem; }}
            .sentiment-score {{ font-size: 2rem; }}
            [data-testid="stSidebar"] {{
                min-width: min(86vw, 320px) !important;
            }}
            div[data-testid="stVerticalBlock"] > div {{
                max-width: 100%;
            }}
        }}
        @media (min-width: 1441px) {{
            .block-container {{ max-width: 1440px; }}
        }}
        @media (orientation: landscape) and (max-height: 500px) {{
            .block-container {{ padding-top: 0.4rem !important; }}
            .hello-line {{ font-size: 1rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            .ticker-tape {{ animation: none; padding-left: 0.6rem; }}
        }}
        .chat-hero {{
            background: linear-gradient(180deg, rgba(28,24,68,0.95), rgba(14,16,40,0.92));
            border: 1px solid {border};
            border-radius: 18px;
            padding: 1.1rem 1.2rem 1rem;
            margin-bottom: 0.85rem;
            box-shadow: 0 16px 40px rgba(5,4,20,0.45);
        }}
        .chat-hero h1 {{
            margin: 0;
            font-size: 1.55rem;
            letter-spacing: -0.03em;
        }}
        .chat-hero p {{
            margin: 0.35rem 0 0;
            color: {muted};
            font-size: 0.92rem;
            line-height: 1.45;
        }}
        .chat-chip-row {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.55rem 0 0.2rem; }}
        div[data-testid="stChatMessage"] {{
            background: {panel};
            border: 1px solid {border};
            border-radius: 16px;
            padding: 0.15rem 0.35rem;
            margin-bottom: 0.55rem;
        }}
        [data-testid="stChatInput"] {{
            border: 1px solid rgba(59,130,246,0.45) !important;
            border-radius: 16px !important;
        }}
        [data-testid="stChatInput"] textarea {{
            min-height: 2.6rem;
        }}
        @supports (padding: max(0px)) {{
            .block-container {{
                padding-left: max(0.7rem, env(safe-area-inset-left)) !important;
                padding-right: max(0.7rem, env(safe-area-inset-right)) !important;
                padding-bottom: max(4.5rem, env(safe-area-inset-bottom)) !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
