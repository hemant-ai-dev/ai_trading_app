"""Chart helpers — snapshot levels and Y-axis range."""

from __future__ import annotations

from typing import Any


def snapshot_levels(df: Any, result: dict[str, Any]) -> dict[str, float]:
    last = df.iloc[-1]
    return {
        "last_close": float(last["Close"]),
        "vwap": float(last["VWAP"]),
        "atr": float(last["ATR"]),
        "rule_stop": float(result["stop_loss"]),
        "rule_target": float(result["target"]),
    }


def chart_y_range(
    df_ist: Any,
    proj_cmp: Any,
    proj_qual: Any | None,
    chart_levels: list[dict[str, Any]],
) -> tuple[float, float]:
    ys: list[float] = []
    close = df_ist["Close"].astype(float)
    ys.extend([float(close.min()), float(close.max())])
    if proj_cmp is not None and len(proj_cmp) > 0:
        ys.extend([float(proj_cmp.min()), float(proj_cmp.max())])
    if proj_qual is not None and len(proj_qual) > 0:
        ys.extend([float(proj_qual.min()), float(proj_qual.max())])
    for row in chart_levels:
        ys.append(float(row["price"]))
    if not ys:
        return 0.0, 1.0
    lo, hi = min(ys), max(ys)
    span = hi - lo
    pad = max(span * 0.06, hi * 0.0015, 1e-6)
    return lo - pad, hi + pad
