"""Local JSON storage for prediction history."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from prediction.models import PredictionRecord, PredictionResult
from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)

DEFAULT_STORE = Path("data/storage/predictions.json")


class PredictionHistoryStore:
    """Persist predictions to a local JSON file."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_STORE)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read prediction history: %s", exc)
            return []

    def _save_all(self, records: list[dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

    def save_prediction(
        self,
        symbol: str,
        result: PredictionResult,
        *,
        actual_price: float | None = None,
    ) -> PredictionRecord:
        record = PredictionRecord(
            id=str(uuid.uuid4())[:12],
            symbol=symbol.upper(),
            timestamp=datetime.now(IST),
            signal=result.signal,
            confidence=result.confidence,
            predicted_price=result.predicted_price,
            target_price=result.target_price,
            stop_loss=result.stop_loss,
            actual_price=actual_price,
            source=result.source,
            reasons=result.reasons_simple or result.reasons,
        )
        all_records = self._load_all()
        all_records.append(record.to_dict())
        self._save_all(all_records)
        return record

    def update_actual_prices(self, symbol: str, current_price: float, min_age_minutes: int = 5) -> int:
        """Backfill actual prices for predictions old enough to evaluate."""
        from datetime import timedelta

        updated = 0
        all_records = self._load_all()
        now = datetime.now(IST)
        for row in all_records:
            if row.get("symbol") != symbol.upper():
                continue
            if row.get("actual_price") is not None:
                continue
            ts = datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=IST)
            if (now - ts) < timedelta(minutes=min_age_minutes):
                continue
            predicted = float(row["predicted_price"])
            row["actual_price"] = current_price
            if predicted > 0:
                row["error_pct"] = round(abs(current_price - predicted) / predicted * 100, 2)
            signal = row.get("signal", "HOLD")
            if signal == "BUY":
                row["win"] = current_price >= predicted * 0.99
            elif signal == "SELL":
                row["win"] = current_price <= predicted * 1.01
            else:
                row["win"] = row.get("error_pct", 100) <= 1.0
            updated += 1
        if updated:
            self._save_all(all_records)
        return updated

    def load_history(self, symbol: str | None = None, limit: int = 100) -> list[PredictionRecord]:
        records = [PredictionRecord.from_dict(r) for r in self._load_all()]
        if symbol:
            records = [r for r in records if r.symbol == symbol.upper()]
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def to_dataframe(self, symbol: str | None = None, limit: int = 100) -> pd.DataFrame:
        records = self.load_history(symbol, limit)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame([r.to_dict() for r in records])

    def load_projection_history(self, symbol: str, limit: int = 30) -> pd.DataFrame:
        """Return historical prediction metadata for chart overlays."""
        df = self.to_dataframe(symbol, limit)
        if df.empty:
            return df
        rows = []
        for _, row in df.iterrows():
            rows.append(
                {
                    "run_time": row["timestamp"],
                    "target_time": row["timestamp"],
                    "predicted_price": row["predicted_price"],
                    "signal": row["signal"],
                }
            )
        return pd.DataFrame(rows)
