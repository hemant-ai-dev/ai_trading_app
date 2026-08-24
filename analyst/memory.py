"""Step 10 — AI memory: use past accuracy to nudge future weights."""

from __future__ import annotations

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
