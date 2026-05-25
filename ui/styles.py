"""Professional Gen AI desk — hide Streamlit chrome."""

import streamlit as st


def inject_responsive_css() -> None:
    st.markdown(
        """
        <style>
        /* Hide Deploy, menu, footer, header clutter */
        [data-testid="stToolbar"], .stDeployButton, #MainMenu, footer,
        header[data-testid="stHeader"] { visibility: hidden !important; height: 0 !important; }
        .stApp > header { background: transparent; }
        /* Cleaner metrics */
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.04);
            padding: 0.65rem 0.85rem;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        @media (max-width: 768px) {
            .block-container { padding: 0.5rem 0.75rem; }
            h1 { font-size: 1.25rem !important; }
        }
        .signal-hero {
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
