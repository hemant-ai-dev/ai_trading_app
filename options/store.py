"""Append-only option prediction ticks — JSON tape plus SQLite archive (never overwrites older rows)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from db.database import execute, execute_count, fetch_all
from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)

OPTION_TARGET_MINUTES = 1  # premium forecast is for the next tape observation
OPTION_EVAL_TOLERANCE_MIN = 10  # first snapshot after target, up to this late, is the actual


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _parse_iso(v: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


class OptionPredictionStore:
    def __init__(self, prediction_store_path: Path | str) -> None:
        base = Path(prediction_store_path)
        self.path = base.with_name(base.stem + "_options.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read option predictions: %s", exc)
            return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)

    def last_action(self, underlying: str, contract: str | None) -> str | None:
        rows = [r for r in self._load() if str(r.get("underlying")) == underlying.upper()]
        if contract:
            rows = [r for r in rows if str(r.get("contract") or "") == contract]
        if not rows:
            return None
        return str(rows[-1].get("action") or "")

    def append(self, payload: dict[str, Any], *, user_id: int | None = None) -> dict[str, Any]:
        now = datetime.now(IST)
        rows = self._load()
        last = None
        for r in reversed(self._load()):
            if str(r.get("underlying")) == str(payload.get("underlying") or "").upper() and str(r.get("contract") or "") == str(payload.get("contract") or ""):
                last = r
                break
        if last:
            try:
                prev = datetime.fromisoformat(str(last["ts"]))
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=IST)
                if now - prev < timedelta(seconds=50):
                    return last
            except (TypeError, ValueError):
                pass
        row = dict(payload)
        row.setdefault("prediction_id", uuid4().hex[:12])
        row.setdefault("ts", datetime.now(IST).isoformat())
        rows.append(row)
        if len(rows) > 6000:
            rows = rows[-6000:]
        self._save(rows)
        if user_id:
            try:
                self._archive(row, int(user_id))
            except Exception as exc:
                logger.warning("Option prediction SQLite mirror failed: %s", exc)
        return row

    @staticmethod
    def _archive(row: dict[str, Any], user_id: int) -> None:
        ts = datetime.fromisoformat(str(row["ts"]))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        target = ts + timedelta(minutes=OPTION_TARGET_MINUTES)
        execute(
            """
            INSERT INTO TOptionPrediction (
                UserId, Underlying, UnderlyingPrice, Expiry, OptionType, Strike, Contract,
                OptionPremium, PredictedPremium, PredictedUnderlying, Horizon, StopLoss,
                TargetPrice, Action, Signal, Confidence, MarketRegime, ModelVersion,
                ReasonsJson, TargetTime, Status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                user_id,
                str(row.get("underlying") or "").upper(),
                _f(row.get("spot")),
                str(row.get("expiry") or ""),
                str(row.get("option_type") or ""),
                _f(row.get("strike")),
                str(row.get("contract") or ""),
                _f(row.get("actual_premium")),
                _f(row.get("predicted_premium")),
                _f(row.get("predicted_underlying")),
                str(row.get("horizon") or "1m"),
                _f(row.get("stop")),
                _f(row.get("target")),
                str(row.get("action") or ""),
                str(row.get("signal") or ""),
                _f(row.get("confidence")),
                str(row.get("market_regime") or ""),
                str(row.get("model_version") or ""),
                json.dumps(row.get("reasons") or [], default=str),
                target.astimezone(IST).isoformat(),
            ),
        )

    def evaluate_due(
        self,
        *,
        user_id: int,
        underlying: str,
        premiums: dict[str, float],
        spot: float | None,
        now_ist: datetime | None = None,
    ) -> int:
        """Evaluate pending archived option predictions against a live chain snapshot.

        `premiums` maps contract symbol -> observed LTP. A row is evaluated only when
        its TargetTime has passed and a later snapshot actually carries that contract;
        pending rows are never marked right or wrong on stale or missing data.
        """
        now_ist = now_ist or datetime.now(IST)
        due = fetch_all(
            """
            SELECT * FROM TOptionPrediction
            WHERE UserId = ? AND Underlying = ? AND Status = 'pending'
              AND TargetTime IS NOT NULL
            ORDER BY CreatedAt DESC LIMIT 200
            """,
            (int(user_id), underlying.upper()),
        )
        evaluated = 0
        for row in due:
            target = _parse_iso(row.get("TargetTime"))
            if target is None:
                continue
            if target > now_ist:
                continue
            if (now_ist - target) > timedelta(minutes=OPTION_EVAL_TOLERANCE_MIN):
                continue  # too old to attribute this snapshot to the target
            contract = str(row.get("Contract") or "")
            actual = premiums.get(contract)
            if actual is None:
                continue
            predicted = _f(row.get("PredictedPremium"))
            at_gen = _f(row.get("OptionPremium"))
            abs_err = round(abs(float(actual) - float(predicted)), 4) if predicted is not None else None
            err_pct = (
                round(abs_err / float(predicted) * 100.0, 4)
                if abs_err is not None and predicted
                else None
            )
            direction_ok = None
            if predicted is not None and at_gen and actual is not None:
                direction_ok = 1 if (float(predicted) - float(at_gen)) * (float(actual) - float(at_gen)) > 0 else 0
            evaluated += execute_count(
                """
                UPDATE TOptionPrediction SET
                    ActualPremium = ?, PredictionError = ?, AbsError = ?, ErrorPct = ?,
                    DirectionOk = ?, ActualUnderlying = ?, Status = 'evaluated',
                    EvaluatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE OptionPredictionId = ? AND Status = 'pending'
                """,
                (
                    float(actual),
                    (float(actual) - float(predicted)) if predicted is not None else None,
                    abs_err,
                    err_pct,
                    direction_ok,
                    float(spot) if spot is not None else None,
                    int(row["OptionPredictionId"]),
                ),
            )
        return evaluated

    def option_stats(self, user_id: int, underlying: str | None = None) -> dict[str, Any]:
        where = "UserId = ?"
        params: list[Any] = [int(user_id)]
        if underlying:
            where += " AND Underlying = ?"
            params.append(underlying.upper())
        totals = fetch_all(
            f"""
            SELECT Status, COUNT(*) AS n,
                   SUM(CASE WHEN DirectionOk = 1 THEN 1 ELSE 0 END) AS hits,
                   SUM(CASE WHEN DirectionOk IS NOT NULL THEN 1 ELSE 0 END) AS dir_total,
                   AVG(AbsError) AS mae, AVG(ErrorPct) AS mape
            FROM TOptionPrediction WHERE {where} GROUP BY Status
            """,
            tuple(params),
        )
        stats = {"total": 0, "pending": 0, "evaluated": 0, "direction_hits": 0, "direction_total": 0, "mae": None, "mape": None}
        mae_w = mape_w = 0.0
        for r in totals:
            n = int(r["n"] or 0)
            stats["total"] += n
            st = str(r.get("Status") or "pending")
            if st in ("pending", "evaluated"):
                stats[st] += n
            stats["direction_hits"] += int(r.get("hits") or 0)
            stats["direction_total"] += int(r.get("dir_total") or 0)
            if st == "evaluated" and r.get("mae") is not None:
                mae_w += float(r["mae"]) * n
                mape_w += float(r.get("mape") or 0) * n
        ev = stats["evaluated"]
        stats["direction_accuracy_pct"] = (
            round(100.0 * stats["direction_hits"] / stats["direction_total"], 1)
            if stats["direction_total"]
            else None
        )
        stats["mae"] = round(mae_w / ev, 4) if ev else None
        stats["mape"] = round(mape_w / ev, 4) if ev else None
        return stats

    def history(self, underlying: str | None = None, contract: str | None = None, limit: int = 80) -> pd.DataFrame:
        rows = self._load()
        if underlying:
            rows = [r for r in rows if str(r.get("underlying")) == underlying.upper()]
        if contract:
            rows = [r for r in rows if str(r.get("contract") or "") == contract]
        rows = rows[-limit:]
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def series(self, contract: str) -> dict[str, pd.Series]:
        rows = [r for r in self._load() if str(r.get("contract") or "") == contract]
        if not rows:
            empty = pd.Series(dtype=float)
            return {"predicted": empty, "actual": empty}
        idx, pred, act = [], [], []
        for r in rows:
            try:
                ts = pd.Timestamp(r["ts"])
                idx.append(ts)
                pred.append(float(r.get("predicted_premium") or 0))
                act.append(float(r.get("actual_premium") or 0))
            except (TypeError, ValueError, KeyError):
                continue
        return {
            "predicted": pd.Series(pred, index=pd.DatetimeIndex(idx), name="ai_premium"),
            "actual": pd.Series(act, index=pd.DatetimeIndex(idx), name="actual_premium"),
        }

    def performance(self, underlying: str | None = None) -> dict[str, Any]:
        df = self.history(underlying, limit=4000)
        if df.empty or "predicted_premium" not in df.columns:
            return {"count": 0, "direction_accuracy_pct": None, "avg_abs_error": None, "close": 0, "incorrect": 0}
        pred = pd.to_numeric(df["predicted_premium"], errors="coerce")
        act = pd.to_numeric(df["actual_premium"], errors="coerce")
        err = (pred - act).abs()
        close = int((err <= 2).sum())
        direction_ok = 0
        direction_n = 0
        acts = act.tolist()
        preds = pred.tolist()
        for i in range(1, len(df)):
            if pd.isna(preds[i]) or pd.isna(acts[i]) or pd.isna(acts[i - 1]):
                continue
            direction_n += 1
            if (preds[i] - acts[i - 1]) * (acts[i] - acts[i - 1]) > 0:
                direction_ok += 1
        return {
            "count": int(len(df)),
            "close": close,
            "incorrect": int(len(df) - close),
            "avg_abs_error": round(float(err.mean()), 4) if len(err) else None,
            "direction_accuracy_pct": round(direction_ok / direction_n * 100, 1) if direction_n else None,
        }
