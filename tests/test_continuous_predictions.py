"""Continuous prediction engine: horizon math, archive lifecycle, scheduler guards, option evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(db_file))
    from db.bootstrap import initialize

    initialize()
    from db.database import execute

    execute("INSERT INTO TReadUser (UserId, Username, Email, PasswordHash) VALUES (1,'t','t@t','x')")
    yield db_file


def _pred_result(pred=105.0, low=102.0, high=108.0, signal="BUY", regime="trending_bull"):
    from prediction.models import PredictionResult

    return PredictionResult(
        signal=signal,
        confidence=60.0,
        predicted_price=pred,
        target_price=pred,
        stop_loss=low,
        price_low=low,
        price_high=high,
        trend="bullish",
        risk_level="Medium",
        score=2.0,
        market_regime=regime,
        reasons=["test"],
        reasons_simple=["test"],
        indicator_snapshot={"rsi": 55, "atr": 1.0, "trend_dir": "bullish"},
    )


# --- horizon engine ---------------------------------------------------------

def test_horizon_prediction_fields_and_probability_sum():
    from prediction.horizon_engine import horizon_prediction

    now = datetime(2026, 10, 12, 11, 0, tzinfo=IST)
    out = horizon_prediction(
        base_price=100.0, atr_bar=0.5, score=2.0, horizon="15m",
        bar_minutes=5, now_ist=now, session_close_ist=datetime(2026, 10, 12, 15, 30, tzinfo=IST),
        bars_available=100,
    )
    assert out is not None
    assert out["horizon"] == "15m"
    assert out["target_time"] == now + timedelta(minutes=15)
    assert out["price_low"] < out["predicted_price"] < out["price_high"] or out["direction"] in ("BUY", "SELL")
    p = out["prob_up"] + out["prob_sideways"] + out["prob_down"]
    assert abs(p - 100.0) < 1e-3  # percent scale
    assert out["prob_source"] == "score_derived_uncalibrated"
    assert out["model_version"] == "angad-horizon-v1"


def test_horizon_no_prediction_guards():
    from prediction.horizon_engine import horizon_prediction

    now = datetime(2026, 10, 12, 11, 0, tzinfo=IST)
    kw = dict(bar_minutes=5, now_ist=now, session_close_ist=datetime(2026, 10, 12, 15, 30, tzinfo=IST))
    assert horizon_prediction(base_price=100.0, atr_bar=0.5, score=2.0, horizon="15m", bars_available=10, **kw) is None
    assert horizon_prediction(base_price=100.0, atr_bar=0.5, score=0.3, horizon="15m", bars_available=100, **kw) is None
    assert horizon_prediction(base_price=100.0, atr_bar=0.0, score=2.0, horizon="15m", bars_available=100, **kw) is None


def test_eod_targets_session_close():
    from prediction.horizon_engine import horizon_prediction

    now = datetime(2026, 10, 12, 14, 0, tzinfo=IST)
    close = datetime(2026, 10, 12, 15, 30, tzinfo=IST)
    out = horizon_prediction(base_price=100.0, atr_bar=0.5, score=2.0, horizon="eod", bar_minutes=5,
                             now_ist=now, session_close_ist=close, bars_available=100)
    assert out is not None
    assert out["target_time"] == close


def test_blend_timeframes_conflict_and_align():
    from prediction.horizon_engine import blend_timeframe_score

    aligned, notes_a = blend_timeframe_score(2.0, "bullish", 1.0, "bullish")
    conflict, notes_c = blend_timeframe_score(2.0, "bullish", -1.0, "bearish")
    assert aligned > 2.0 and abs(conflict) < 2.0
    assert notes_a and notes_c


def test_signal_from_probs_thresholds():
    from prediction.horizon_engine import signal_from_probs

    assert signal_from_probs((70.0, 15.0, 15.0)) == "BUY"
    assert signal_from_probs((15.0, 15.0, 70.0)) == "SELL"
    assert signal_from_probs((34.0, 33.0, 33.0)) == "HOLD"  # razor-thin edge is not a direction
    assert signal_from_probs((30.0, 40.0, 30.0)) == "HOLD"  # sideways dominant
    assert signal_from_probs((0.7, 0.15, 0.15)) == "BUY"  # fraction scale also supported


# --- archive lifecycle ------------------------------------------------------

def test_save_and_dedup_by_scheduled_key(sqlite_db):
    from prediction import archive

    gen = datetime(2026, 10, 12, 5, 30, tzinfo=timezone.utc)  # 11:00 IST
    key = archive.make_scheduled_key(1, "TEST.NS", "15m", gen)
    pid = archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(), market_price=100.0, horizon="15m",
        scheduled_key=key, target_time=gen + timedelta(minutes=15),
        timeframe="15m", probs=(0.5, 0.2, 0.3),
    )
    assert pid is not None
    dup = archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(), market_price=100.0, horizon="15m",
        scheduled_key=key, target_time=gen + timedelta(minutes=15),
        timeframe="15m", probs=(0.5, 0.2, 0.3),
    )
    assert dup is None  # duplicate scheduled minute ignored


def test_evaluate_due_only_at_target_and_idempotent(sqlite_db):
    from prediction import archive

    target = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
    key = archive.make_scheduled_key(1, "TEST.NS", "30m", target - timedelta(minutes=30))
    archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(pred=105.0, low=102.0, high=108.0),
        market_price=100.0, horizon="30m", scheduled_key=key, target_time=target, timeframe="30m",
    )
    def _naive_ist(dt_utc: datetime) -> pd.Timestamp:
        return pd.Timestamp(dt_utc.astimezone(IST).replace(tzinfo=None))  # Yahoo-style naive IST wall time

    idx = pd.DatetimeIndex([
        _naive_ist(target - timedelta(minutes=10)),
        _naive_ist(target + timedelta(minutes=3)),
    ])
    bars = pd.DataFrame(
        {"Open": [101, 104], "High": [102, 105], "Low": [100, 103], "Close": [101.0, 104.0], "Volume": [10, 10]},
        index=idx,
    )
    n = archive.evaluate_due(1, "TEST.NS", bars, now_utc=target + timedelta(minutes=3))
    assert n == 1
    again = archive.evaluate_due(1, "TEST.NS", bars, now_utc=target + timedelta(minutes=4))
    assert again == 0  # idempotent — pending-only update

    from db.database import fetch_one

    row = fetch_one("SELECT * FROM TPrediction WHERE Symbol='TEST.NS'")
    assert row["Status"] == "evaluated"
    assert row["ActualPrice"] == pytest.approx(104.0)
    assert row["DirectionOk"] == 1
    assert row["AbsError"] == pytest.approx(1.0)
    assert row["RangeOk"] == 1  # 104 inside 102–108


def test_evaluate_never_marks_on_stale_data(sqlite_db):
    from prediction import archive

    target = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
    key = archive.make_scheduled_key(1, "TEST.NS", "60m", target - timedelta(minutes=60))
    archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(), market_price=100.0, horizon="60m",
        scheduled_key=key, target_time=target, timeframe="60m",
    )
    idx = pd.DatetimeIndex([pd.Timestamp((target - timedelta(minutes=30)).astimezone(IST).replace(tzinfo=None))])
    bars = pd.DataFrame({"Open": [99], "High": [100], "Low": [98], "Close": [99.0], "Volume": [5]}, index=idx)
    n = archive.evaluate_due(1, "TEST.NS", bars, now_utc=target + timedelta(minutes=3))
    assert n == 0  # no bar at/after target → stays pending, never falsely judged

    from db.database import fetch_one

    assert fetch_one("SELECT Status FROM TPrediction WHERE Symbol='TEST.NS'")["Status"] == "pending"


def test_performance_stats_counts_only_evaluated(sqlite_db):
    from prediction import archive

    target = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
    for i, horizon in enumerate(("15m", "30m")):
        key = archive.make_scheduled_key(1, "TEST.NS", horizon, target)
        archive.save_prediction(
            user_id=1, symbol="TEST.NS", result=_pred_result(), market_price=100.0, horizon=horizon,
            scheduled_key=key, target_time=target + timedelta(minutes=i), timeframe=horizon,
        )
    stats = archive.performance_stats(1, "TEST.NS")
    assert stats["total_predictions"] == 2
    assert stats["evaluated"] == 0
    assert stats["pending"] == 2
    assert stats["direction_accuracy_pct"] is None  # no fabricated accuracy


# --- scheduler guards -------------------------------------------------------

def test_stale_bars_guard():
    from workers.prediction_scheduler import _stale_bars

    now = datetime(2026, 10, 12, 11, 0, tzinfo=IST)
    fresh = pd.DataFrame({"Close": [1]}, index=pd.DatetimeIndex([pd.Timestamp("2026-10-12 10:55")]))
    old = pd.DataFrame({"Close": [1]}, index=pd.DatetimeIndex([pd.Timestamp("2026-10-12 09:00")]))
    assert _stale_bars(fresh, now) is False
    assert _stale_bars(old, now) is True
    assert _stale_bars(None, now) is True


def test_watch_roundtrip(sqlite_db):
    from workers.prediction_scheduler import is_watched, list_watch, set_watch

    assert is_watched(1, "TEST.NS") is False
    set_watch(1, "TEST.NS", True, horizons=["5m", "15m"])
    assert is_watched(1, "TEST.NS") is True
    rows = list_watch(1)
    assert any(r["Symbol"] == "TEST.NS" and "5m" in r["Horizons"] for r in rows)
    set_watch(1, "TEST.NS", False)
    assert is_watched(1, "TEST.NS") is False


def test_set_watch_creates_sqlite_stub_for_excel_user(sqlite_db):
    """Cloud logins live in Excel; TLiveWatch still needs a TReadUser row."""
    from db.database import fetch_one
    from workers.prediction_scheduler import is_watched, set_watch

    set_watch(99, "NIFTY.NS", True)
    assert is_watched(99, "NIFTY.NS") is True
    stub = fetch_one("SELECT Username FROM TReadUser WHERE UserId=99")
    assert stub and stub["Username"] == "xlsx_99"


# --- option prediction lifecycle ---------------------------------------------

def test_option_append_mirror_and_evaluate(sqlite_db, tmp_path):
    from options.store import OptionPredictionStore
    from db.database import fetch_all

    store = OptionPredictionStore(tmp_path / "hist.json")
    row = store.append(
        {
            "underlying": "^NSEI", "spot": 22360.0, "expiry": "2026-10-19", "option_type": "CE",
            "strike": 22350, "contract": "NIFTYX22350", "actual_premium": 120.5,
            "predicted_premium": 126.0, "predicted_underlying": 22375, "horizon": "1m",
            "stop": 110, "target": 135, "action": "WATCH", "signal": "BUY", "confidence": 58,
            "market_regime": "trending_bull", "model_version": "opt-test", "reasons": ["r"],
        },
        user_id=1,
    )
    pending = fetch_all("SELECT * FROM TOptionPrediction WHERE Status='pending'")
    assert len(pending) == 1
    target = datetime.fromisoformat(pending[0]["TargetTime"])

    # before target → not evaluated (no false marks)
    assert store.evaluate_due(
        user_id=1, underlying="^NSEI", premiums={"NIFTYX22350": 125.0}, spot=22366.0,
        now_ist=target - timedelta(minutes=1),
    ) == 0
    # after target with matching contract → evaluated once
    assert store.evaluate_due(
        user_id=1, underlying="^NSEI", premiums={"NIFTYX22350": 125.0}, spot=22366.0,
        now_ist=target + timedelta(minutes=2),
    ) == 1
    # idempotent
    assert store.evaluate_due(
        user_id=1, underlying="^NSEI", premiums={"NIFTYX22350": 125.0}, spot=22366.0,
        now_ist=target + timedelta(minutes=3),
    ) == 0
    ev = fetch_all("SELECT * FROM TOptionPrediction WHERE Status='evaluated'")
    assert len(ev) == 1
    assert ev[0]["AbsError"] == pytest.approx(1.0)
    stats = store.option_stats(1, "^NSEI")
    assert stats["evaluated"] == 1 and stats["pending"] == 0


# --- regime classes -----------------------------------------------------------

def test_regime_breakout_breakdown_and_low_vol():
    from analyst.regime import detect_regime

    base = {"ohlcv": {"close": 100}, "ema9": 101, "ema20": 100, "rsi": 65, "adx": 30, "atr": 1.0,
            "vol_ratio": 2.0, "bb_width": 0.08, "trend_dir": "bullish"}
    assert detect_regime(dict(base)).regime == "breakout"
    down = dict(base, ema9=99, ema20=100, rsi=35, trend_dir="bearish")
    assert detect_regime(down).regime == "breakdown"
    quiet = dict(base, adx=15, rsi=50, atr=0.3, bb_width=0.03, vol_ratio=0.8, trend_dir="neutral", ema9=100, ema20=100)
    assert detect_regime(quiet).regime == "low_volatility"


def test_regime_uncertain_wins_over_sideways():
    from analyst.regime import detect_regime

    ctx = {"ohlcv": {"close": 100}, "ema9": 100, "ema20": 100, "rsi": 50, "adx": 20, "atr": 0.5,
           "vol_ratio": 1.0, "bb_width": 0.05, "trend_dir": "neutral"}
    state = detect_regime(ctx)
    assert state.regime == "uncertain"
    assert "trend_following" in state.de_emphasized  # conflicting reads dampen conviction
    assert state.preferred_techniques == ["support_resistance", "volume"]


def test_chart_series_keeps_the_original_forecast(sqlite_db):
    from prediction import archive

    target = datetime(2026, 10, 12, 5, 30, tzinfo=timezone.utc)
    first = target - timedelta(minutes=15)
    archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(pred=105.0), market_price=100.0,
        horizon="15m", timeframe="15m", scheduled_key=archive.make_scheduled_key(1, "TEST.NS", "15m", first),
        target_time=target, model_version="angad-horizon-v1",
    )
    revised = first + timedelta(minutes=1)
    archive.save_prediction(
        user_id=1, symbol="TEST.NS", result=_pred_result(pred=110.0), market_price=101.0,
        horizon="15m", timeframe="15m", scheduled_key=archive.make_scheduled_key(1, "TEST.NS", "15m", revised),
        target_time=target, model_version="angad-horizon-v1",
    )
    frame = archive.chart_series(1, "TEST.NS", horizon="15m")
    assert len(frame) == 1
    assert frame.iloc[0]["predicted_price"] == pytest.approx(105.0)
    assert frame.iloc[0]["actual_price"] is None or pd.isna(frame.iloc[0]["actual_price"])


def test_chart_series_null_target_time_uses_created_at(sqlite_db):
    """Pandas 3 rejects loc-filling datetime64 columns; older rows have no TargetTime."""
    from db.database import execute
    from prediction import archive

    now = datetime(2026, 9, 26, 16, 54, 56, 647000, tzinfo=timezone.utc)
    for i in range(72):
        created = now - timedelta(minutes=5 * i)
        execute(
            """
            INSERT INTO TPrediction (
                UserId, Symbol, Exchange, MarketPrice, Horizon, PredictedPrice, PriceLow, PriceHigh,
                Direction, Signal, Confidence, Timeframe, TargetTime, CreatedAt, Status
            ) VALUES (1,'NULLT.NS','NSE',100,'5m',101,99,103,'bullish','BUY',55,'5m',NULL,?, 'pending')
            """,
            (created.strftime("%Y-%m-%dT%H:%M:%S.") + f"{created.microsecond // 1000:03d}Z",),
        )
    frame = archive.chart_series(1, "NULLT.NS", horizon="5m")
    assert len(frame) == 72
    assert frame["predicted_price"].notna().all()


def test_model_version_is_seeded(sqlite_db):
    from db.database import fetch_one

    row = fetch_one("SELECT Status, Description FROM TModelVersion WHERE ModelVersion='angad-horizon-v1'")
    assert row is not None
    assert row["Status"] == "active"
    assert "uncalibrated" in row["Description"]


def test_empty_nse_chain_falls_through_to_yahoo(monkeypatch):
    import pandas as pd

    from data.cache import APP_CACHE
    from options import chain

    APP_CACHE.clear()
    monkeypatch.setattr(chain.nse, "nse_pair", lambda _s: ("NIFTY", "Indices"))
    monkeypatch.setattr(chain.nse, "fetch_chain_payload", lambda *_a, **_k: {"records": {"data": []}})
    monkeypatch.setattr(
        chain,
        "_yahoo_chain",
        lambda _s, _e: {
            "calls": pd.DataFrame([{"strike": 24000, "ltp": 100}]),
            "puts": pd.DataFrame(),
            "note": "",
            "source": "yahoo",
            "ticker": "^NSEI",
        },
    )
    out = chain.fetch_chain("^NSEI", "2026-10-30")
    assert out["source"] == "yahoo"
    assert not out["calls"].empty
    APP_CACHE.clear()
