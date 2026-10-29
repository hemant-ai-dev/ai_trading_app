"""Browser Web Speech dictation — no audio uploaded to our servers."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT = components.declare_component(
    "angad_voice",
    path=str(Path(__file__).resolve().parent / "voice_component"),
)


def dictation_bar(key: str = "chat_voice") -> dict | None:
    raw = _COMPONENT(key=key, default=None)
    return raw if isinstance(raw, dict) else None
