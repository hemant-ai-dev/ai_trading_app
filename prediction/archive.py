"""SQLite-backed prediction archive. Append-only; never overwrites older rows."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from db.database import execute, fetch_all, fetch_one
from prediction.models import PredictionResult

STRATEGY_VERSION = "angad-analyst-v1"


def last_saved_at(user_id: int, symbol: str) -> datetime | None:
    row = fetch_one(
        """
        SELECT CreatedAt FROM TPrediction
        WHERE UserId = ? AND Symbol = ?
        ORDER BY PredictionId DESC LIMIT 1
        """,
        (int(user_id), symbol.upper()),
    )
    if not row:
        return None
    try:
        return datetime.fromisoformat(str(row["CreatedAt"]).replace("Z", "+00:00"))
    except ValueError:
        return None


def save_prediction(
    *,
    user_id: int,
    symbol: str,
    result: PredictionResult,
    market_price: float,
    horizon: str,
    min_interval_seconds: int = 55,
) -> int | None:
    """Append a prediction unless one was stored for this user/symbol very recently."""
    last = last_saved_at(user_id, symbol)
    now = datetime.now(timezone.utc)
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < timedelta(seconds=min_interval_seconds):
            return None
    snap = result.indicator_snapshot or {}
    features = {
        "rsi": snap.get("rsi"),
        "macd": snap.get("macd"),
        "ema9": snap.get("ema9"),
        "ema20": snap.get("ema20"),
        "vwap": snap.get("vwap"),
        "atr": snap.get("atr"),
        "adx": snap.get("adx"),
        "trend": snap.get("trend_dir") or result.trend,
    }
    proj = []
    if result.projection_series is not None and len(result.projection_series):
        for ts, px in list(result.projection_series.items())[:40]:
            proj.append({"t": str(ts), "p": float(px)})
    pid = execute(
        """
        INSERT INTO TPrediction (
            UserId, Symbol, Exchange, MarketPrice, Horizon, PredictedPrice, PriceLow, PriceHigh,
            Direction, Signal, Confidence, StrategyVersion, MarketRegime, FeaturesJson, RiskLevel,
            ReasonsJson, ProjectionJson
        ) VALUES (?, ?, 'NSE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            symbol.upper(),
            float(market_price),
            horizon,
            float(result.predicted_price),
            float(result.price_low),
            float(result.price_high),
            result.trend,
            result.signal,
            float(result.confidence),
            STRATEGY_VERSION,
            result.market_regime,
            json.dumps(features, default=str),
            result.risk_level,
            json.dumps(result.reasons_simple or result.reasons, default=str),
            json.dumps(proj, default=str),
        ),
    )
    return int(pid)


def list_predictions(user_id: int, symbol: str | None = None, *, limit: int = 120) -> list[dict[str, Any]]:
    if symbol:
        return fetch_all(
            """
            SELECT * FROM TPrediction WHERE UserId = ? AND Symbol = ?
            ORDER BY PredictionId DESC LIMIT ?
            """,
            (int(user_id), symbol.upper(), int(limit)),
        )
    return fetch_all(
        "SELECT * FROM TPrediction WHERE UserId = ? ORDER BY PredictionId DESC LIMIT ?",
        (int(user_id), int(limit)),
    )


def backfill_actuals(user_id: int, symbol: str, current_price: float, min_age_minutes: int = 5) -> int:
    rows = fetch_all(
        """
        SELECT PredictionId, CreatedAt FROM TPrediction
        WHERE UserId = ? AND Symbol = ? AND ActualPrice IS NULL
        """,
        (int(user_id), symbol.upper()),
    )
    updated = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        try:
            created = datetime.fromisoformat(str(row["CreatedAt"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if now - created < timedelta(minutes=min_age_minutes):
            continue
        execute(
            "UPDATE TPrediction SET ActualPrice = ? WHERE PredictionId = ?",
            (float(current_price), int(row["PredictionId"])),
        )
        updated += 1
    return updated
