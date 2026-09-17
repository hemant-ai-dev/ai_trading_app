"""Dedicated AI Trading Chat workspace."""

from __future__ import annotations

import json

import streamlit as st

from ai import chat_agent

_PRESETS = [
    ("Nifty 50", "^NSEI", "Tell me about Nifty 50"),
    ("Bank Nifty", "^NSEBANK", "Tell me about Bank Nifty"),
    ("Tata Motors", "TATAMOTORS.NS", "Analyze TATAMOTORS using daily data"),
    ("Climate / ESG", "^NSEI", "How can environment and climate news affect Nifty 50?"),
]


def _role(raw: str) -> str:
    name = (raw or "").strip().lower()
    if name in ("user", "human"):
        return "user"
    return "assistant"


def render_ai_trading_chat(user: dict) -> None:
    st.markdown(
        """
<div class="chat-hero">
  <h1>Angad AI Chat</h1>
  <p>Type in any way you like — typos, short Hindi-English, “nfty ka rate”. I interpret the question, pick the instrument, then fill answers from daily tools. I still will not invent prices.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    uid = int(user["user_id"])
    c1, c2 = st.columns([2.2, 1])
    with c1:
        default_symbol = st.selectbox(
            "Fallback instrument if your message has no ticker",
            ["^NSEI", "^NSEBANK", "^BSESN", "RELIANCE.NS", "TATAMOTORS.NS", "INFY.NS", "TCS.NS", "BHEL.NS"],
            index=0,
            key="ai_chat_symbol",
        )
    with c2:
        st.caption("Daily Yahoo/Stooq bars · educational only")

    chips = st.columns(len(_PRESETS))
    for col, (label, ticker, prompt) in zip(chips, _PRESETS):
        if col.button(label, use_container_width=True, key=f"chip_{ticker}_{label}"):
            with st.spinner("Fetching daily data and knowledge…"):
                chat_agent.answer(
                    user_id=uid,
                    text=prompt,
                    symbol=ticker,
                    conversation_id="trading_chat",
                )
            st.rerun()

    messages = chat_agent.load_messages(uid, conversation_id="trading_chat", limit=50)
    if not messages:
        st.info("Try **Nifty 50** or ask *How does climate news affect markets?*")

    for msg in messages:
        with st.chat_message(_role(str(msg.get("Role") or "assistant"))):
            st.markdown(msg["Content"])
            tools = msg.get("ToolsJson")
            if tools and _role(str(msg.get("Role"))) == "assistant":
                try:
                    used = json.loads(tools)
                    names = [t.get("tool") for t in used if t.get("tool")]
                    ok = [t.get("tool") for t in used if t.get("ok")]
                    if names:
                        st.caption("Tools: " + ", ".join(names) + (f" · ok: {', '.join(ok)}" if ok else ""))
                except json.JSONDecodeError:
                    pass

    prompt = st.chat_input("Any wording is fine — e.g. nfty ka rate, tata motor kaisa hai, climate news…")
    if not prompt:
        return
    with st.spinner("Resolving symbol and feeding daily data into analysis tools…"):
        chat_agent.answer(
            user_id=uid,
            text=prompt,
            symbol=default_symbol,
            conversation_id="trading_chat",
        )
    st.rerun()
