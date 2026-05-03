"""OpenAI-compatible chat backend — swap URL/key via env for Azure/other gateways."""

from __future__ import annotations

import json
import os
from typing import Any


class OpenAILLM:
    """Uses official OpenAI SDK; set OPENAI_BASE_URL for proxies/Azure-compatible endpoints."""

    __slots__ = ("_model_chat", "_model_json", "_client")

    def __init__(
        self,
        *,
        api_key: str,
        model_chat: str,
        model_json: str,
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": api_key.strip()}
        if base_url:
            kwargs["base_url"] = base_url.strip()
        elif os.getenv("OPENAI_BASE_URL"):
            kwargs["base_url"] = os.getenv("OPENAI_BASE_URL", "").strip()
        self._client = OpenAI(**kwargs)
        self._model_chat = model_chat
        self._model_json = model_json

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any] | None:
        try:
            resp = self._client.chat.completions.create(
                model=self._model_json,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw = resp.choices[0].message.content
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def chat_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> str | None:
        try:
            resp = self._client.chat.completions.create(
                model=self._model_chat,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            choice = resp.choices[0].message.content
            return choice.strip() if choice else None
        except Exception:
            return None


class NullLLM:
    """No-op backend for offline UI checks."""

    def chat_json(self, **kwargs) -> dict[str, Any] | None:
        return None

    def chat_text(self, **kwargs) -> str | None:
        return None
