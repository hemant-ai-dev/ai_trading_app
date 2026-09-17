"""Grounded desk chat — delegates to the tool-using internal AI agent."""

from __future__ import annotations

from typing import Any

from ai import chat_agent


def save_message(user_id: int, role: str, content: str, symbol: str | None = None) -> None:
    chat_agent.save_message(int(user_id), role, content, symbol=symbol, conversation_id="desk")


def load_messages(user_id: int, *, limit: int = 40) -> list[dict[str, Any]]:
    return chat_agent.load_messages(int(user_id), conversation_id="desk", limit=limit)


def answer(
    *,
    user_id: int,
    text: str,
    analysis: dict[str, Any] | None,
    symbol: str,
) -> str:
    del analysis  # tools fetch daily analysis themselves
    out = chat_agent.answer(
        user_id=int(user_id),
        text=text,
        symbol=symbol,
        conversation_id="desk",
    )
    return str(out.get("reply") or out.get("error") or "No reply.")
