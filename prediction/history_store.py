"""Local JSON storage for prediction history and chart overlays."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from prediction.models import PredictionRecord, PredictionResult
from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)

DEFAULT_STORE = Path("data/storage/predictions.json")


class PredictionHistoryStore:
    """Persist predictions to a local JSON file for history and accuracy."""

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
        market_price: float | None = None,
    ) -> PredictionRecord:
        """Append a prediction run with optional projection path for chart overlays."""
        now = datetime.now(IST)
        market_px = market_price
        if market_px is None and result.indicator_snapshot:
            ohlcv = result.indicator_snapshot.get("ohlcv") or {}
            market_px = ohlcv.get("close")

        projection_points: list[dict[str, Any]] = []
        pred_start = now.isoformat()
        pred_end = now.isoformat()
        if result.projection_series is not None and len(result.projection_series) > 0:
            series = result.projection_series
            pred_start = pd.Timestamp(series.index[0]).isoformat()
            pred_end = pd.Timestamp(series.index[-1]).isoformat()
            for ts, px in series.items():
                projection_points.append(
                    {
                        "target_time": pd.Timestamp(ts).isoformat(),
                        "predicted_price": float(px),
                    }
                )

        record_id = str(uuid.uuid4())[:12]
        record = PredictionRecord(
            id=record_id,
            symbol=symbol.upper(),
            timestamp=now,
            signal=result.signal,
            confidence=result.confidence,
            predicted_price=result.predicted_price,
            target_price=result.target_price,
            stop_loss=result.stop_loss,
            actual_price=actual_price,
            source=result.source,
            reasons=result.reasons_simple or result.reasons,
        )
        payload = record.to_dict()
        payload.update(
            {
                "market_price": market_px,
                "price_low": result.price_low,
                "price_high": result.price_high,
                "prediction_start": pred_start,
                "prediction_end": pred_end,
                "projection_points": projection_points,
                "profit_loss_pct": None,
                "accuracy_label": "Pending",
                "trend": result.trend,
                "risk_level": result.risk_level,
            }
        )
        all_records = self._load_all()
        all_records.append(payload)
        # Keep file bounded
        if len(all_records) > 2000:
            all_records = all_records[-2000:]
        self._save_all(all_records)
        return record

    def update_actual_prices(self, symbol: str, current_price: float, min_age_minutes: int = 5) -> int:
        """Backfill actual prices and P/L for predictions old enough to evaluate."""
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
                error = abs(current_price - predicted) / predicted * 100
                row["error_pct"] = round(error, 2)
                raw_pl = (current_price - predicted) / predicted * 100
            else:
                row["error_pct"] = None
                raw_pl = 0.0

            signal = row.get("signal", "HOLD")
            if signal == "BUY":
                row["win"] = current_price >= predicted * 0.99
                row["profit_loss_pct"] = round(raw_pl, 2)
            elif signal == "SELL":
                row["win"] = current_price <= predicted * 1.01
                row["profit_loss_pct"] = round(-raw_pl, 2)
            else:
                row["win"] = (row.get("error_pct") or 100) <= 1.0
                row["profit_loss_pct"] = round(-abs(raw_pl), 2)

            if row.get("error_pct") is not None and row["error_pct"] <= 1.0:
                row["accuracy_label"] = "Accurate (±1%)"
            elif row.get("win"):
                row["accuracy_label"] = "Direction correct"
            else:
                row["accuracy_label"] = "Incorrect"
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
        rows = self._load_all()
        if symbol:
            rows = [r for r in rows if r.get("symbol") == symbol.upper()]
        rows = sorted(rows, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
        if not rows:
            return pd.DataFrame()
        # Drop heavy nested fields for table view
        cleaned = []
        for r in rows:
            item = {k: v for k, v in r.items() if k != "projection_points"}
            cleaned.append(item)
        return pd.DataFrame(cleaned)

    def load_projection_history(self, symbol: str, limit: int = 30) -> pd.DataFrame:
        """Flatten stored projection paths for faint past-prediction chart overlays."""
        rows = self._load_all()
        rows = [r for r in rows if r.get("symbol") == symbol.upper()]
        rows = sorted(rows, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
        out: list[dict[str, Any]] = []
        for r in reversed(rows):
            points = r.get("projection_points") or []
            if points:
                for p in points:
                    out.append(
                        {
                            "run_time": r["timestamp"],
                            "target_time": p["target_time"],
                            "predicted_price": p["predicted_price"],
                            "signal": r.get("signal"),
                        }
                    )
            else:
                out.append(
                    {
                        "run_time": r["timestamp"],
                        "target_time": r.get("prediction_end") or r["timestamp"],
                        "predicted_price": r["predicted_price"],
                        "signal": r.get("signal"),
                    }
                )
        return pd.DataFrame(out) if out else pd.DataFrame()

    def load_comparison_records(self, symbol: str, limit: int = 12) -> list[dict[str, Any]]:
        """Return evaluated predictions for on-chart Correct/Incorrect annotations."""
        rows = self._load_all()
        rows = [
            r
            for r in rows
            if r.get("symbol") == symbol.upper() and r.get("actual_price") is not None
        ]
        rows = sorted(rows, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
        return list(reversed(rows))

    def latest_evaluated(self, symbol: str) -> dict[str, Any] | None:
        """Most recent evaluated prediction for the compare card."""
        rows = self.load_comparison_records(symbol, limit=1)
        return rows[-1] if rows else None
