"""Yahoo Finance headlines + RSS — driven entirely by config.news.yahoo_rss."""

from __future__ import annotations

from typing import Any

from market_intel import NewsItem, fetch_rss_titles, fetch_yahoo_finance_news


class YahooRssNewsIntel:
    __slots__ = ("_cfg",)

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._cfg = cfg

    def gather(self, stock_symbol: str, include_world_rss: bool) -> tuple[list[NewsItem], list[NewsItem]]:
        bench = list(self._cfg.get("benchmark_symbols") or ["^NSEI"])
        max_per = int(self._cfg.get("max_per_symbol") or 6)
        equity_sources = [stock_symbol.strip().upper()] + [s.upper() for s in bench if s]
        equity_news = fetch_yahoo_finance_news(equity_sources, max_per_symbol=max_per)

        world: list[NewsItem] = []
        cap = int(self._cfg.get("world_headlines_cap") or 10)
        per_feed = int(self._cfg.get("rss_max_items_per_feed") or 4)
        rss_urls = tuple(self._cfg.get("rss_urls") or [])
        if include_world_rss:
            for u in rss_urls:
                world.extend(fetch_rss_titles(str(u), max_items=per_feed))
                if len(world) >= cap:
                    break
            world = world[:cap]

        return equity_news, world
