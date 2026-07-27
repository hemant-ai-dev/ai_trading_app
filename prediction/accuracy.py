"""Prediction accuracy analytics."""

from __future__ import annotations

from typing import Any

import pandas as pd

from prediction.history_store import PredictionHistoryStore


def compute_accuracy_metrics(symbol: str | None = None, store: PredictionHistoryStore | None = None) -> dict[str, Any]:
    """Compute accuracy dashboard metrics from stored predictions."""
    store = store or PredictionHistoryStore()
    df = store.to_dataframe(symbol, limit=500)
    if df.empty:
        return {
            "total_predictions": 0,
            "evaluated": 0,
            "accuracy_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_error_pct": 0.0,
            "avg_confidence": 0.0,
            "profit_loss_sim_pct": 0.0,
        }

    evaluated = df[df["actual_price"].notna()].copy()
    if evaluated.empty:
        return {
            "total_predictions": len(df),
            "evaluated": 0,
            "accuracy_pct": 0.0,
            "win_rate_pct": 0.0,
            "avg_error_pct": 0.0,
            "avg_confidence": round(float(df["confidence"].mean()), 1),
            "profit_loss_sim_pct": 0.0,
        }

    within_1pct = (evaluated["error_pct"] <= 1.0).sum()
    wins = evaluated["win"].fillna(False).sum()
    n = len(evaluated)

    # Simple P/L simulation: +1% on win BUY, -1% on loss BUY, inverse for SELL
    pnl = 0.0
    for _, row in evaluated.iterrows():
        if row["signal"] == "BUY":
            pnl += 1.0 if row.get("win") else -1.0
        elif row["signal"] == "SELL":
            pnl += 1.0 if row.get("win") else -1.0

    return {
        "total_predictions": len(df),
        "evaluated": n,
        "accuracy_pct": round(within_1pct / n * 100, 1),
        "win_rate_pct": round(wins / n * 100, 1),
        "avg_error_pct": round(float(evaluated["error_pct"].mean()), 2),
        "avg_confidence": round(float(df["confidence"].mean()), 1),
        "profit_loss_sim_pct": round(pnl, 1),
        "confidence_distribution": evaluated.groupby(
            pd.cut(evaluated["confidence"], bins=[0, 50, 70, 85, 100], labels=["Low", "Medium", "High", "Very High"])
        ).size().to_dict(),
    }


def confidence_distribution_df(symbol: str | None = None, store: PredictionHistoryStore | None = None) -> pd.DataFrame:
    """Return confidence bucket counts for charting."""
    store = store or PredictionHistoryStore()
    df = store.to_dataframe(symbol, limit=500)
    if df.empty:
        return pd.DataFrame(columns=["bucket", "count"])
    buckets = pd.cut(df["confidence"], bins=[0, 50, 70, 85, 100], labels=["Low (0-50)", "Medium (50-70)", "High (70-85)", "Very High (85+)"])
    counts = buckets.value_counts().reset_index()
    counts.columns = ["bucket", "count"]
    return counts
