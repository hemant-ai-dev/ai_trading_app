"""Rule-based intraday projection paths (not a forecast of real prices — compare with live data cautiously)."""

from __future__ import annotations

from datetime import date, datetime, time
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from market_calendar import MarketStatus, SessionPhase

IST = ZoneInfo("Asia/Kolkata")


def ensure_ist_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = out.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    out.index = idx.tz_convert(IST)
    return out


def nse_regular_5m_index(day: date) -> pd.DatetimeIndex:
    """5-minute stamps covering regular cash session (aligned with common charts)."""
    start = datetime.combine(day, time(9, 15), tzinfo=IST)
    end = datetime.combine(day, time(15, 30), tzinfo=IST)
    return pd.date_range(start=start, end=end, freq="5min")


def linear_projection(index: pd.DatetimeIndex, start_px: float, end_px: float) -> pd.Series:
    n = len(index)
    if n == 0:
        return pd.Series(dtype=float)
    y = np.linspace(float(start_px), float(end_px), n)
    return pd.Series(y, index=index, name="projection")


def filter_session_day(df_ist: pd.DataFrame, day: date) -> pd.DataFrame:
    mask = df_ist.index.map(lambda t: t.date()) == day
    return df_ist.loc[mask]


def build_comparison_series(
    df_ist: pd.DataFrame,
    target_price: float,
    ms: MarketStatus,
    session_anchor: dict | None,
) -> tuple[pd.Series, pd.Series, str]:
    """
    Returns (actual_series_for_plot, projection_series_for_plot, note).

    actual_series: today's intraday close if available; else empty.
    projection_series: straight-line path from anchor to target on today's or next session grid.
    """
    today = ms.now_ist.date()

    if ms.phase == SessionPhase.HOLIDAY_OR_WEEKEND or not ms.is_trading_day:
        last_close = float(df_ist["Close"].iloc[-1])
        idx = nse_regular_5m_index(ms.next_session_date)
        proj = linear_projection(idx, last_close, float(target_price))
        note = (
            f"No live session today — showing next session roadmap ({ms.next_session_date.isoformat()}) "
            f"from last close ₹{last_close:.2f} toward rule-based target ₹{float(target_price):.2f}."
        )
        return pd.Series(dtype=float), proj, note

    bounds_open = ms.session_open_ist
    bounds_close = ms.session_close_ist
    assert bounds_open is not None and bounds_close is not None

    today_df = filter_session_day(df_ist, today)
    last_close = float(df_ist["Close"].iloc[-1])

    if len(today_df) > 0:
        first_px = float(today_df["Close"].iloc[0])
        anchor_src = "first intraday close (session start region)"
    else:
        first_px = last_close
        anchor_src = "last available close (no prints yet today in window)"

    anchor_px = first_px
    if session_anchor is not None:
        anchor_px = float(session_anchor.get("anchor_price", first_px))

    session_day = today
    idx = nse_regular_5m_index(session_day)
    proj = linear_projection(idx, anchor_px, float(target_price))

    if ms.phase == SessionPhase.PRE_OPEN:
        note = (
            f"Pre-open — projection for today's session ({session_day}) from {anchor_src}, "
            f"anchor ₹{anchor_px:.2f} → target ₹{float(target_price):.2f}."
        )
        actual = pd.Series(dtype=float)
        return actual, proj, note

    if ms.phase == SessionPhase.POST_CLOSE:
        nxt = ms.next_session_date
        idx_n = nse_regular_5m_index(nxt)
        proj_n = linear_projection(idx_n, last_close, float(target_price))
        note = (
            f"After close — today's history retained; next-session roadmap ({nxt.isoformat()}) "
            f"from last close ₹{last_close:.2f} → target ₹{float(target_price):.2f}."
        )
        return today_df["Close"], proj_n, note

    # OPEN
    if len(today_df) == 0:
        note = (
            f"Session open — no intraday rows in the selected window yet; projection uses anchor "
            f"₹{anchor_px:.2f} → target ₹{float(target_price):.2f}."
        )
        return pd.Series(dtype=float), proj, note

    actual = today_df["Close"]
    note = (
        f"Live session — projection fixed from anchor ₹{anchor_px:.2f} ({anchor_src}) to target "
        f"₹{float(target_price):.2f}; compare orange path to live closes."
    )
    return actual, proj, note


def snapshot_session_anchor(
    stock: str,
    day: date,
    anchor_price: float,
) -> dict:
    return {"symbol": stock, "day": day.isoformat(), "anchor_price": anchor_price}
