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
            background: {bg} !important;
            color: {text};
            -webkit-font-smoothing: antialiased;
        }}
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
        .auth-shell {{
            text-align: center;
            padding: 1.2rem 0 0.4rem;
        }}
        .auth-brand {{
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: 0.04em;
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
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {{
            font-size: 16px !important;
        }}
        .js-plotly-plot, .plotly {{
            max-width: 100% !important;
        }}
        [data-testid="stDataFrame"] {{
            overflow-x: auto;
        }}
        a {{ color: {accent} !important; }}
        .stCheckbox label span {{ color: {text} !important; }}

        @media (max-width: 900px) {{
            .block-container {{
                padding: 0.55rem 0.7rem 5rem !important;
                max-width: 100%;
            }}
            .terminal-title {{ font-size: 1.15rem; }}
            .smart-signal {{ font-size: 1.7rem; }}
            .ai-pred {{ font-size: 1.35rem; }}
            [data-testid="stMetric"] {{ padding: 0.55rem 0.6rem; }}
            [data-testid="stHorizontalBlock"] {{
                gap: 0.5rem !important;
            }}
            div[data-testid="stTabs"] button {{
                padding: 0.4rem 0.65rem !important;
            }}
            button, [data-testid="baseButton-secondary"], [data-testid="baseButton-primary"] {{
                min-height: 44px;
            }}
        }}
        @media (max-width: 480px) {{
            .smart-grid {{ grid-template-columns: 1fr 1fr; }}
            .auth-brand {{ font-size: 1.65rem; }}
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
