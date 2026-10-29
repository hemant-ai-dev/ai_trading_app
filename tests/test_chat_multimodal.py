"""Chat media validation, follow-ups, and image path without a vision model."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from ai.media import MediaError, load_image
from ai.nlu import understand
from ai.symbols import detect_symbols


def _png_bytes() -> bytes:
    img = Image.new("RGB", (40, 30), (20, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_rejects_non_image_bytes():
    with pytest.raises(MediaError):
        load_image(b"%PDF-1.4 fake", name="note.pdf", mime="application/pdf")


def test_accepts_png_and_resizes():
    img, meta = load_image(_png_bytes(), name="chart.png", mime="image/png")
    assert img.size[0] <= 1600
    assert meta["format"] == "png"


def test_follow_up_support_keeps_nifty():
    mind = understand("What is the support level?", previous_symbol="^NSEI")
    assert mind.symbol == "^NSEI"
    assert mind.used_previous_symbol is True
    assert "analysis" in mind.intents


def test_compare_two_names():
    mind = understand("Compare RELIANCE and INFY")
    assert mind.symbol in ("RELIANCE.NS", "INFY.NS")
    assert mind.compare_symbol in ("RELIANCE.NS", "INFY.NS")
    assert mind.symbol != mind.compare_symbol
    assert detect_symbols("NIFTY vs BANKNIFTY")[:2]


def test_answer_image_without_vision_does_not_invent(monkeypatch, tmp_path):
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(tmp_path / "chat.db"))
    from db.bootstrap import initialize
    from db.database import execute

    initialize()
    execute("INSERT INTO TReadUser (UserId, Username, Email, PasswordHash) VALUES (1,'t','t@t','x')")

    from ai import chat_agent
    from ai.llm_openai import NullLLM

    monkeypatch.setattr("ai.vision.build_llm_provider", lambda _s: NullLLM())
    monkeypatch.setattr(chat_agent, "_run_tools", lambda *a, **k: [])
    monkeypatch.setattr(chat_agent, "_llm_polish", lambda *a, **k: a[-1] if a else "draft")
    out = chat_agent.answer(
        user_id=1,
        text="Analyse this chart",
        symbol="^NSEI",
        conversation_id="test_chat",
        image_bytes=_png_bytes(),
        image_name="nifty.png",
        image_mime="image/png",
    )
    assert out["ok"] is True
    assert "invent" in out["reply"].lower() or "vision" in out["reply"].lower() or "VISIBLE" in out["reply"]
    vis = [t for t in out["tools"] if t["tool"] == "analyze_image"]
    assert vis
    assert vis[0]["result"].get("source") in ("local_limits", "openai_vision")
