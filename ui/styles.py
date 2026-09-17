"""Trading-terminal CSS for Angad dashboard."""

from __future__ import annotations

import streamlit as st


def inject_responsive_css(theme: str = "dark") -> None:
    """Inject terminal-style CSS. theme is 'dark' or 'light'."""
    dark = theme != "light"
    bg = "#07090c" if dark else "#f4f6f9"
    panel = "#12161c" if dark else "#ffffff"
    text = "#e8eaed" if dark else "#0f172a"
    muted = "#8b909a"
    border = "rgba(255,255,255,0.08)" if dark else "rgba(15,23,42,0.08)"
    accent = "#3b82f6"

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: radial-gradient(1200px 500px at 10% -10%, rgba(59,130,246,0.16), transparent 55%),
                        radial-gradient(900px 400px at 100% 0%, rgba(240,185,11,0.08), transparent 50%),
                        {bg} !important;
            color: {text};
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden !important;
        }}
        .stApp {{ overflow-x: hidden; }}
        [data-testid="stToolbar"], .stDeployButton, #MainMenu, footer {{
            visibility: hidden !important;
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .block-container {{
            padding-top: 0.85rem !important;
            padding-bottom: 4.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 1440px;
        }}
        [data-testid="stMetric"] {{
            background: {panel};
            padding: 0.7rem 0.85rem;
            border-radius: 12px;
            border: 1px solid {border};
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
            font-size: 2.1rem;
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
            letter-spacing: 0.14em;
            font-size: 0.95rem;
        }}
        .brand-sub {{ color: {muted}; font-size: 0.75rem; }}
        .hello-line {{
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.2;
        }}
        .hello-sub {{ color: {muted}; font-size: 0.8rem; margin-top: 0.15rem; }}
        .signal-hero {{
            background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
            border: 1px solid {border};
            border-left-width: 6px;
            border-radius: 18px;
            padding: 1.05rem 1.15rem 0.35rem;
            margin: 0.2rem 0 0.65rem;
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
        .auth-hero {{
            padding: 1.4rem 0.4rem 1rem;
        }}
        .auth-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            color: {accent};
            font-weight: 700;
        }}
        .auth-brand {{
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: 0.02em;
            line-height: 1.05;
            margin: 0.25rem 0 0.6rem;
        }}
        .auth-lead {{
            color: {text};
            opacity: 0.9;
            font-size: 1.05rem;
            line-height: 1.5;
            max-width: 28rem;
        }}
        .auth-pills span {{
            display: inline-block;
            margin: 0.2rem 0.35rem 0.2rem 0;
            padding: 0.28rem 0.65rem;
            border-radius: 999px;
            border: 1px solid {border};
            background: {panel};
            font-size: 0.75rem;
            letter-spacing: 0.04em;
        }}
        .auth-points {{
            color: {muted};
            line-height: 1.65;
            padding-left: 1.1rem;
            margin-top: 1rem;
        }}
        .auth-card-title {{
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 0.15rem;
        }}
        .auth-tag {{ color: {muted}; margin-top: 0.25rem; }}
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
            [data-testid="stMetric"] {{ padding: 0.55rem 0.6rem; }}
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
            .auth-brand {{ font-size: 1.65rem; }}
            .auth-hero {{ padding-top: 0.2rem; }}
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
            background: linear-gradient(135deg, rgba(59,130,246,0.18), rgba(15,23,42,0.5));
            border: 1px solid {border};
            border-radius: 18px;
            padding: 1.1rem 1.2rem 1rem;
            margin-bottom: 0.85rem;
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
