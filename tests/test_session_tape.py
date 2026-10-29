"""Session tape: AI predicted vs actual prints."""

from datetime import datetime
from zoneinfo import ZoneInfo

from prediction.session_tape import SessionTapeStore

IST = ZoneInfo("Asia/Kolkata")


def test_session_tape_keeps_history(tmp_path):
    store = SessionTapeStore(tmp_path / "predictions.json")
    t0 = datetime(2026, 9, 26, 10, 0, tzinfo=IST)
    store.append(
        symbol="^NSEI",
        predicted_price=100.0,
        actual_price=99.5,
        signal="BUY",
        confidence=70,
        now=t0,
        min_interval_seconds=0,
    )
    store.append(
        symbol="^NSEI",
        predicted_price=101.2,
        actual_price=100.1,
        signal="BUY",
        confidence=72,
        now=datetime(2026, 9, 26, 10, 1, tzinfo=IST),
        min_interval_seconds=0,
    )
    tracks = store.series_for("^NSEI", t0.date())
    assert len(tracks["predicted"]) == 2
    assert list(tracks["predicted"].values) == [100.0, 101.2]
    assert list(tracks["actual"].values) == [99.5, 100.1]


def test_session_tape_debounce(tmp_path):
    store = SessionTapeStore(tmp_path / "predictions.json")
    t0 = datetime(2026, 9, 26, 10, 0, tzinfo=IST)
    store.append(
        symbol="RELIANCE.NS",
        predicted_price=1400,
        actual_price=1399,
        signal="HOLD",
        confidence=50,
        now=t0,
        min_interval_seconds=50,
    )
    store.append(
        symbol="RELIANCE.NS",
        predicted_price=1401,
        actual_price=1398,
        signal="HOLD",
        confidence=51,
        now=t0,
        min_interval_seconds=50,
    )
    tracks = store.series_for("RELIANCE.NS", t0.date())
    assert len(tracks["predicted"]) == 1
