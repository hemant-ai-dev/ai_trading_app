"""Prediction domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class PredictionResult:
    """Unified prediction output from any model."""

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
    reasons: list[str] = field(default_factory=list)
    reasons_simple: list[str] = field(default_factory=list)
    projection_series: pd.Series | None = None
    indicator_snapshot: dict[str, Any] = field(default_factory=dict)
    source: str = "RULE"
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "confidence": self.confidence,
            "predicted_price": self.predicted_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "price_low": self.price_low,
            "price_high": self.price_high,
            "trend": self.trend,
            "risk_level": self.risk_level,
            "score": self.score,
            "market_regime": self.market_regime,
            "reasons": self.reasons,
            "reasons_simple": self.reasons_simple,
            "source": self.source,
            "indicator_snapshot": self._serialize_snapshot(),
            "raw": self.raw,
        }

    def _serialize_snapshot(self) -> dict[str, Any]:
        snap = dict(self.indicator_snapshot)
        fib = snap.pop("fibonacci", None)
        if fib is not None and hasattr(fib, "retracements"):
            snap["fibonacci"] = {
                "swing_high": fib.swing_high,
                "swing_low": fib.swing_low,
                "trend": fib.trend,
                "retracements": fib.retracements,
                "extensions": fib.extensions,
                "nearest_support": fib.nearest_support,
                "nearest_resistance": fib.nearest_resistance,
            }
        return snap


@dataclass
class PredictionRecord:
    """Stored prediction for history and accuracy tracking."""

    id: str
    symbol: str
    timestamp: datetime
    signal: str
    confidence: float
    predicted_price: float
    target_price: float
    stop_loss: float
    actual_price: float | None = None
    error_pct: float | None = None
    win: bool | None = None
    source: str = "RULE"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "signal": self.signal,
            "confidence": self.confidence,
            "predicted_price": self.predicted_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "actual_price": self.actual_price,
            "error_pct": self.error_pct,
            "win": self.win,
            "source": self.source,
            "reasons": self.reasons,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionRecord":
        return cls(
            id=str(data["id"]),
            symbol=str(data["symbol"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            signal=str(data["signal"]),
            confidence=float(data["confidence"]),
            predicted_price=float(data["predicted_price"]),
            target_price=float(data["target_price"]),
            stop_loss=float(data["stop_loss"]),
            actual_price=float(data["actual_price"]) if data.get("actual_price") is not None else None,
            error_pct=float(data["error_pct"]) if data.get("error_pct") is not None else None,
            win=data.get("win"),
            source=str(data.get("source", "RULE")),
            reasons=list(data.get("reasons") or []),
        )
