"""Factory functions — API keys resolved from SQL-backed settings only."""

from __future__ import annotations

import os
from typing import Any

from providers.contracts import LLMProvider, MarketDataProvider, NewsIntelProvider
from providers.llm_openai import NullLLM, OpenAILLM
from providers.market_yfinance import YfinanceMarketData
from providers.news_yahoo_rss import YahooRssNewsIntel


def resolve_openai_api_key(settings: dict) -> str | None:
    """Primary source: SQL table api_config (merged into settings). Env is fallback only."""
    nested = (settings.get("llm") or {}).get("openai") or {}
    k = nested.get("api_key")
    if k and str(k).strip():
        return str(k).strip()
    k = os.getenv("OPENAI_API_KEY")
    return k.strip() if k else None


def build_market_data_provider(settings: dict) -> MarketDataProvider:
    name = (settings.get("market_data") or {}).get("provider") or "yfinance"
    if name == "yfinance":
        opts = (settings.get("market_data") or {}).get("yfinance") or {}
        return YfinanceMarketData(opts)
    raise ValueError(f"Unknown market_data.provider: {name}")


def build_llm_provider(settings: dict, *, api_key_override: str | None = None) -> LLMProvider:
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


def build_news_intel_provider(settings: dict) -> NewsIntelProvider:
    name = (settings.get("news") or {}).get("provider") or "yahoo_rss"
    if name == "yahoo_rss":
        cfg = (settings.get("news") or {}).get("yahoo_rss") or {}
        return YahooRssNewsIntel(cfg)
    raise ValueError(f"Unknown news.provider: {name}")
