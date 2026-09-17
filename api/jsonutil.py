"""JSON-safe conversion for API payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item) and not isinstance(value, dict):
        try:
            return jsonable(value.item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, pd.Series):
        return {str(k): jsonable(v) for k, v in value.items()}
    return str(value)
