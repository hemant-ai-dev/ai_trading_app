"""Speech-to-text for chat audio. Prefer browser Web Speech (no server upload).

Recorded blobs from Streamlit's chat mic are only transcribed locally if a
free local engine is installed. OpenAI Whisper API is not called (extra cost).
"""

from __future__ import annotations

from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


def transcribe_audio(data: bytes, *, mime: str | None = None, name: str | None = None) -> dict[str, Any]:
    if not data:
        return {"ok": False, "text": "", "error": "Empty audio clip."}
    # Optional local whisper (not in requirements — must already be installed).
    try:
        import whisper  # type: ignore
        import tempfile
        import os

        suffix = ".webm"
        if name and "." in name:
            suffix = "." + name.rsplit(".", 1)[-1]
        elif mime and "wav" in mime:
            suffix = ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            path = tmp.name
        try:
            model = whisper.load_model("base")
            out = model.transcribe(path)
            text = str(out.get("text") or "").strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if text:
            return {
                "ok": True,
                "text": text,
                "source": "local_whisper",
                "note": "Transcribed on this machine. Audio was not sent to OpenAI Audio API.",
            }
    except Exception:
        logger.info("local whisper unavailable; browser dictation should be used instead")
    return {
        "ok": False,
        "text": "",
        "error": (
            "This app does not send microphone audio to a paid speech API. "
            "Use the browser dictation button (Chrome/Edge Web Speech) so text appears before Send, "
            "or type the message. Optional: install local `openai-whisper` for file transcription."
        ),
        "source": None,
    }
