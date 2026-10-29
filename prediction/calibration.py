"""Calibration, baselines, and honesty metrics from stored evaluations.

ProbUp/ProbDown on TPrediction are uncalibrated model scores unless labelled
otherwise. These functions never invent accuracy.
"""

from __future__ import annotations

import math
from typing import Any

from db.database import fetch_all

MIN_CALIB = 30
MIN_BASELINE = 10


def _rows(user_id: int, symbol: str | None) -> list[dict[str, Any]]:
    where = "UserId = ? AND Status = 'evaluated' AND ActualPrice IS NOT NULL AND MarketPrice IS NOT NULL"
    params: list[Any] = [int(user_id)]
    if symbol:
        where += " AND Symbol = ?"
        params.append(symbol.upper())
    return fetch_all(
        f"""
        SELECT MarketPrice, PredictedPrice, ActualPrice, DirectionOk, AbsError, ErrorPct,
               ProbUp, ProbDown, ProbSideways, MarketRegime, Timeframe, SignedError
        FROM TPrediction WHERE {where}
        ORDER BY PredictionId
        """,
        tuple(params),
    )


def _brier_three(p_up: float, p_side: float, p_down: float, y_up: float, y_side: float, y_down: float) -> float:
    return (p_up - y_up) ** 2 + (p_side - y_side) ** 2 + (p_down - y_down) ** 2


def _log_loss(p: float, y: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def evaluate_calibration(user_id: int, symbol: str | None = None) -> dict[str, Any]:
    """Brier / log-loss / ECE on stored ProbUp vs actual up-move. Preliminary if n < 30."""
    rows = [r for r in _rows(user_id, symbol) if r.get("ProbUp") is not None]
    n = len(rows)
    if n < MIN_CALIB:
        return {
            "ok": True,
            "n": n,
            "min_sample": MIN_CALIB,
            "preliminary": True,
            "note": f"Need {MIN_CALIB} evaluated rows with probability scores (have {n}). Figures are preliminary.",
            "brier": None,
            "log_loss": None,
            "ece": None,
            "rmse": None,
        }
    brier_sum = 0.0
    ll_sum = 0.0
    se_sum = 0.0
    bins: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    for r in rows:
        base = float(r["MarketPrice"])
        actual = float(r["ActualPrice"])
        pred = float(r["PredictedPrice"] or base)
        p_up = float(r["ProbUp"] or 0) / 100.0
        p_dn = float(r["ProbDown"] or 0) / 100.0
        if r.get("ProbSideways") is not None:
            p_sd = float(r["ProbSideways"]) / 100.0
        else:
            p_sd = max(0.0, 1.0 - p_up - p_dn)
        if p_up + p_dn + p_sd <= 0:
            continue
        tot = p_up + p_dn + p_sd
        p_up, p_dn, p_sd = p_up / tot, p_dn / tot, p_sd / tot
        y_up = 1.0 if actual > base else 0.0
        y_dn = 1.0 if actual < base else 0.0
        y_sd = 1.0 if y_up == 0 and y_dn == 0 else 0.0
        brier_sum += _brier_three(p_up, p_sd, p_dn, y_up, y_sd, y_dn)
        ll_sum += _log_loss(p_up, y_up)
        se_sum += (pred - actual) ** 2
        idx = min(9, max(0, int(p_up * 10)))
        bins[idx].append((p_up, y_up))
    ece = 0.0
    filled = 0
    for bucket in bins:
        if not bucket:
            continue
        filled += 1
        mean_p = sum(p for p, _ in bucket) / len(bucket)
        mean_y = sum(y for _, y in bucket) / len(bucket)
        ece += abs(mean_p - mean_y) * (len(bucket) / n)
    return {
        "ok": True,
        "n": n,
        "min_sample": MIN_CALIB,
        "preliminary": False,
        "note": (
            f"Based on {n} evaluated forecasts with uncalibrated probability scores. "
            "A 70% up-score is only well calibrated if similar scores rose about 70% of the time."
        ),
        "brier": round(brier_sum / n, 4),
        "log_loss": round(ll_sum / n, 4),
        "ece": round(ece, 4),
        "rmse": round(math.sqrt(se_sum / n), 4),
        "bins_used": filled,
    }


def baseline_comparison(user_id: int, symbol: str | None = None) -> dict[str, Any]:
    """Compare model MAE/direction to naive no-change and last-direction continuation.

    Continuation uses the sign of (predicted - base) as a stand-in for 'recent trend'
    because that is what the model itself used; the no-change baseline predicts
    Actual == MarketPrice.
    """
    rows = _rows(user_id, symbol)
    n = len(rows)
    if n < MIN_BASELINE:
        return {
            "ok": True,
            "n": n,
            "min_sample": MIN_BASELINE,
            "preliminary": True,
            "note": f"Need {MIN_BASELINE} evaluated rows to compare against baselines (have {n}).",
            "model_mae": None,
            "no_change_mae": None,
            "beats_no_change": None,
        }
    model_abs = []
    naive_abs = []
    model_dir = []
    naive_dir = []  # no-change is correct only when price is unchanged (always False almost)
    for r in rows:
        base = float(r["MarketPrice"])
        pred = float(r["PredictedPrice"] or base)
        actual = float(r["ActualPrice"])
        model_abs.append(abs(actual - pred))
        naive_abs.append(abs(actual - base))
        model_dir.append(int(r["DirectionOk"] or 0))
        # Continuation of last model drift vs a coin-flip is not used; no-change
        # direction is correct iff actual is within 0.08% of base.
        naive_dir.append(1 if abs(actual - base) <= base * 0.0008 else 0)
    mae_m = sum(model_abs) / n
    mae_n = sum(naive_abs) / n
    return {
        "ok": True,
        "n": n,
        "min_sample": MIN_BASELINE,
        "preliminary": False,
        "model_mae": round(mae_m, 4),
        "no_change_mae": round(mae_n, 4),
        "beats_no_change": mae_m < mae_n,
        "model_direction_pct": round(100.0 * sum(model_dir) / n, 1),
        "no_change_direction_pct": round(100.0 * sum(naive_dir) / n, 1),
        "note": (
            "No-change baseline predicts the price at generation time. "
            "Directional accuracy is not profitability. "
            + (
                "Model MAE is lower than no-change on this sample — still not a profit claim."
                if mae_m < mae_n
                else "Model MAE is not better than predicting no change on this sample."
            )
        ),
    }


def regime_caution(user_id: int, symbol: str | None = None) -> list[dict[str, Any]]:
    """Where directional accuracy is weak — treat those regimes cautiously."""
    rows = _rows(user_id, symbol)
    buckets: dict[str, list[int]] = {}
    for r in rows:
        key = str(r.get("MarketRegime") or "unknown")
        buckets.setdefault(key, []).append(int(r.get("DirectionOk") or 0))
    out = []
    for regime, hits in sorted(buckets.items()):
        n = len(hits)
        if n < MIN_BASELINE:
            out.append(
                {
                    "regime": regime,
                    "n": n,
                    "direction_accuracy_pct": None,
                    "caution": True,
                    "note": f"Insufficient sample ({n} < {MIN_BASELINE}).",
                }
            )
            continue
        acc = round(100.0 * sum(hits) / n, 1)
        out.append(
            {
                "regime": regime,
                "n": n,
                "direction_accuracy_pct": acc,
                "caution": acc < 50,
                "note": "Treat forecasts cautiously in this regime." if acc < 50 else "Sample does not imply future accuracy.",
            }
        )
    return out
