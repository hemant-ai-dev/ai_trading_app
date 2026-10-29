"""SQLite-backed prediction archive — durable store for the yellow AI line.

Evaluation conventions (documented, used everywhere):
  base     = MarketPrice (price when the prediction was generated)
  pred     = PredictedPrice, actual = ActualPrice at TargetTime
  SignedError = actual - pred
  AbsError    = |actual - pred|
  ErrorPct    = AbsError / |base| * 100   (denominator = price at prediction time)
  DirectionOk = sign(pred - base) == sign(actual - base) with a sideways band;
                for HOLD-like forecasts (|pred-base| <= band) it is correct when
                |actual - base| <= band.
  RangeOk   = PriceLow <= actual <= PriceHigh
Directional correctness and numerical accuracy are measured separately.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from db.database import execute, execute_count, fetch_all, fetch_one
from prediction.models import PredictionResult
from utils.logging import get_logger

logger = get_logger(__name__)

STRATEGY_VERSION = "angad-analyst-v1"
MODEL_VERSION = "angad-horizon-v1"
# Sideways band: move smaller than 0.08% of base price is treated as flat.
SIDEWAYS_PCT = 0.08
# An actual bar must be within this many minutes of the target time to evaluate.
TARGET_TOLERANCE_MIN = 8


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def make_scheduled_key(user_id: int, symbol: str, horizon: str, gen_minute: datetime) -> str:
    """One job per instrument, horizon and scheduled minute — duplicate-proof."""
    return f"{int(user_id)}|{symbol.upper()}|{horizon}|{gen_minute.strftime('%Y%m%d%H%M')}"


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
    return _parse_ts(row["CreatedAt"])


def save_prediction(
    *,
    user_id: int,
    symbol: str,
    result: PredictionResult,
    market_price: float,
    horizon: str,
    min_interval_seconds: int = 55,
    timeframe: str | None = None,
    target_time: datetime | None = None,
    scheduled_key: str | None = None,
    model_version: str = MODEL_VERSION,
    probs: tuple[float, float, float] | None = None,
    prob_source: str = "score_derived_uncalibrated",
    strategy_id: str | None = None,
) -> int | None:
    """Append a prediction. With ``scheduled_key`` the insert is idempotent;
    without it, a 55-second window prevents UI-refresh duplicates."""
    now = datetime.now(timezone.utc)
    if scheduled_key:
        if last_saved_key_exists(scheduled_key):
            return None
    else:
        last = last_saved_at(user_id, symbol)
        if last is not None and now - last < timedelta(seconds=min_interval_seconds):
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
        "strategy_id": strategy_id
        or (result.raw or {}).get("trade_plan", {}).get("strategy_id")
        or (result.raw or {}).get("strategies", {}).get("primary_strategy"),
        "master_regime": (result.raw or {}).get("strategies", {}).get("master_regime") or result.market_regime,
        "rr": (result.raw or {}).get("trade_plan", {}).get("rr"),
        "score": result.score,
        "prob_source": prob_source if probs else None,
        "confidence_interpretation": (
            "uncalibrated_score"
            if probs and "uncalibrated" in (prob_source or "")
            else "rule_confidence"
        ),
        "vwap_slope": snap.get("vwap_slope"),
        "breakout_up": snap.get("breakout_up"),
        "breakdown": snap.get("breakdown"),
    }
    proj = []
    if result.projection_series is not None and len(result.projection_series):
        for ts, px in list(result.projection_series.items())[:40]:
            proj.append({"t": str(ts), "p": float(px)})

    if target_time is None and proj:
        target_time = _parse_ts(proj[-1]["t"])

    tf = timeframe or (horizon.split("/")[-1] if "/" in horizon else horizon) or "1d"
    params = (
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
        tf,
        _iso(target_time) if target_time else None,
        model_version,
        probs[0] if probs else None,
        probs[1] if probs else None,
        probs[2] if probs else None,
        scheduled_key,
    )
    if scheduled_key:
        pid = execute(
            """
            INSERT OR IGNORE INTO TPrediction (
                UserId, Symbol, Exchange, MarketPrice, Horizon, PredictedPrice, PriceLow, PriceHigh,
                Direction, Signal, Confidence, StrategyVersion, MarketRegime, FeaturesJson, RiskLevel,
                ReasonsJson, ProjectionJson, Timeframe, TargetTime, ModelVersion,
                ProbUp, ProbSideways, ProbDown, ScheduledKey, Status
            ) VALUES (?, ?, 'NSE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            params,
        )
    else:
        pid = execute(
            """
            INSERT INTO TPrediction (
                UserId, Symbol, Exchange, MarketPrice, Horizon, PredictedPrice, PriceLow, PriceHigh,
                Direction, Signal, Confidence, StrategyVersion, MarketRegime, FeaturesJson, RiskLevel,
                ReasonsJson, ProjectionJson, Timeframe, TargetTime, ModelVersion,
                ProbUp, ProbSideways, ProbDown, ScheduledKey, Status
            ) VALUES (?, ?, 'NSE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            params,
        )
    if not pid:
        return None
    try:
        from prediction.audit import log_decision

        log_decision(
            user_id=user_id,
            action="prediction_saved",
            instrument=symbol,
            prediction_id=int(pid),
            strategy_id=str(features.get("strategy_id") or ""),
            model_version=model_version,
            regime=result.market_regime,
            detail={"horizon": tf, "scheduled_key": scheduled_key, "signal": result.signal},
        )
        prev = fetch_one(
            """
            SELECT PredictionId, MarketRegime FROM TPrediction
            WHERE UserId = ? AND Symbol = ? AND PredictionId < ?
            ORDER BY PredictionId DESC LIMIT 1
            """,
            (int(user_id), symbol.upper(), int(pid)),
        )
        if prev and str(prev.get("MarketRegime") or "") != str(result.market_regime or ""):
            log_decision(
                user_id=user_id,
                action="regime_revision",
                instrument=symbol,
                prediction_id=int(pid),
                regime=result.market_regime,
                detail={
                    "previous_prediction_id": prev.get("PredictionId"),
                    "previous_regime": prev.get("MarketRegime"),
                    "new_regime": result.market_regime,
                    "note": "Original row kept; this is a new stored forecast.",
                },
            )
    except Exception:
        pass
    return int(pid)


def last_saved_key_exists(scheduled_key: str) -> bool:
    row = fetch_one("SELECT 1 FROM TPrediction WHERE ScheduledKey = ?", (scheduled_key,))
    return row is not None


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


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def pending_due(user_id: int, symbol: str, now_utc: datetime) -> list[dict[str, Any]]:
    """Predictions whose target horizon has completed and await actual data."""
    rows = fetch_all(
        """
        SELECT * FROM TPrediction
        WHERE UserId = ? AND Symbol = ? AND Status = 'pending' AND TargetTime IS NOT NULL
        """,
        (int(user_id), symbol.upper()),
    )
    return [r for r in rows if (_parse_ts(r["TargetTime"]) or now_utc) <= now_utc]


def _actual_at(bars, target_utc: datetime) -> dict[str, float] | None:
    """Close/High/Low of the bar nearest the target time, within tolerance.

    Naive bar timestamps are interpreted as IST exchange wall time (Yahoo bars
    are delivered tz-stripped in Asia/Kolkata).
    """
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
    if bars is None or len(bars) == 0:
        return None
    best = None
    best_gap = None
    for ts, row in bars.iterrows():
        ts_utc = ts
        if getattr(ts_utc.tzinfo, "utcoffset", lambda: None)() is None:
            ts_utc = ts_utc.replace(tzinfo=IST).astimezone(timezone.utc)
        else:
            ts_utc = ts_utc.astimezone(timezone.utc)
        gap = abs((ts_utc - target_utc).total_seconds())
        if best_gap is None or gap < best_gap:
            best_gap, best = gap, (ts_utc, row)
    if best is None or best_gap > TARGET_TOLERANCE_MIN * 60:
        return None
    ts_utc, row = best
    return {
        "time": _iso(ts_utc),
        "close": float(row["Close"]),
        "high": float(row.get("High", row["Close"])),
        "low": float(row.get("Low", row["Close"])),
    }


def evaluate_row(row: dict[str, Any], actual: dict[str, float]) -> dict[str, Any]:
    """Compute all evaluation metrics for one stored prediction (pure function)."""
    base = float(row.get("MarketPrice") or 0)
    pred = float(row.get("PredictedPrice") or 0)
    a = float(actual["close"])
    signed = round(a - pred, 4)
    abs_err = abs(signed)
    err_pct = round(100.0 * abs_err / base, 4) if base else None
    band = base * SIDEWAYS_PCT / 100.0
    pred_move = pred - base
    actual_move = a - base
    if abs(pred_move) <= band:
        direction_ok = abs(actual_move) <= band
    else:
        direction_ok = (pred_move > 0 and actual_move > band) or (pred_move < 0 and actual_move < -band)
    low, high = row.get("PriceLow"), row.get("PriceHigh")
    range_ok = bool(low is not None and high is not None and float(low) <= a <= float(high))
    return {
        "actual_price": a,
        "actual_time": actual["time"],
        "actual_high": actual["high"],
        "actual_low": actual["low"],
        "signed_error": signed,
        "abs_error": round(abs_err, 4),
        "error_pct": err_pct,
        "direction_ok": 1 if direction_ok else 0,
        "range_ok": 1 if range_ok else 0,
    }


def evaluate_due(user_id: int, symbol: str, bars, now_utc: datetime | None = None) -> int:
    """Evaluate pending predictions against real bars at their target timestamps.

    ``bars`` must be a timestamped OHLC DataFrame of the same instrument.
    Rows whose target time is not yet covered by reliable data stay pending.
    Idempotent: each row is only evaluated while Status='pending'.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    updated = 0
    for row in pending_due(user_id, symbol, now_utc):
        target = _parse_ts(row["TargetTime"])
        if target is None:
            continue
        actual = _actual_at(bars, target)
        if actual is None:
            continue  # stale/missing data — never mark success/failure falsely
        m = evaluate_row(row, actual)
        changed = execute_count(
            """
            UPDATE TPrediction SET
                ActualPrice = ?, ActualTime = ?, ActualHigh = ?, ActualLow = ?,
                SignedError = ?, AbsError = ?, ErrorPct = ?, DirectionOk = ?, RangeOk = ?,
                Status = 'evaluated', EvaluatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE PredictionId = ? AND Status = 'pending'
            """,
            (
                m["actual_price"], m["actual_time"], m["actual_high"], m["actual_low"],
                m["signed_error"], m["abs_error"], m["error_pct"], m["direction_ok"], m["range_ok"],
                int(row["PredictionId"]),
            ),
        )
        if not changed:
            continue
        updated += 1
        _record_strategy_outcome(row, m)
        try:
            from prediction.audit import log_decision

            log_decision(
                user_id=user_id,
                action="prediction_evaluated",
                instrument=symbol,
                prediction_id=int(row["PredictionId"]),
                model_version=str(row.get("ModelVersion") or ""),
                regime=str(row.get("MarketRegime") or ""),
                detail={
                    "direction_ok": m["direction_ok"],
                    "abs_error": m["abs_error"],
                    "range_ok": m["range_ok"],
                    "actual": m["actual_price"],
                },
            )
        except Exception:
            pass
    return updated


def _record_strategy_outcome(row: dict[str, Any], metrics: dict[str, Any]) -> None:
    try:
        from analyst.strategy_registry import record_outcome

        feats = {}
        raw = row.get("FeaturesJson")
        if raw:
            feats = json.loads(raw) if isinstance(raw, str) else dict(raw)
        record_outcome(
            strategy_id=str(feats.get("strategy_id") or "Alpha"),
            regime=str(feats.get("master_regime") or row.get("MarketRegime") or "unknown"),
            timeframe=str(row.get("Timeframe") or "1d"),
            direction_ok=bool(metrics["direction_ok"]),
            abs_error=float(metrics["abs_error"] or 0),
            rr=feats.get("rr"),
        )
    except Exception as exc:  # registry must never break evaluation
        logger.warning("strategy outcome record failed: %s", exc)


def backfill_actuals(user_id: int, symbol: str, current_price: float, min_age_minutes: int = 5) -> int:
    """Legacy rows (no TargetTime) get the price seen at backfill time.

    Rows saved with a TargetTime are evaluated only by ``evaluate_due`` so the
    original forecast is compared against the price AT the target, not "now".
    """
    rows = fetch_all(
        """
        SELECT PredictionId, CreatedAt, MarketPrice, PredictedPrice, Signal, FeaturesJson, MarketRegime, Horizon
        FROM TPrediction
        WHERE UserId = ? AND Symbol = ? AND ActualPrice IS NULL AND TargetTime IS NULL
        """,
        (int(user_id), symbol.upper()),
    )
    updated = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        created = _parse_ts(row["CreatedAt"])
        if created is None or now - created < timedelta(minutes=min_age_minutes):
            continue
        execute(
            "UPDATE TPrediction SET ActualPrice = ?, Status = 'evaluated', "
            "EvaluatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE PredictionId = ?",
            (float(current_price), int(row["PredictionId"])),
        )
        updated += 1
        try:
            from analyst.strategy_registry import record_outcome

            feats = json.loads(row["FeaturesJson"]) if row.get("FeaturesJson") else {}
            mkt = float(row.get("MarketPrice") or 0)
            pred = float(row.get("PredictedPrice") or 0)
            actual = float(current_price)
            direction_ok = (pred - mkt) * (actual - mkt) > 0 if mkt else False
            if str(row.get("Signal") or "").upper() == "HOLD":
                direction_ok = abs(actual - mkt) / mkt < 0.004 if mkt else False
            record_outcome(
                strategy_id=str(feats.get("strategy_id") or "Alpha"),
                regime=str(feats.get("master_regime") or row.get("MarketRegime") or "unknown"),
                timeframe=str(row.get("Horizon") or "1d"),
                direction_ok=direction_ok,
                abs_error=abs(pred - actual),
                rr=feats.get("rr"),
            )
        except Exception:
            pass
    return updated


# ---------------------------------------------------------------------------
# Chart reconstruction (the persistent yellow line)
# ---------------------------------------------------------------------------

def load_projection_paths(user_id: int, symbol: str, limit: int = 30):
    """Flatten STORED predictions into projection points for chart overlays.

    Survives refresh and restart: the yellow line is rebuilt from TPrediction.
    """
    import pandas as pd

    rows = fetch_all(
        """
        SELECT * FROM TPrediction
        WHERE UserId = ? AND Symbol = ?
        ORDER BY PredictionId DESC LIMIT ?
        """,
        (int(user_id), symbol.upper(), int(limit)),
    )
    out: list[dict[str, Any]] = []
    for r in reversed(rows):
        run_time = str(r.get("CreatedAt") or "")
        signal = r.get("Signal")
        meta = {
            "model_version": r.get("ModelVersion") or r.get("StrategyVersion") or "",
            "regime": r.get("MarketRegime") or "",
            "signal": signal,
            "market_price": r.get("MarketPrice"),
            "predicted_price": r.get("PredictedPrice"),
            "actual_price": r.get("ActualPrice"),
            "abs_error": r.get("AbsError"),
            "error_pct": r.get("ErrorPct"),
            "direction_ok": r.get("DirectionOk"),
            "range_ok": r.get("RangeOk"),
            "status": r.get("Status") or "pending",
            "horizon": r.get("Horizon") or "",
        }
        proj = []
        if r.get("ProjectionJson"):
            try:
                proj = json.loads(r["ProjectionJson"])
            except json.JSONDecodeError:
                proj = []
        if proj:
            for p in proj:
                out.append({"run_time": run_time, "target_time": str(p["t"]), "predicted_price": float(p["p"]), **meta})
        elif r.get("PredictedPrice") is not None:
            out.append(
                {
                    "run_time": run_time,
                    "target_time": str(r.get("TargetTime") or run_time),
                    "predicted_price": float(r["PredictedPrice"]),
                    **meta,
                }
            )
    return pd.DataFrame(out) if out else pd.DataFrame()


def load_evaluated_records(user_id: int, symbol: str, limit: int = 12) -> list[dict[str, Any]]:
    """Evaluated predictions shaped like the JSON store records (for annotations)."""
    rows = fetch_all(
        """
        SELECT * FROM TPrediction
        WHERE UserId = ? AND Symbol = ? AND ActualPrice IS NOT NULL
        ORDER BY PredictionId DESC LIMIT ?
        """,
        (int(user_id), symbol.upper(), int(limit)),
    )
    out = []
    for r in reversed(rows):
        out.append(
            {
                "timestamp": r.get("CreatedAt"),
                "symbol": r.get("Symbol"),
                "signal": r.get("Signal"),
                "confidence": r.get("Confidence"),
                "market_price": r.get("MarketPrice"),
                "predicted_price": r.get("PredictedPrice"),
                "price_low": r.get("PriceLow"),
                "price_high": r.get("PriceHigh"),
                "actual_price": r.get("ActualPrice"),
                "actual_time": r.get("ActualTime"),
                "error_pct": r.get("ErrorPct"),
                "abs_error": r.get("AbsError"),
                "win": bool(r.get("DirectionOk")) if r.get("DirectionOk") is not None else None,
                "direction_ok": r.get("DirectionOk"),
                "range_ok": r.get("RangeOk"),
                "status": r.get("Status"),
                "model_version": r.get("ModelVersion") or r.get("StrategyVersion"),
                "regime": r.get("MarketRegime"),
                "horizon": r.get("Horizon"),
            }
        )
    return out


def latest_pending(user_id: int, symbol: str, horizon_prefix: str | None = None):
    """Most recent not-yet-evaluated prediction — drives the live yellow line."""
    if horizon_prefix:
        return fetch_one(
            """
            SELECT * FROM TPrediction
            WHERE UserId = ? AND Symbol = ? AND Status = 'pending' AND Horizon LIKE ?
            ORDER BY PredictionId DESC LIMIT 1
            """,
            (int(user_id), symbol.upper(), f"{horizon_prefix}%"),
        )
    return fetch_one(
        """
        SELECT * FROM TPrediction
        WHERE UserId = ? AND Symbol = ? AND Status = 'pending'
        ORDER BY PredictionId DESC LIMIT 1
        """,
        (int(user_id), symbol.upper()),
    )


# ---------------------------------------------------------------------------
# Performance statistics (from stored, evaluated records only)
# ---------------------------------------------------------------------------

def performance_stats(user_id: int, symbol: str | None = None) -> dict[str, Any]:
    where = "UserId = ?"
    params: list[Any] = [int(user_id)]
    if symbol:
        where += " AND Symbol = ?"
        params.append(symbol.upper())

    totals = fetch_one(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN Status = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN Status = 'evaluated' THEN 1 ELSE 0 END) AS evaluated,
            SUM(CASE WHEN DirectionOk = 1 THEN 1 ELSE 0 END) AS dir_hits,
            SUM(CASE WHEN DirectionOk IS NOT NULL THEN 1 ELSE 0 END) AS dir_total,
            SUM(CASE WHEN RangeOk = 1 THEN 1 ELSE 0 END) AS range_hits,
            AVG(AbsError) AS mae,
            AVG(ErrorPct) AS mape,
            MIN(CreatedAt) AS first_at,
            MAX(CreatedAt) AS last_at
        FROM TPrediction WHERE {where}
        """,
        tuple(params),
    ) or {}
    total = int(totals.get("total") or 0)
    dir_total = int(totals.get("dir_total") or 0)
    stats = {
        "total_predictions": total,
        "pending": int(totals.get("pending") or 0),
        "evaluated": int(totals.get("evaluated") or 0),
        "direction_hits": int(totals.get("dir_hits") or 0),
        "direction_total": dir_total,
        "direction_accuracy_pct": round(100.0 * int(totals.get("dir_hits") or 0) / dir_total, 1) if dir_total else None,
        "range_hits": int(totals.get("range_hits") or 0),
        "range_pct": round(100.0 * int(totals.get("range_hits") or 0) / dir_total, 1) if dir_total else None,
        "mean_abs_error": round(float(totals.get("mae") or 0), 3) if dir_total else None,
        "mean_abs_pct_error": round(float(totals.get("mape") or 0), 3) if dir_total else None,
        "period_from": totals.get("first_at"),
        "period_to": totals.get("last_at"),
        "by_timeframe": _group_by("Timeframe", where, params),
        "by_symbol": _group_by("Symbol", where, params),
        "by_regime": _group_by("MarketRegime", where, params),
        "by_model": _group_by("COALESCE(ModelVersion, StrategyVersion)", where, params),
        "error_over_time": _error_over_time(where, params),
    }
    try:
        from prediction.calibration import baseline_comparison, evaluate_calibration, regime_caution

        stats["calibration"] = evaluate_calibration(int(user_id), symbol)
        stats["baselines"] = baseline_comparison(int(user_id), symbol)
        stats["regime_caution"] = regime_caution(int(user_id), symbol)
    except Exception as exc:
        logger.warning("calibration stats skipped: %s", exc)
        stats["calibration"] = {"ok": False, "error": str(exc)}
        stats["baselines"] = {"ok": False}
        stats["regime_caution"] = []
    return stats


def _error_over_time(where: str, params: list[Any], limit: int = 120) -> list[dict[str, Any]]:
    """Completed forecasts, oldest first, so the chart can plot error without filling gaps."""
    rows = fetch_all(
        f"""
        SELECT EvaluatedAt, CreatedAt, TargetTime, Timeframe, Symbol,
               COALESCE(ModelVersion, StrategyVersion) AS model_version,
               MarketRegime, AbsError, ErrorPct, DirectionOk, RangeOk
        FROM TPrediction
        WHERE {where} AND Status = 'evaluated' AND AbsError IS NOT NULL
        ORDER BY COALESCE(EvaluatedAt, CreatedAt) DESC
        LIMIT ?
        """,
        tuple(params) + (int(limit),),
    )
    return list(reversed(rows))


def chart_series(
    user_id: int,
    symbol: str,
    *,
    horizon: str | None = None,
    limit: int = 480,
) -> "Any":
    """One stored forecast per target minute, original record kept.

    The yellow line is this frame: predicted price at the target timestamp,
    never overwritten by the later actual price. ``horizon`` prefers that
    timeframe and falls back to every stored row when that timeframe is empty.
    """
    import pandas as pd

    def _query(hz: str | None):
        sql = """
            SELECT PredictionId, CreatedAt, TargetTime, PredictedPrice, PriceLow, PriceHigh,
                   MarketPrice, ActualPrice, AbsError, ErrorPct, DirectionOk, RangeOk,
                   ModelVersion, StrategyVersion, Status, Horizon, Timeframe, Signal, MarketRegime
            FROM TPrediction
            WHERE UserId = ? AND Symbol = ? AND PredictedPrice IS NOT NULL
        """
        params: list[Any] = [int(user_id), symbol.upper()]
        if hz:
            sql += " AND (Timeframe = ? OR Horizon = ?)"
            params.extend([hz, hz])
        sql += " ORDER BY PredictionId DESC LIMIT ?"
        params.append(int(limit))
        return fetch_all(sql, tuple(params))

    rows = _query(horizon)
    if not rows and horizon:
        rows = _query(None)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    # Pandas 3 cannot .loc-fill a datetime64[us, UTC] column from another
    # DatetimeArray (unit mismatch). Build one series in Python first.
    stamps = []
    for tgt, created in zip(frame.get("TargetTime", []), frame.get("CreatedAt", [])):
        stamps.append(_parse_ts(tgt) or _parse_ts(created))
    frame["target_time"] = pd.to_datetime(stamps, utc=True, errors="coerce")
    frame = frame.dropna(subset=["target_time", "PredictedPrice"])
    if frame.empty:
        return pd.DataFrame()
    frame["target_time"] = frame["target_time"].dt.tz_convert("Asia/Kolkata")
    frame["target_minute"] = frame["target_time"].dt.floor("min")
    frame = frame.sort_values(["target_minute", "PredictionId"])
    # Keep the earliest forecast for each target minute. A later revision stays
    # in the table but does not replace the original point on the line.
    frame = frame.drop_duplicates(subset=["target_minute"], keep="first")
    frame = frame.sort_values("target_time")
    frame["predicted_price"] = frame["PredictedPrice"].astype(float)
    frame["created_at"] = frame["CreatedAt"]
    frame["price_low"] = frame["PriceLow"]
    frame["price_high"] = frame["PriceHigh"]
    frame["market_price"] = frame["MarketPrice"]
    frame["actual_price"] = frame["ActualPrice"]
    frame["abs_error"] = frame["AbsError"]
    frame["error_pct"] = frame["ErrorPct"]
    frame["direction_ok"] = frame["DirectionOk"]
    frame["model_version"] = frame["ModelVersion"].fillna(frame["StrategyVersion"])
    frame["signal"] = frame["Signal"]
    frame["status"] = frame["Status"]
    frame["horizon"] = frame["Horizon"]
    return frame.reset_index(drop=True)


def _group_by(expr: str, where: str, params: list[Any]) -> list[dict[str, Any]]:
    rows = fetch_all(
        f"""
        SELECT {expr} AS key,
               COUNT(*) AS n,
               SUM(CASE WHEN DirectionOk = 1 THEN 1 ELSE 0 END) AS hits,
               ROUND(AVG(AbsError), 3) AS mae,
               ROUND(AVG(ErrorPct), 3) AS mape,
               SUM(CASE WHEN RangeOk = 1 THEN 1 ELSE 0 END) AS range_hits
        FROM TPrediction
        WHERE {where} AND Status = 'evaluated'
        GROUP BY key ORDER BY n DESC LIMIT 20
        """,
        tuple(params),
    )
    for r in rows:
        n = int(r.get("n") or 0)
        r["direction_accuracy_pct"] = round(100.0 * int(r.get("hits") or 0) / n, 1) if n else None
    return rows
