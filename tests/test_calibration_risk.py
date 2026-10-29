"""Calibration, sizing, Greeks, audit, and evaluation — deterministic fixtures only."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from analyst.sizing import theoretical_size
from analyst.trade_plan import build_trade_plan, classify_setup_status
from options.greeks import theoretical_greeks
from prediction.archive import evaluate_row


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    db_file = tmp_path / "calib.db"
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(db_file))
    from db.bootstrap import initialize
    from db.database import execute

    initialize()
    execute("INSERT INTO TReadUser (UserId, Username, Email, PasswordHash) VALUES (1,'t','t@t','x')")
    yield db_file


def test_evaluate_row_direction_and_range():
    row = {
        "MarketPrice": 100.0,
        "PredictedPrice": 102.0,
        "PriceLow": 101.0,
        "PriceHigh": 104.0,
    }
    hit = evaluate_row(row, {"close": 103.0, "time": "t", "high": 104.0, "low": 102.0})
    assert hit["direction_ok"] == 1
    assert hit["range_ok"] == 1
    assert hit["signed_error"] == 1.0
    miss = evaluate_row(row, {"close": 99.0, "time": "t", "high": 100.0, "low": 98.0})
    assert miss["direction_ok"] == 0
    assert miss["range_ok"] == 0


def test_sizing_requires_capital_and_respects_stop():
    empty = theoretical_size(entry=100, stop=98, capital=None)
    assert empty["configured"] is False
    assert empty["qty"] == 0
    ok = theoretical_size(entry=100, stop=98, capital=100_000, max_risk_pct=1.0)
    assert ok["configured"] is True
    assert ok["qty"] > 0
    assert ok["risk_rupees"] <= ok["budget_rupees"] * 1.01
    tight = theoretical_size(entry=100, stop=1, capital=1000, max_risk_pct=0.5)
    assert tight["qty"] == 0
    assert tight["exceeds_risk"] is True
    opt = theoretical_size(entry=50, stop=1, capital=20_000, is_option_buy=True, premium=50, lot_size=15)
    assert opt["note"].startswith("Long option")
    assert opt["qty"] % 15 == 0


def test_trade_plan_no_trade_when_rr_weak():
    plan = build_trade_plan(
        symbol="TEST.NS",
        name="TEST",
        spot=100,
        signal="BUY",
        trend="bullish",
        confidence=80,
        predicted_price=100.2,
        atr=0.2,
        support=99.9,
        resistance=101,
        regime="sideways",
        strategy_id="Alpha",
        strategy_name="Trend",
        risk_plan={"stop_loss": 99.95, "target_price": 100.15},
        reasons=["thin edge"],
    )
    assert plan["rr"] < 1.5
    assert plan["status"] == "NO TRADE"
    assert "entry_reason" in plan
    assert plan["sizing"]["configured"] is False


def test_classify_stop_not_widened():
    status = classify_setup_status(
        signal="BUY",
        spot=90,
        entry_low=99,
        entry_high=101,
        stop=95,
        target1=110,
        target2=120,
        rr=2.0,
        previous="ENTRY",
    )
    assert status == "STOP LOSS"


def test_theoretical_call_greeks_labelled():
    g = theoretical_greeks(spot=100, strike=100, days_remaining=30, iv=0.2, right="CE", ltp=3.0)
    assert g["source"] == "black_scholes_theoretical"
    assert g["delta"] is not None and 0.4 < g["delta"] < 0.7
    assert g["intrinsic"] == 0.0
    assert g["extrinsic"] == 3.0
    missing = theoretical_greeks(spot=100, strike=100, days_remaining=10, iv=None, right="CE")
    assert missing["delta"] is None
    assert "IV" in missing["unavailable"]


def test_calibration_preliminary_and_baselines(sqlite_db):
    from db.database import execute
    from prediction.calibration import baseline_comparison, evaluate_calibration

    cal = evaluate_calibration(1, "AAA.NS")
    assert cal["preliminary"] is True
    assert cal["n"] == 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for i in range(12):
        execute(
            """
            INSERT INTO TPrediction (
                UserId, Symbol, Exchange, MarketPrice, Horizon, PredictedPrice, PriceLow, PriceHigh,
                Direction, Signal, Confidence, Status, Timeframe, AbsError, ErrorPct, DirectionOk,
                ActualPrice, ProbUp, ProbDown, ProbSideways, CreatedAt
            ) VALUES (1,'AAA.NS','NSE',100,'1d',?,99,105,'bullish','BUY',60,'evaluated','1d',
                      ?,1.0,?,?, 70, 20, 10, ?)
            """,
            (101 + (i % 3), abs(2 - i % 3), 1 if i % 2 == 0 else 0, 100 + (i % 4), now),
        )
    base = baseline_comparison(1, "AAA.NS")
    assert base["n"] == 12
    assert base["preliminary"] is False
    assert base["model_mae"] is not None
    cal2 = evaluate_calibration(1, "AAA.NS")
    assert cal2["n"] == 12
    assert cal2["preliminary"] is True  # needs 30


def test_audit_on_save(sqlite_db):
    from prediction.archive import save_prediction
    from prediction.audit import recent
    from prediction.models import PredictionResult

    result = PredictionResult(
        signal="BUY",
        confidence=60.0,
        predicted_price=105.0,
        target_price=105.0,
        stop_loss=99.0,
        price_low=102.0,
        price_high=108.0,
        trend="bullish",
        risk_level="Medium",
        score=2.0,
        market_regime="trending_bull",
        reasons=["test"],
        reasons_simple=["test"],
        indicator_snapshot={"rsi": 55, "atr": 1.0},
    )
    pid = save_prediction(
        user_id=1,
        symbol="BBB.NS",
        result=result,
        market_price=100.0,
        horizon="15m",
        min_interval_seconds=0,
        timeframe="15m",
        target_time=datetime.now(timezone.utc),
        scheduled_key="1|BBB.NS|15m|testkey",
        probs=(55.0, 20.0, 25.0),
    )
    assert pid
    logs = recent(1, limit=10)
    assert any(r.get("Action") == "prediction_saved" for r in logs)
