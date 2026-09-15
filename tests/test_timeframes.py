from datetime import datetime

import pandas as pd

from config.timeframes import default_interval, intervals_for_period
from services.market_service import MarketService, _slice_last_session, clip_to_requested_window


def test_1d_keeps_intraday_interval():
    period, interval = MarketService.normalize_period_interval("1d", "5m")
    assert period == "1d"
    assert interval == "5m"
    period, interval = MarketService.normalize_period_interval("1d", "1h")
    assert period == "1d"
    assert interval == "1h"


def test_1d_rejects_daily_interval():
    period, interval = MarketService.normalize_period_interval("1d", "1d")
    assert period == "1d"
    assert interval in intervals_for_period("1d")
    assert interval != "1d"


def test_intervals_for_1d_include_hourly():
    assert "1m" in intervals_for_period("1d")
    assert "1h" in intervals_for_period("1d")
    assert default_interval("1d") == "5m"


def test_slice_last_session_drops_prior_days():
    idx = pd.date_range("2026-01-08 09:15", periods=10, freq="1h").append(
        pd.date_range("2026-01-09 09:15", periods=6, freq="1h")
    )
    df = pd.DataFrame({"Close": range(len(idx))}, index=idx)
    sliced = _slice_last_session(df)
    assert all(t.date() == datetime(2026, 1, 9).date() for t in sliced.index)
    assert len(sliced) == 6


def test_clip_1d_keeps_last_session_only():
    idx = pd.date_range("2026-01-05 09:15", periods=3, freq="1D").union(
        pd.date_range("2026-01-08 09:15", periods=8, freq="1h")
    )
    df = pd.DataFrame({"Close": range(len(idx))}, index=idx.sort_values())
    clipped = clip_to_requested_window(df, "1d", "5m")
    assert {t.date() for t in clipped.index} == {datetime(2026, 1, 8).date()}


def test_clip_5d_keeps_five_trading_dates():
    days = pd.date_range("2026-01-01 10:00", periods=8, freq="1D")
    df = pd.DataFrame({"Close": range(8)}, index=days)
    clipped = clip_to_requested_window(df, "5d", "1d")
    assert len({t.date() for t in clipped.index}) == 5
    assert clipped.index.min() == days[-5]
