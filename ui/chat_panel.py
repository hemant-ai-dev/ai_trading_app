"""Portal 1 chat + strategy-to-worker task composer."""

from __future__ import annotations

from typing import Any

import streamlit as st

from chat import desk_chat
from tasks import store
from workers.orchestrator import run_until_blocked


def render_desk_chat(user: dict, analysis: dict[str, Any] | None, symbol: str) -> None:
    st.markdown("##### AI desk chat")
    st.caption("Answers use this session’s analysis, SQLite prediction history, and worker tasks — not a generic chatbot.")
    uid = int(user["user_id"])
    for msg in desk_chat.load_messages(uid):
        with st.chat_message(msg["Role"]):
            st.markdown(msg["Content"])
    prompt = st.chat_input("Ask about trend, HOLD, risk, history, or send a worker task…")
    if prompt:
        desk_chat.save_message(uid, "user", prompt, symbol)
        reply = desk_chat.answer(user_id=uid, text=prompt, analysis=analysis, symbol=symbol)
        desk_chat.save_message(uid, "assistant", reply, symbol)
        st.rerun()


def render_task_composer(user: dict, symbol: str) -> None:
    st.markdown("##### Send a task to AI Workers")
    st.caption("Creates a structured job on Portal 2. This does not place a live order.")
    text = st.text_area(
        "Request",
        value=f"Monitor {symbol} and notify me if the price falls 2% from the last print.",
        key="p1_task_text",
    )
    if st.button("Create worker task", type="primary", key="p1_create_task"):
        if not text.strip():
            st.error("Write a request first.")
            return
        task = store.create_task(
            user_id=int(user["user_id"]),
            request_text=text.strip(),
            source="portal1_strategy",
            symbol=symbol,
        )
        ctx = {
            "market": st.session_state["analysis"].market,
            "analysis": st.session_state["analysis"],
            "default_symbol": symbol,
        }
        run_until_blocked(int(task["TaskId"]), ctx)
        st.success(f"Task {task['PublicId']} sent to the Workers portal.")
