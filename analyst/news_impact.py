"""Step 2 — News intelligence with bullish/bearish/neutral impact scoring."""

from __future__ import annotations

from typing import Any

from analyst.models import NewsImpactItem

BULLISH_KEYWORDS = (
    "surge", "rally", "jump", "gain", "soar", "record high", "beat", "beats",
    "upgrade", "buy", "bullish", "profit", "growth", "expansion", "deal",
    "win", "wins", "approval", "approved", "strong", "outperform", "dividend",
    "raise", "raises", "raised guidance", "contract win", "order win",
    "positive", "breakthrough", "all-time high",
)

BEARISH_KEYWORDS = (
    "fall", "falls", "drop", "drops", "plunge", "crash", "slump", "loss",
    "losses", "miss", "misses", "downgrade", "sell", "bearish", "fraud",
    "probe", "investigation", "ban", "fine", "penalty", "cut", "cuts",
    "layoff", "weak", "warning", "default", "lawsuit", "decline", "down",
    "recession", "inflation spike", "rate hike", "geopolitical", "war",
)

# Amplifiers for market-moving categories
STRONG_AMPLIFIERS = (
    "earnings", "results", "rbi", "fed", "interest rate", "sebi", "budget",
    "war", "election", "crude", "oil", "inflation", "gdp", "fii", "dii",
    "block deal", "bulk deal", "guidance", "bankruptcy",
)


def _headline_text(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        title = str(item.get("title") or item.get("headline") or "")
        source = str(item.get("source") or item.get("publisher") or "news")
        return title, source
    title = str(getattr(item, "title", "") or getattr(item, "headline", "") or item)
    source = str(getattr(item, "source", "news") or "news")
    return title, source


def score_headline(title: str, source: str = "news") -> NewsImpactItem:
    """Score a single headline for directional market impact."""
    text = title.lower()
    bull = sum(1 for k in BULLISH_KEYWORDS if k in text)
    bear = sum(1 for k in BEARISH_KEYWORDS if k in text)
    amp = sum(1 for k in STRONG_AMPLIFIERS if k in text)

    if bull > bear:
        impact = "bullish"
        strength = min(1.0, 0.35 + 0.15 * bull + 0.12 * amp)
        reason = "Headline language suggests positive market reaction."
    elif bear > bull:
        impact = "bearish"
        strength = min(1.0, 0.35 + 0.15 * bear + 0.12 * amp)
        reason = "Headline language suggests negative market reaction."
    else:
        impact = "neutral"
        strength = 0.15 + 0.08 * amp
        reason = "No clear bullish or bearish tilt from wording alone."

    if amp:
        reason += " Market-sensitive topic detected (earnings/macro/regulatory)."

    # Signed score on master schema scale −1.0 … +1.0
    if impact == "bullish":
        signed = strength
    elif impact == "bearish":
        signed = -strength
    else:
        signed = 0.0

    item = NewsImpactItem(
        headline=title.strip() or "(untitled)",
        source=source,
        impact=impact,
        strength=round(strength, 3),
        reason=reason,
        signed_score=round(signed, 3),
    )
    return item


def analyze_news_impact(
    equity_news: list | None,
    world_news: list | None,
    *,
    max_items: int = 14,
) -> tuple[list[NewsImpactItem], dict[str, Any]]:
    """
    Analyze news lists and return scored items plus an aggregate summary.

    Does not merely list headlines — assigns impact direction and strength.
    """
    items: list[NewsImpactItem] = []
    for bucket, label in ((equity_news or [], "equity"), (world_news or [], "world")):
        for raw in bucket:
            title, source = _headline_text(raw)
            if not title.strip():
                continue
            scored = score_headline(title, source or label)
            items.append(scored)

    # Keep strongest first
    items.sort(key=lambda x: x.strength, reverse=True)
    items = items[:max_items]

    bull = [i for i in items if i.impact == "bullish"]
    bear = [i for i in items if i.impact == "bearish"]
    bull_score = sum(i.strength for i in bull)
    bear_score = sum(i.strength for i in bear)
    net = bull_score - bear_score

    if net > 0.45:
        tilt = "bullish"
        summary = (
            f"News lean is bullish (net impact {net:+.2f}). "
            f"{len(bull)} positive vs {len(bear)} negative headlines."
        )
    elif net < -0.45:
        tilt = "bearish"
        summary = (
            f"News lean is bearish (net impact {net:+.2f}). "
            f"{len(bear)} negative vs {len(bull)} positive headlines."
        )
    else:
        tilt = "neutral"
        summary = (
            f"News lean is mixed/neutral (net impact {net:+.2f}). "
            "No dominant headline driver."
        )

    # Major event flag: any strong amplifier headline
    major = any(i.strength >= 0.7 for i in items)

    aggregate = {
        "tilt": tilt,
        "net_score": round(net, 3),
        "bull_score": round(bull_score, 3),
        "bear_score": round(bear_score, 3),
        "count": len(items),
        "major_event": major,
        "summary": summary,
    }
    return items, aggregate
