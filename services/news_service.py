"""News intelligence service."""

from __future__ import annotations

import time
from typing import Any

from config.loader import load_settings
from providers.news_yahoo_rss import YahooRssNewsIntel


class NewsService:
    """Gather equity and world news headlines."""

    def __init__(self, settings: dict | None = None) -> None:
        self.settings = settings or load_settings()
        cfg = (self.settings.get("news") or {}).get("yahoo_rss") or {}
        self._provider = YahooRssNewsIntel(cfg)
        self._cache: dict[str, tuple[float, Any]] = {}

    def gather(self, symbol: str, include_world: bool = True) -> tuple[list, list]:
        news_cfg = self.settings.get("news", {}).get("yahoo_rss") or {}
        ttl = float(news_cfg.get("intel_cache_ttl_seconds") or 600)
        key = f"news|{symbol.upper()}|{include_world}"
        now = time.time()
        if key in self._cache and (now - self._cache[key][0]) < ttl:
            return self._cache[key][1]
        equity, world = self._provider.gather(symbol.strip(), include_world)
        self._cache[key] = (now, (equity, world))
        return equity, world
