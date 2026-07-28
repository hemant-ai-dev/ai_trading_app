"""Chart Y-axis range helper."""

from __future__ import annotations

from typing import Any

import pandas as pd


def chart_y_range(
    df_ist: pd.DataFrame,
    proj: pd.Series | None,
    fib_levels: list[float] | None = None,
) -> tuple[float, float]:
    """Compute padded Y-axis range for price charts."""
    ys: list[float] = []
    if "Low" in df_ist.columns and "High" in df_ist.columns:
        ys.extend([float(df_ist["Low"].min()), float(df_ist["High"].max())])
    close = df_ist["Close"].astype(float)
    ys.extend([float(close.min()), float(close.max())])
    if proj is not None and len(proj) > 0:
        ys.extend([float(proj.min()), float(proj.max())])
    for level in fib_levels or []:
        ys.append(float(level))
    if not ys:
        return 0.0, 1.0
    lo, hi = min(ys), max(ys)
    span = hi - lo
    pad = max(span * 0.06, hi * 0.0015, 1e-6)
    return lo - pad, hi + pad
