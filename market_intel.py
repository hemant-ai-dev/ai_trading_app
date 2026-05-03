"""Headlines and macro context for Angad AI (Yahoo Finance + optional RSS). Not investment advice."""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import yfinance as yf


@dataclass
class NewsItem:
    title: str
    source: str
    link: str = ""


def _parse_yf_news_item(raw: dict[str, Any]) -> NewsItem | None:
    c = raw.get("content")
    if isinstance(c, dict):
        title = (c.get("title") or "").strip()
        prov = c.get("provider") or {}
        source = (prov.get("displayName") or "Yahoo").strip()
        link = ""
        cu = c.get("canonicalUrl")
        if isinstance(cu, dict) and cu.get("url"):
            link = str(cu["url"])
        elif c.get("clickThroughUrl", {}).get("url"):
            link = str(c["clickThroughUrl"]["url"])
    else:
        title = str(raw.get("title", "")).strip()
        source = "Yahoo"
        link = str(raw.get("link", ""))
    if not title:
        return None
    return NewsItem(title=title, source=source, link=link)


def fetch_yahoo_finance_news(symbols: list[str], max_per_symbol: int = 6) -> list[NewsItem]:
    out: list[NewsItem] = []
    seen: set[str] = set()
    for sym in symbols:
        if not sym:
            continue
        try:
            t = yf.Ticker(sym)
            items = t.news or []
        except Exception:
            items = []
        for raw in items[:max_per_symbol]:
            ni = _parse_yf_news_item(raw) if isinstance(raw, dict) else None
            if ni is None:
                continue
            key = ni.title.lower()[:200]
            if key in seen:
                continue
            seen.add(key)
            out.append(ni)
    return out


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def fetch_rss_titles(url: str, max_items: int = 5, timeout: float = 8.0) -> list[NewsItem]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ai-trading-app/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        titles: list[NewsItem] = []
        for item in root.findall(".//item")[: max_items * 2]:
            t_el = item.find("title")
            if t_el is None or not t_el.text:
                continue
            title = _strip_html(t_el.text)
            link_el = item.find("link")
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            if title:
                titles.append(NewsItem(title=title, source="RSS", link=link))
            if len(titles) >= max_items:
                break
        return titles
    except Exception:
        return []


def gather_intel(
    stock_symbol: str,
    include_world_rss: bool = True,
    rss_urls: tuple[str, ...] = (
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    ),
) -> tuple[list[NewsItem], list[NewsItem]]:
    """
    Returns (equity_related, macro_world_headlines).
    Indian benchmark headline bundle helps broader market tone.
    """
    bench = "^NSEI"
    equity_sources = [stock_symbol.strip().upper(), bench]
    equity_news = fetch_yahoo_finance_news(equity_sources, max_per_symbol=6)

    world: list[NewsItem] = []
    if include_world_rss:
        for u in rss_urls:
            world.extend(fetch_rss_titles(u, max_items=4))
            if len(world) >= 8:
                break
        world = world[:10]

    return equity_news, world


def format_intel_for_prompt(equity: list[NewsItem], world: list[NewsItem], max_chars: int = 4500) -> str:
    lines = ["=== Yahoo/symbol + NIFTY index headlines (public) ==="]
    for n in equity:
        lines.append(f"- [{n.source}] {n.title}")
    lines.append("=== World / macro RSS headlines (public) ===")
    for n in world:
        lines.append(f"- [{n.source}] {n.title}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…(truncated)"
    return text


def news_digest_for_cache(equity: list[NewsItem], world: list[NewsItem]) -> str:
    blob = json.dumps([n.title for n in equity + world], ensure_ascii=False)
    return blob


def format_headlines_indexed_for_prompt(
    equity: list[NewsItem],
    world: list[NewsItem],
    *,
    max_equity: int = 14,
    max_world: int = 10,
) -> tuple[str, dict[str, str]]:
    """Stable IDs so the model can cite exact headlines (E1.. / W1..)."""
    lines: list[str] = []
    id_to_title: dict[str, str] = {}
    ei = 1
    for n in equity[:max_equity]:
        hid = f"E{ei}"
        lines.append(f"[{hid}] ({n.source}) {n.title}")
        id_to_title[hid] = n.title
        ei += 1
    wi = 1
    for n in world[:max_world]:
        hid = f"W{wi}"
        lines.append(f"[{hid}] ({n.source}) {n.title}")
        id_to_title[hid] = n.title
        wi += 1
    return "\n".join(lines), id_to_title
