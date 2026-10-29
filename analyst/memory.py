"""Step 10 — AI memory: use past accuracy to nudge future weights."""

from __future__ import annotations

import json
from typing import Any

from prediction.accuracy import compute_accuracy_metrics
from prediction.history_store import PredictionHistoryStore


def load_memory_feedback(symbol: str, store: PredictionHistoryStore | None = None) -> dict[str, Any]:
    """
    Inspect recent prediction outcomes and suggest small weight nudges.

    This is a light calibration loop — not full model training.
    """
    store = store or PredictionHistoryStore()
    metrics = compute_accuracy_metrics(symbol, store)
    df = store.to_dataframe(symbol, limit=40)

    nudges: dict[str, float] = {}
    notes: list[str] = []

    if metrics.get("evaluated", 0) < 5:
        return {
            "weight_nudges": {},
            "notes": ["Not enough evaluated history yet to calibrate weights."],
            "metrics": metrics,
        }

    win = float(metrics.get("win_rate_pct") or 0)
    avg_err = float(metrics.get("avg_error_pct") or 0)

    if win >= 60:
        notes.append(f"Recent win rate {win:.0f}% — maintaining current approach.")
        nudges["trend"] = 1.05
    elif win <= 40:
        notes.append(f"Recent win rate {win:.0f}% — being more selective; boosting confirmation tools.")
        nudges["volume"] = 1.15
        nudges["support_resistance"] = 1.1
        nudges["news"] = 1.08
        nudges["trend"] = 0.9

    if avg_err > 1.5:
        notes.append(f"Average error {avg_err:.2f}% is elevated — widening caution / risk sensitivity.")
        nudges["macro"] = 1.1

    # Signal mix bias
    if not df.empty and "signal" in df.columns:
        buys = (df["signal"] == "BUY").sum()
        sells = (df["signal"] == "SELL").sum()
        if buys > sells * 2:
            notes.append("History skewed to BUY calls — requiring stronger bullish confirmation.")
            nudges["momentum"] = nudges.get("momentum", 1.0) * 1.05
        elif sells > buys * 2:
            notes.append("History skewed to SELL calls — requiring stronger bearish confirmation.")
            nudges["macd"] = nudges.get("macd", 1.0) * 1.05

    return {"weight_nudges": nudges, "notes": notes, "metrics": metrics}


def similar_setups(symbol: str, features: dict[str, Any], *, user_id: int | None = None, limit: int = 40) -> dict[str, Any]:
    """Comparable stored predictions — historical evidence, not proof of the next print."""
    from prediction import archive

    rows = archive.list_predictions(int(user_id or 0), None, limit=200) if user_id else []
    rsi = float(features.get("rsi") or 50)
    adx = float(features.get("adx") or 0)
    trend = str(features.get("trend") or features.get("trend_dir") or "")
    regime = str(features.get("regime") or features.get("master_regime") or "")
    matched = []
    for row in rows:
        try:
            feats = json.loads(row.get("FeaturesJson") or "{}")
        except Exception:
            feats = {}
        rsi2 = float(feats.get("rsi") or 50)
        if abs(rsi2 - rsi) > 12:
            continue
        if trend and str(feats.get("trend") or "") and str(feats.get("trend") or "") != trend:
            continue
        if regime and str(feats.get("master_regime") or row.get("MarketRegime") or "") not in (regime, regime.replace(" ", "_")):
            if str(row.get("MarketRegime") or "") != regime:
                continue
        actual = row.get("ActualPrice")
        mkt = row.get("MarketPrice")
        pred = row.get("PredictedPrice")
        if actual is None or mkt is None:
            continue
        matched.append(
            {
                "symbol": row.get("Symbol"),
                "signal": row.get("Signal"),
                "market": mkt,
                "predicted": pred,
                "actual": actual,
                "created_at": row.get("CreatedAt"),
            }
        )
        if len(matched) >= limit:
            break
    ups = 0
    for m in matched:
        try:
            if float(m["actual"]) > float(m["market"]):
                ups += 1
        except (TypeError, ValueError):
            pass
    n = len(matched)
    moves = []
    abs_err = []
    for m in matched:
        try:
            base = float(m["market"])
            actual = float(m["actual"])
            pred = float(m["predicted"]) if m.get("predicted") is not None else None
            if base:
                moves.append((actual - base) / base * 100)
            if pred is not None:
                abs_err.append(abs(actual - pred))
        except (TypeError, ValueError):
            pass
    return {
        "comparable_cases": n,
        "up_outcomes": ups,
        "down_or_flat": n - ups,
        "avg_subsequent_move_pct": round(sum(moves) / len(moves), 3) if moves else None,
        "avg_abs_prediction_error": round(sum(abs_err) / len(abs_err), 3) if abs_err else None,
        "note": "Similar stored conditions. This is evidence from past forecasts, not proof the next print will repeat.",
        "rows": matched[:12],
    }
