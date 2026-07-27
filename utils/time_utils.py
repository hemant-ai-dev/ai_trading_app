"""Timezone and datetime helpers."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

IST = ZoneInfo("Asia/Kolkata")


def ensure_ist_index(df: pd.DataFrame) -> pd.DataFrame:
    """Convert DataFrame index to Asia/Kolkata timezone."""
    out = df.copy()
    idx = out.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    out.index = idx.tz_convert(IST)
    return out


def nse_regular_5m_index(day: date) -> pd.DatetimeIndex:
    """Five-minute timestamps for NSE regular cash session."""
    start = datetime.combine(day, time(9, 15), tzinfo=IST)
    end = datetime.combine(day, time(15, 30), tzinfo=IST)
    return pd.date_range(start=start, end=end, freq="5min")
