"""Shared dataclasses for the AI Trading Analyst."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class EvidenceFactor:
    """One piece of evidence the analyst considered."""

    name: str
    category: str  # technical | news | pattern | candle | macro | volume | fibonacci | structure
    direction: str  # bullish | bearish | neutral
    strength: float  # 0–1 raw signal strength
    weight: float  # dynamic importance 0–1
    contribution: float  # signed score contribution
    reason: str
    accepted: bool = True
    reject_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "direction": self.direction,
            "strength": round(self.strength, 3),
            "weight": round(self.weight, 3),
            "contribution": round(self.contribution, 3),
            "reason": self.reason,
            "accepted": self.accepted,
            "reject_reason": self.reject_reason,
        }


@dataclass
class MarketRegimeState:
    """Detected market regime and which techniques to emphasize."""

    regime: str  # trending_up | trending_down | sideways | volatile | breakout
    adx: float
    atr_pct: float
    vol_ratio: float
    preferred_techniques: list[str] = field(default_factory=list)
    de_emphasized: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "adx": round(self.adx, 2),
            "atr_pct": round(self.atr_pct, 3),
            "vol_ratio": round(self.vol_ratio, 3),
            "preferred_techniques": self.preferred_techniques,
            "de_emphasized": self.de_emphasized,
            "notes": self.notes,
        }


@dataclass
class NewsImpactItem:
    """Scored news headline with likely market impact."""

    headline: str
    source: str
    impact: str  # bullish | bearish | neutral
    strength: float  # 0–1
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "source": self.source,
            "impact": self.impact,
            "strength": round(self.strength, 3),
            "reason": self.reason,
        }


@dataclass
class ScenarioPath:
    """One future price scenario."""

    name: str  # bullish | base | bearish | neutral
    target_price: float
    series: pd.Series | None = None
    probability: float = 0.33
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_price": self.target_price,
            "probability": round(self.probability, 3),
            "summary": self.summary,
            "points": int(len(self.series)) if self.series is not None else 0,
        }


@dataclass
class AnalystReport:
    """Full explainable analyst report for the UI."""

    market_summary: str = ""
    current_trend: str = ""
    technical_analysis: str = ""
    news_analysis: str = ""
    pattern_analysis: str = ""
    risk_analysis: str = ""
    probability_analysis: str = ""
    prediction: str = "HOLD"
    confidence: float = 0.0
    why: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    stop_loss: str = ""
    alternative_scenarios: list[str] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [
            "# AI Trading Analyst Report",
            "",
            f"## Prediction: **{self.prediction}** ({self.confidence:.0f}% confidence)",
            "",
            "### Market Summary",
            self.market_summary or "—",
            "",
            "### Current Trend",
            self.current_trend or "—",
            "",
            "### Technical Analysis",
            self.technical_analysis or "—",
            "",
            "### News Analysis",
            self.news_analysis or "—",
            "",
            "### Pattern Analysis",
            self.pattern_analysis or "—",
            "",
            "### Risk Analysis",
            self.risk_analysis or "—",
            "",
            "### Probability Analysis",
            self.probability_analysis or "—",
            "",
            "### Why this prediction was generated",
        ]
        for w in self.why:
            lines.append(f"- {w}")
        lines.extend(["", "### Rejected / de-emphasized signals"])
        for r in self.rejected:
            lines.append(f"- {r}")
        lines.extend(["", "### What could invalidate this prediction"])
        for i in self.invalidation:
            lines.append(f"- {i}")
        lines.extend(["", "### Targets"])
        for t in self.targets:
            lines.append(f"- {t}")
        lines.append("")
        lines.append(f"### Stop-loss / invalidation level\n{self.stop_loss or '—'}")
        lines.extend(["", "### Alternative scenarios"])
        for a in self.alternative_scenarios:
            lines.append(f"- {a}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_summary": self.market_summary,
            "current_trend": self.current_trend,
            "technical_analysis": self.technical_analysis,
            "news_analysis": self.news_analysis,
            "pattern_analysis": self.pattern_analysis,
            "risk_analysis": self.risk_analysis,
            "probability_analysis": self.probability_analysis,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "why": self.why,
            "rejected": self.rejected,
            "invalidation": self.invalidation,
            "targets": self.targets,
            "stop_loss": self.stop_loss,
            "alternative_scenarios": self.alternative_scenarios,
            "sections": self.sections,
        }


@dataclass
class AnalystResult:
    """Complete analyst output returned to the app layer."""

    signal: str
    confidence: float
    predicted_price: float
    target_price: float
    stop_loss: float
    price_low: float
    price_high: float
    trend: str
    risk_level: str
    score: float
    market_regime: str
    regime: MarketRegimeState | None = None
    factors: list[EvidenceFactor] = field(default_factory=list)
    news_impacts: list[NewsImpactItem] = field(default_factory=list)
    scenarios: list[ScenarioPath] = field(default_factory=list)
    report: AnalystReport | None = None
    context: dict[str, Any] = field(default_factory=dict)
    preferred_indicators: list[str] = field(default_factory=list)
    chart_patterns: list[str] = field(default_factory=list)
    candle_patterns: list[str] = field(default_factory=list)
    memory_adjustment: dict[str, Any] = field(default_factory=dict)
    risk_plan: dict[str, Any] = field(default_factory=dict)
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    source: str = "ANALYST"

    @property
    def accepted_factors(self) -> list[EvidenceFactor]:
        return [f for f in self.factors if f.accepted]

    @property
    def rejected_factors(self) -> list[EvidenceFactor]:
        return [f for f in self.factors if not f.accepted]
