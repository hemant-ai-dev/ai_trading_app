"""Trading-terminal CSS for Angad dashboard."""

from __future__ import annotations

import streamlit as st


def inject_responsive_css(theme: str = "dark") -> None:
    """Inject terminal-style CSS. theme is 'dark' or 'light'."""
    dark = theme != "light"
    bg = "#0b0e11" if dark else "#f5f7fa"
    panel = "#12161c" if dark else "#ffffff"
    text = "#d1d4dc" if dark else "#131722"
    muted = "#787b86"
    border = "rgba(255,255,255,0.08)" if dark else "rgba(0,0,0,0.08)"
    accent = "#2962ff"

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: {bg} !important;
            color: {text};
        }}
        [data-testid="stToolbar"], .stDeployButton, #MainMenu, footer,
        header[data-testid="stHeader"] {{ visibility: hidden !important; height: 0 !important; }}
        .stApp > header {{ background: transparent; }}
        .block-container {{
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            max-width: 1600px;
        }}
        [data-testid="stMetric"] {{
            background: {panel};
            padding: 0.7rem 0.9rem;
            border-radius: 8px;
            border: 1px solid {border};
        }}
        [data-testid="stMetricLabel"] {{ color: {muted} !important; }}
        .signal-strip {{
            height: 3px;
            border-bottom: 3px solid;
            margin: 0.35rem 0 0.9rem 0;
            border-radius: 2px;
        }}
        .ai-panel {{
            background: {panel};
            border-radius: 8px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.75rem;
            border: 1px solid {border};
        }}
        .ai-panel-title {{
            font-size: 0.75rem;
            letter-spacing: 0.08em;
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
            border-radius: 8px;
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
            font-size: 1.45rem;
            margin-bottom: 0.15rem;
            color: {text};
        }}
        .terminal-sub {{
            color: {muted};
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }}
        div[data-testid="stTabs"] button {{
            font-weight: 600;
        }}
        @media (max-width: 768px) {{
            .block-container {{ padding: 0.5rem 0.65rem !important; }}
            .terminal-title {{ font-size: 1.15rem; }}
            .ai-pred {{ font-size: 1.35rem; }}
        }}
        /* Accent focus for interactive controls */
        .stCheckbox label span {{ color: {text} !important; }}
        a {{ color: {accent} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
