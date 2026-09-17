"""Pydantic schemas for Angad internal APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    symbol: str | None = Field(default=None, max_length=32)
    conversation_id: str = Field(default="trading_chat", max_length=64)


class TaskCreateRequest(BaseModel):
    request_text: str = Field(min_length=3, max_length=2000)
    symbol: str | None = Field(default=None, max_length=32)


class ErrorBody(BaseModel):
    ok: bool = False
    error: str
    code: str = "error"
