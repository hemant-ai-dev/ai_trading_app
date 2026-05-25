"""Single combined view: BUY/SELL/HOLD + detailed reason + logic (EN + MR)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.bilingual import REGIME_MR, SIGNAL_EN_MR, build_steps_table, factors_table_rows
from ui.explanations import build_rule_narrative_en, build_rule_narrative_mr

INDICATOR_MR = {
    "RSI": "मोमेंटम — खरेदी/विक्रीची ताकद मोजते",
    "EMA 9": "लघुकालीन सरासरी — तात्काळ ट्रेंड",
    "EMA 20": "मध्यमकालीन सरासती — मुख्य ट्रेंड दिशा",
    "MACD": "ट्रेंड बदल आणि मोमेंटम",
    "VWAP": "व्हॉल्यूम-भारित सरासरी — सत्राची ‘योग्य’ किंमत",
    "ATR": "चढउतार — स्टॉप/लक्ष्य अंतरासाठी",
}

INDICATOR_EN = {
    "RSI": "Above 60 = strong momentum; below 40 = weak; 45–55 = neutral zone.",
    "EMA 9": "Short-term average — reacts quickly to price.",
    "EMA 20": "Medium-term average — defines main trend direction.",
    "MACD": "Cross above signal line with MACD>0 supports bulls; opposite for bears.",
    "VWAP": "Institutions often reference VWAP intraday — above = relative strength.",
    "ATR": "Average True Range — sizes stop and target bands.",
}


def _signal_color(sig: str) -> str:
    return {"BUY": "#27ae60", "SELL": "#e74c3c", "HOLD": "#f39c12"}.get(sig, "#95a5a6")


def render_signal_decision_block(
    *,
    signal: str,
    confidence: float,
    target: float,
    stop: float,
    last_close: float,
    source_label: str,
    reason: str,
    score: float | None,
    market_regime: str | None,
    brain: dict | None,
    logic_snap: dict,
    rule: dict,
    acc_summary: dict,
) -> None:
    sig = signal.upper()
    en_label, mr_label = SIGNAL_EN_MR.get(sig, (sig, sig))
    color = _signal_color(sig)

    st.markdown(
        f"""
        <div class="signal-hero" style="border-left:6px solid {color};
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);">
        <h2 style="margin:0;color:{color};font-size:1.75rem;">{en_label}</h2>
        <h3 style="margin:0.25rem 0 0 0;color:#d7bde2;font-weight:500;">{mr_label}</h3>
        <p style="margin:0.6rem 0 0 0;font-size:1.05rem;opacity:0.95;">
        Confidence <b>{confidence}%</b> · Live <b>₹{last_close:,.2f}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Target", f"₹{target:,.2f}")
    c2.metric("Stop / invalidation", f"₹{stop:,.2f}")
    c3.metric("Market structure", REGIME_MR.get(market_regime or "", market_regime or "—"))

    st.markdown("### 📋 Decision summary | निर्णय सारांश")
    st.dataframe(
        pd.DataFrame(
            [
                {"Item": "Signal", "English": en_label, "Marathi": mr_label},
                {"Item": "Confidence", "English": f"{confidence}%", "Marathi": f"{confidence}% विश्वास"},
                {"Item": "Target", "English": f"₹{target:,.2f}", "Marathi": f"लक्ष्य ₹{target:,.2f}"},
                {"Item": "Stop", "English": f"₹{stop:,.2f}", "Marathi": f"स्टॉप ₹{stop:,.2f}"},
                {
                    "Item": "Structure",
                    "English": market_regime or "—",
                    "Marathi": REGIME_MR.get(market_regime or "", "—"),
                },
                {
                    "Item": "Engine",
                    "English": source_label,
                    "Marathi": "Gen AI" if "Gen" in source_label else "नियम इंजिन",
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 💬 Detailed explanation | सविस्तर स्पष्टीकरण")

    if brain and brain.get("market_read"):
        col_en, col_mr = st.columns(2)
        with col_en:
            st.markdown("#### English — Gen AI analysis")
            st.markdown(brain["market_read"])
            if brain.get("risks"):
                st.markdown(f"**Risks:** {brain['risks']}")
        with col_mr:
            st.markdown("#### मराठी — Gen AI विश्लेषण")
            st.markdown(brain.get("market_read_mr") or "_मराठी आउटपुट उपलब्ध नाही — API पुन्हा चालवा._")
    else:
        col_en, col_mr = st.columns(2)
        with col_en:
            st.markdown("#### English — full logic")
            st.markdown(build_rule_narrative_en(sig, rule, logic_snap))
        with col_mr:
            st.markdown("#### मराठी — पूर्ण तर्क")
            st.markdown(build_rule_narrative_mr(sig, rule, logic_snap))

    st.markdown("### 🔍 Step-by-step logic | पायरी-पायरी तर्क")
    steps_df = pd.DataFrame(build_steps_table(brain, reason))
    if not steps_df.empty:
        st.dataframe(steps_df, use_container_width=True, hide_index=True)

    st.markdown("### 📐 Indicators (values + meaning) | निर्देशक")
    ind = logic_snap.get("indicators") or {}
    if ind:
        rows = []
        labels = {
            "rsi": "RSI",
            "ema9": "EMA 9",
            "ema20": "EMA 20",
            "macd": "MACD",
            "vwap": "VWAP",
            "atr": "ATR",
        }
        for key, name in labels.items():
            if key in ind:
                val = float(ind[key])
                disp = round(val, 2) if key == "rsi" else round(val, 2)
                rows.append(
                    {
                        "Indicator": name,
                        "Value": disp,
                        "Detail (English)": INDICATOR_EN.get(name, ""),
                        "Detail (Marathi)": INDICATOR_MR.get(name, ""),
                    }
                )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### 🏷 All factors in score | स्कोअरमधील घटक")
    ft = pd.DataFrame(factors_table_rows(reason))
    if not ft.empty:
        st.dataframe(ft, use_container_width=True, hide_index=True)

    if acc_summary.get("evaluated", 0) > 0:
        st.markdown("### ✅ Prediction accuracy | अचूकता")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Points checked": acc_summary.get("evaluated"),
                        "Within ±1%": f"{acc_summary.get('hit_rate_pct', 0)}%",
                        "Avg error": f"{acc_summary.get('avg_error_pct', 0)}%",
                    }
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
