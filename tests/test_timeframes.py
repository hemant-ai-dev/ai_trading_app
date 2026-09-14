from datetime import datetime

import pandas as pd

from config.timeframes import default_interval, intervals_for_period
from services.market_service import MarketService, _slice_last_session


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
