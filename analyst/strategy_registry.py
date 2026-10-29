"""Strategy performance registry — evidence for selection, not auto-parameter tuning."""

from __future__ import annotations

import json
from typing import Any

from db.database import execute, fetch_all, fetch_one

MODEL_VERSION = "angad-analyst-v1"
MIN_SAMPLE = 20


def record_signal(strategy_id: str, strategy_name: str, regime: str, timeframe: str = "1d") -> None:
    regime = (regime or "unknown").replace(" ", "_")[:64]
    sid = (strategy_id or "Alpha")[:32]
    execute(
        """
        INSERT INTO TStrategyPerformance (
            StrategyId, StrategyName, ModelVersion, MarketRegime, Timeframe, Signals
        ) VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(StrategyId, MarketRegime, Timeframe) DO UPDATE SET
            Signals = Signals + 1,
            StrategyName = excluded.StrategyName,
            ModelVersion = excluded.ModelVersion,
            UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (sid, strategy_name or sid, MODEL_VERSION, regime, timeframe),
    )


def record_outcome(
    *,
    strategy_id: str,
    regime: str,
    timeframe: str,
    direction_ok: bool,
    abs_error: float,
    rr: float | None,
) -> None:
    regime = (regime or "unknown").replace(" ", "_")[:64]
    sid = (strategy_id or "Alpha")[:32]
    execute(
        """
        UPDATE TStrategyPerformance SET
            Completed = Completed + 1,
            Successful = Successful + CASE WHEN ? THEN 1 ELSE 0 END,
            Failed = Failed + CASE WHEN ? THEN 0 ELSE 1 END,
            DirectionHits = DirectionHits + CASE WHEN ? THEN 1 ELSE 0 END,
            DirectionTotal = DirectionTotal + 1,
            SumAbsError = SumAbsError + ?,
            SumRR = SumRR + ?,
            UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE StrategyId = ? AND MarketRegime = ? AND Timeframe = ?
        """,
        (
            1 if direction_ok else 0,
            1 if direction_ok else 0,
            1 if direction_ok else 0,
            float(abs_error or 0),
            float(rr or 0),
            sid,
            regime,
            timeframe,
        ),
    )


def snapshot(strategy_id: str, regime: str, timeframe: str = "1d") -> dict[str, Any]:
    regime = (regime or "unknown").replace(" ", "_")[:64]
    row = fetch_one(
        """
        SELECT * FROM TStrategyPerformance
        WHERE StrategyId = ? AND MarketRegime = ? AND Timeframe = ?
        """,
        ((strategy_id or "Alpha")[:32], regime, timeframe),
    )
    if not row:
        return {
            "strategy_id": strategy_id,
            "completed": 0,
            "validated": False,
            "direction_accuracy_pct": None,
            "note": f"Fewer than {MIN_SAMPLE} completed observations — not treated as validated.",
        }
    completed = int(row["Completed"] or 0)
    dt = int(row["DirectionTotal"] or 0)
    acc = round(100.0 * int(row["DirectionHits"] or 0) / dt, 1) if dt else None
    avg_err = round(float(row["SumAbsError"] or 0) / completed, 4) if completed else None
    return {
        "strategy_id": row["StrategyId"],
        "strategy_name": row["StrategyName"],
        "regime": row["MarketRegime"],
        "signals": int(row["Signals"] or 0),
        "completed": completed,
        "successful": int(row["Successful"] or 0),
        "failed": int(row["Failed"] or 0),
        "direction_accuracy_pct": acc,
        "avg_abs_error": avg_err,
        "validated": completed >= MIN_SAMPLE,
        "min_sample": MIN_SAMPLE,
        "note": (
            f"Based on {completed} completed setups in this regime (not a guarantee)."
            if completed
            else f"Need {MIN_SAMPLE} completed observations before treating this strategy as validated."
        ),
    }


def _recent_direction_pct(strategy_id: str, regime: str, timeframe: str, window: int = 20) -> tuple[int, float | None]:
    """Hit rate on the latest completed forecasts for this strategy, regime, and timeframe.

    Returns (sample, percent). Percent is None until 10 completed rows exist,
    so a short hot streak cannot override the longer record.
    """
    rows = fetch_all(
        """
        SELECT DirectionOk, FeaturesJson FROM TPrediction
        WHERE Status = 'evaluated' AND MarketRegime = ? AND Timeframe = ?
        ORDER BY PredictionId DESC LIMIT 120
        """,
        (regime, timeframe),
    )
    hits = total = 0
    sid = (strategy_id or "Alpha")[:32]
    for row in rows:
        try:
            feats = json.loads(row.get("FeaturesJson") or "{}")
        except (TypeError, json.JSONDecodeError):
            feats = {}
        if str(feats.get("strategy_id") or "Alpha")[:32] != sid:
            continue
        if row.get("DirectionOk") is None:
            continue
        total += 1
        hits += int(row["DirectionOk"])
        if total >= window:
            break
    if total < 10:
        return total, None
    return total, round(100.0 * hits / total, 1)


def choose_primary(default_id: str, regime: str, timeframe: str, candidates: list[str]) -> tuple[str, dict[str, Any]]:
    """Pick among candidates only when sample size is met. Never from one trade.

    A candidate whose recent hit rate is at least 15 points below its longer
    record is skipped. Recent deterioration is a reason to stay uncertain,
    not a reason to flip to the last winner.
    """
    default_id = default_id or "Alpha"
    best = None
    skipped_recent: list[str] = []
    for sid in candidates:
        snap = snapshot(sid, regime, timeframe)
        if not snap.get("validated"):
            continue
        acc = snap.get("direction_accuracy_pct")
        if acc is None:
            continue
        recent_n, recent_acc = _recent_direction_pct(sid, (regime or "unknown").replace(" ", "_")[:64], timeframe)
        if recent_acc is not None and acc - recent_acc >= 15:
            skipped_recent.append(sid)
            continue
        snap = dict(snap)
        snap["recent_completed"] = recent_n
        snap["recent_direction_accuracy_pct"] = recent_acc
        if best is None or acc > best[0]:
            best = (acc, sid, snap)
    if best is None:
        note = "Regime default used — not enough validated history to override."
        if skipped_recent:
            note = (
                "Regime default used — validated candidates "
                + ", ".join(skipped_recent)
                + " have weaker recent results than their longer record."
            )
        return default_id, snapshot(default_id, regime, timeframe) | {
            "used_evidence": False,
            "selection_note": note,
        }
    return best[1], best[2] | {
        "used_evidence": True,
        "selection_note": (
            f"Selected {best[1]} from {best[2].get('completed')} completed setups "
            f"in this regime (recent accuracy {best[2].get('recent_direction_accuracy_pct')}). "
            "Historical accuracy is not a profit guarantee."
        ),
    }


def list_registry(limit: int = 40) -> list[dict[str, Any]]:
    return fetch_all(
        "SELECT * FROM TStrategyPerformance ORDER BY UpdatedAt DESC LIMIT ?",
        (int(limit),),
    )
