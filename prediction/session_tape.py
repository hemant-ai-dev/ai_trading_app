"""Minute-by-minute AI vs actual prints for one market session."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)


class SessionTapeStore:
    """Append-only session ticks so yellow AI prints can be compared to the tape."""

    def __init__(self, prediction_store_path: Path | str) -> None:
        base = Path(prediction_store_path)
        self.path = base.with_name(base.stem + "_session.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read session tape: %s", exc)
            return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)

    def append(
        self,
        *,
        symbol: str,
        predicted_price: float,
        actual_price: float,
        signal: str,
        confidence: float,
        now: datetime | None = None,
        min_interval_seconds: int = 50,
    ) -> dict[str, Any] | None:
        now = now or datetime.now(IST)
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        else:
            now = now.astimezone(IST)
        sym = symbol.upper()
        rows = self._load()
        last = next((r for r in reversed(rows) if str(r.get("symbol")) == sym), None)
        if last:
            try:
                prev = datetime.fromisoformat(str(last["ts"]))
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=IST)
                if now - prev < timedelta(seconds=min_interval_seconds):
                    return last
            except (TypeError, ValueError, KeyError):
                pass
        tick = {
            "symbol": sym,
            "ts": now.isoformat(),
            "session_date": now.date().isoformat(),
            "predicted_price": round(float(predicted_price), 4),
            "actual_price": round(float(actual_price), 4),
            "signal": str(signal or "").upper(),
            "confidence": float(confidence or 0),
        }
        rows.append(tick)
        if len(rows) > 8000:
            rows = rows[-8000:]
        self._save(rows)
        return tick

    def rows_for(self, symbol: str, day: date | None = None) -> list[dict[str, Any]]:
        sym = symbol.upper()
        want = day.isoformat() if day else None
        rows = [r for r in self._load() if str(r.get("symbol")) == sym]
        if want:
            rows = [r for r in rows if str(r.get("session_date")) == want]
        return rows

    def comparison_table(self, symbol: str, day: date | None = None, limit: int = 40) -> pd.DataFrame:
        rows = self.rows_for(symbol, day)
        out = []
        prev_actual = None
        prev_pred = None
        for r in rows:
            pred = float(r["predicted_price"])
            act = float(r["actual_price"])
            diff = pred - act
            pct = (diff / act * 100) if act else 0.0
            abs_pct = abs(pct)
            if abs_pct <= 0.12:
                label = "Close"
            elif diff > 0:
                label = "Higher than actual"
            else:
                label = "Lower than actual"
            direction = "—"
            if prev_actual is not None:
                pred_dir = (pred - prev_actual)
                act_dir = (act - prev_actual)
                if pred_dir == 0 or act_dir == 0:
                    direction = "Flat"
                elif (pred_dir > 0) == (act_dir > 0):
                    direction = "Correct direction"
                else:
                    direction = "Incorrect"
            out.append(
                {
                    "Time": r["ts"],
                    "AI predicted": round(pred, 2),
                    "Actual": round(act, 2),
                    "Difference": round(diff, 2),
                    "Error %": round(pct, 3),
                    "Result": label,
                    "Direction": direction,
                    "Signal": r.get("signal"),
                    "Confidence": r.get("confidence"),
                }
            )
            prev_actual = act
            prev_pred = pred
        df = pd.DataFrame(out)
        if df.empty:
            return df
        return df.tail(limit)

    def performance(self, symbol: str, day: date | None = None) -> dict[str, Any]:
        table = self.comparison_table(symbol, day, limit=5000)
        empty = {
            "count": 0,
            "close": 0,
            "higher": 0,
            "lower": 0,
            "direction_correct": 0,
            "direction_incorrect": 0,
            "avg_abs_error": None,
            "avg_error_pct": None,
            "accuracy_close_pct": None,
            "direction_accuracy_pct": None,
            "horizons": {},
        }
        if table.empty:
            return empty
        close_n = int((table["Result"] == "Close").sum())
        high_n = int((table["Result"] == "Higher than actual").sum())
        low_n = int((table["Result"] == "Lower than actual").sum())
        dir_ok = int((table["Direction"] == "Correct direction").sum())
        dir_bad = int((table["Direction"] == "Incorrect").sum())
        n = len(table)
        dir_n = dir_ok + dir_bad
        return {
            "count": n,
            "close": close_n,
            "higher": high_n,
            "lower": low_n,
            "direction_correct": dir_ok,
            "direction_incorrect": dir_bad,
            "avg_abs_error": round(float(table["Difference"].abs().mean()), 4),
            "avg_error_pct": round(float(table["Error %"].abs().mean()), 4),
            "accuracy_close_pct": round(close_n / n * 100, 1) if n else None,
            "direction_accuracy_pct": round(dir_ok / dir_n * 100, 1) if dir_n else None,
            "horizons": self._horizon_stats(symbol, day),
        }

    def _horizon_stats(self, symbol: str, day: date | None) -> dict[str, dict[str, Any]]:
        rows = self.rows_for(symbol, day)
        parsed = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["ts"]))
                parsed.append((ts, float(r["predicted_price"]), float(r["actual_price"])))
            except (TypeError, ValueError, KeyError):
                continue
        out: dict[str, dict[str, Any]] = {}
        for label, minutes in (("1m", 1), ("5m", 5), ("15m", 15), ("30m", 30), ("intraday", 0)):
            hits, ok = 0, 0
            errors = []
            for i, (ts, pred, _act) in enumerate(parsed):
                if label == "intraday":
                    later = parsed[-1] if parsed else None
                    if later is None or later[0] <= ts:
                        continue
                    actual_later = later[2]
                else:
                    target = ts + timedelta(minutes=minutes)
                    actual_later = None
                    for ts2, _p2, a2 in parsed[i + 1 :]:
                        if abs((ts2 - target).total_seconds()) <= 90:
                            actual_later = a2
                            break
                        if ts2 > target + timedelta(minutes=2):
                            break
                    if actual_later is None:
                        continue
                hits += 1
                errors.append(abs(pred - actual_later))
                if i > 0:
                    prev_spot = parsed[i][2]
                    if (pred - prev_spot) * (actual_later - prev_spot) > 0:
                        ok += 1
            out[label] = {
                "pairs": hits,
                "avg_abs_error": round(sum(errors) / len(errors), 4) if errors else None,
                "direction_accuracy_pct": round(ok / hits * 100, 1) if hits else None,
            }
        return out

    def series_for(self, symbol: str, day: date | None = None) -> dict[str, pd.Series]:
        """Predicted vs actual prints for a session day (IST)."""
        sym = symbol.upper()
        want = day.isoformat() if day else None
        rows = [r for r in self._load() if str(r.get("symbol")) == sym]
        if want:
            rows = [r for r in rows if str(r.get("session_date")) == want]
        if not rows:
            empty = pd.Series(dtype=float)
            return {"predicted": empty, "actual": empty}
        idx, pred, act = [], [], []
        for r in rows:
            try:
                ts = pd.Timestamp(r["ts"])
                if ts.tzinfo is None:
                    ts = ts.tz_localize(IST)
                else:
                    ts = ts.tz_convert(IST)
                idx.append(ts)
                pred.append(float(r["predicted_price"]))
                act.append(float(r["actual_price"]))
            except (TypeError, ValueError, KeyError):
                continue
        if not idx:
            empty = pd.Series(dtype=float)
            return {"predicted": empty, "actual": empty}
        return {
            "predicted": pd.Series(pred, index=pd.DatetimeIndex(idx), name="ai_predicted"),
            "actual": pd.Series(act, index=pd.DatetimeIndex(idx), name="actual_print"),
        }
