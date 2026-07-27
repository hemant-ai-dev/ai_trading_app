"""LLM provider factory."""

from __future__ import annotations

import os
from typing import Any

from ai.llm_openai import NullLLM, OpenAILLM


def resolve_openai_api_key(settings: dict) -> str | None:
    """Resolve OpenAI API key from config, secrets, or environment."""
    nested = (settings.get("llm") or {}).get("openai") or {}
    k = nested.get("api_key")
    if k and str(k).strip():
        return str(k).strip()
    k = os.getenv("OPENAI_API_KEY")
    return k.strip() if k else None


def build_llm_provider(settings: dict, *, api_key_override: str | None = None) -> Any:
    name = (settings.get("llm") or {}).get("provider") or "openai"
    if name == "none":
        return NullLLM()
    if name == "openai":
        sec = (settings.get("llm") or {}).get("openai") or {}
        key = api_key_override or resolve_openai_api_key(settings)
        if not key:
            return NullLLM()
        base_url = sec.get("base_url") or os.getenv("OPENAI_BASE_URL")
        return OpenAILLM(
            api_key=key,
            model_chat=str(sec.get("model_chat") or "gpt-4o-mini"),
            model_json=str(sec.get("model_json") or "gpt-4o-mini"),
            base_url=str(base_url) if base_url else None,
        )
    raise ValueError(f"Unknown llm.provider: {name}")
