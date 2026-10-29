"""Dedicated AI Trading Chat workspace — text, dictation, and screenshots."""

from __future__ import annotations

import json
import uuid

import pandas as pd
import streamlit as st

from ai import chat_agent
from ai.transcribe import transcribe_audio
from ui.voice import dictation_bar

_PRESETS = [
    ("Nifty 50", "^NSEI", "Show me today's NIFTY data."),
    ("Reliance", "RELIANCE.NS", "Show me today's RELIANCE data."),
    ("Nifty chain", "^NSEI", "Show me NIFTY option chain."),
    ("Reliance chain", "RELIANCE.NS", "Show me RELIANCE option chain."),
]


def _role(raw: str) -> str:
    name = (raw or "").strip().lower()
    if name in ("user", "human"):
        return "user"
    return "assistant"


def _parse_tools(raw) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {}
    if isinstance(data, list):
        return {"tools": data, "ui": {}}
    if isinstance(data, dict):
        return data
    return {}


def _render_ui(ui: dict) -> None:
    img = (ui or {}).get("image") or {}
    thumb = img.get("thumb")
    if thumb:
        st.image(thumb, caption=(img.get("meta") or {}).get("name") or "attachment", width=360)
    chain = (ui or {}).get("option_chain") or {}
    if chain:
        calls = pd.DataFrame(chain.get("calls") or [])
        puts = pd.DataFrame(chain.get("puts") or [])
        rec = chain.get("recommendation") or {}
        if rec:
            st.caption(
                f"Option AI action **{rec.get('action')}** · bias {rec.get('bias')} · "
                f"confidence {rec.get('confidence')}% (calibration, not a win rate)."
            )
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Calls (CE)**")
            if calls.empty:
                st.info(chain.get("error") or "Option-chain data is currently unavailable. Please try again.")
            else:
                st.dataframe(calls, use_container_width=True, hide_index=True, height=280)
        with cols[1]:
            st.markdown("**Puts (PE)**")
            if puts.empty:
                if calls.empty:
                    st.info(chain.get("error") or "Option-chain data is currently unavailable. Please try again.")
                else:
                    st.caption("Puts are hidden by the current filter, or none were returned.")
            else:
                st.dataframe(puts, use_container_width=True, hide_index=True, height=280)
        hit = chain.get("contract")
        if hit:
            st.markdown(f"**Selected contract** strike {hit.get('strike')} {hit.get('right')} · LTP ₹{hit.get('ltp')}")
    bars = (ui or {}).get("bars") or []
    if bars:
        try:
            df = pd.DataFrame(bars)
            if "close" in df.columns:
                st.line_chart(df.set_index(df.columns[0] if "t" not in df.columns else "t")["close"])
        except Exception:
            pass


def _conversation_id() -> str:
    cid = st.session_state.get("trading_chat_id") or "trading_chat"
    st.session_state["trading_chat_id"] = cid
    return str(cid)


def _submit(
    *,
    uid: int,
    text: str,
    symbol: str,
    image_bytes: bytes | None = None,
    image_name: str | None = None,
    image_mime: str | None = None,
) -> None:
    with st.status("Working on your request…", expanded=False) as status:
        st.write("Using desk tools (quotes, analysis, stored predictions). Not a live broker.")
        out = chat_agent.answer(
            user_id=uid,
            text=text,
            symbol=symbol,
            conversation_id=_conversation_id(),
            image_bytes=image_bytes,
            image_name=image_name,
            image_mime=image_mime,
        )
        if not out.get("ok"):
            status.update(label="Request failed", state="error")
            st.error(out.get("error") or "Chat failed.")
            return
        status.update(label="Done", state="complete")
    st.rerun()


def render_ai_trading_chat(user: dict) -> None:
    st.markdown(
        """
<div class="chat-hero">
  <h1>Angad AI Chat</h1>
  <p>Text, optional mic dictation, and chart screenshots. Numbers come from this desk — I do not invent live prices.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    uid = int(user["user_id"])
    c1, c2, c3 = st.columns([2.0, 1.0, 0.9])
    with c1:
        default_symbol = st.selectbox(
            "Fallback instrument if your message has no ticker",
            ["^NSEI", "^NSEBANK", "^BSESN", "RELIANCE.NS", "TATAMOTORS.NS", "INFY.NS", "TCS.NS", "BHEL.NS"],
            index=0,
            key="ai_chat_symbol",
        )
    with c2:
        st.caption("Enter sends · Shift+Enter new line · attach PNG/JPG/WEBP")
    with c3:
        if st.button("New conversation", use_container_width=True, key="chat_new"):
            st.session_state["trading_chat_id"] = f"trading_chat_{uuid.uuid4().hex[:10]}"
            st.session_state.pop("chat_voice_draft", None)
            st.rerun()

    chips = st.columns(len(_PRESETS))
    for col, (label, ticker, prompt) in zip(chips, _PRESETS):
        if col.button(label, use_container_width=True, key=f"chip_{ticker}_{label}"):
            _submit(uid=uid, text=prompt, symbol=ticker)

    voice = dictation_bar(key=f"voice_{_conversation_id()}")
    if isinstance(voice, dict) and voice.get("ok") and voice.get("text"):
        spoken = str(voice["text"]).strip()
        if spoken and st.session_state.get("chat_voice_applied") != spoken:
            st.session_state["chat_voice_draft"] = spoken
            st.session_state["chat_voice_edit"] = spoken
            st.session_state["chat_voice_applied"] = spoken
    elif isinstance(voice, dict) and voice.get("error") == "not-allowed":
        st.warning("Microphone permission was denied. Allow the browser mic, or type.")
    elif isinstance(voice, dict) and voice.get("error") == "unsupported":
        st.info("This browser cannot dictate. Type, use Win+H, or attach a screenshot.")

    draft = st.session_state.get("chat_voice_draft") or ""
    if draft:
        st.session_state.setdefault("chat_voice_edit", draft)
        edited = st.text_area(
            "Voice draft — edit before sending (not sent until you confirm)",
            key="chat_voice_edit",
            height=80,
        )
        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button("Send voice draft", type="primary", key="send_voice"):
            text = (edited or draft).strip()
            st.session_state.pop("chat_voice_draft", None)
            st.session_state.pop("chat_voice_edit", None)
            _submit(uid=uid, text=text, symbol=default_symbol)
        if b2.button("Discard draft", key="discard_voice"):
            st.session_state.pop("chat_voice_draft", None)
            st.session_state.pop("chat_voice_edit", None)
            st.rerun()

    messages = chat_agent.load_messages(uid, conversation_id=_conversation_id(), limit=50)
    if not messages:
        st.info("Try **Show me today's RELIANCE data**, attach a chart screenshot, or dictate in Chrome/Edge.")

    for msg in messages:
        with st.chat_message(_role(str(msg.get("Role") or "assistant"))):
            st.markdown(msg["Content"])
            payload = _parse_tools(msg.get("ToolsJson"))
            _render_ui(payload.get("ui") or {})
            if _role(str(msg.get("Role"))) == "assistant":
                names = [t.get("tool") for t in (payload.get("tools") or []) if t.get("tool")]
                if names:
                    st.caption("Modules: " + ", ".join(names))

    incoming = st.chat_input(
        "Ask anything — e.g. Analyse NIFTY 50 · attach a chart · mic is in this bar too",
        key="trading_chat_input",
        accept_file=True,
        file_type=["png", "jpg", "jpeg", "webp"],
        accept_audio=True,
        max_upload_size=6,
    )
    if not incoming:
        return

    text = incoming if isinstance(incoming, str) else (incoming.text or "")
    files = [] if isinstance(incoming, str) else list(incoming.files or [])
    audio = None if isinstance(incoming, str) else incoming.audio

    image_bytes = image_name = image_mime = None
    for f in files:
        mime = getattr(f, "type", None) or ""
        name = getattr(f, "name", "") or "upload.png"
        if mime.startswith("image/") or name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            image_bytes = f.getvalue()
            image_name = name
            image_mime = mime
            break
        st.error(f"Rejected `{name}` — only PNG, JPG, and WEBP images are accepted.")
        return

    if audio is not None and not (text or "").strip():
        spoken = transcribe_audio(
            audio.getvalue(),
            mime=getattr(audio, "type", None),
            name=getattr(audio, "name", None),
        )
        if spoken.get("ok") and spoken.get("text"):
            text = spoken["text"]
            st.caption(spoken.get("note") or "Transcribed locally.")
        else:
            st.warning(spoken.get("error") or "Could not transcribe. Dictation button puts editable text first.")
            return

    if not (text or "").strip() and not image_bytes:
        return
    _submit(
        uid=uid,
        text=text,
        symbol=default_symbol,
        image_bytes=image_bytes,
        image_name=image_name,
        image_mime=image_mime,
    )
