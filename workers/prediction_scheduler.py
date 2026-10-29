"""Continuous market prediction engine.

A single background thread (started with the internal API server, not the
Streamlit browser session) generates and evaluates predictions for every
active TLiveWatch row. Closing the UI does not stop predictions; restarting
the app resumes because scheduled jobs are keyed by
(user, symbol, horizon, minute) and stored with SQLite unique constraints.

Chart refresh and prediction generation are deliberately separate:
refreshing a chart never enqueues work here.
"""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from utils.logging import get_logger

logger = get_logger(__name__)

IST = ZoneInfo("Asia/Kolkata")
MAX_TICK_SECONDS = 240  # a tick that overshoots is skipped, never queued up

_thread: threading.Thread | None = None
_stop = threading.Event()
DEFAULT_HORIZONS = ("1m", "5m", "15m", "30m", "60m", "eod")


# ---------------------------------------------------------------------------
# Watch list (per-user, persisted in SQLite — survives restarts)
# ---------------------------------------------------------------------------

def set_watch(user_id: int, symbol: str, active: bool, *, interval_seconds: int = 60,
              horizons: list[str] | None = None) -> None:
    from db.database import execute, fetch_one

    symbol = symbol.upper()
    hz = ",".join(horizons or list(DEFAULT_HORIZONS))
    row = fetch_one("SELECT WatchId FROM TLiveWatch WHERE UserId=? AND Symbol=?", (int(user_id), symbol))
    if row:
        if active:
            execute(
                "UPDATE TLiveWatch SET IsActive=1, IntervalSeconds=?, Horizons=?, "
                "UpdatedAt=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE WatchId=?",
                (int(interval_seconds), hz, int(row["WatchId"])),
            )
        else:
            execute("UPDATE TLiveWatch SET IsActive=0, UpdatedAt=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE WatchId=?",
                    (int(row["WatchId"]),))
    elif active:
        execute(
            "INSERT INTO TLiveWatch (UserId, Symbol, IntervalSeconds, Horizons) VALUES (?, ?, ?, ?)",
            (int(user_id), symbol, int(interval_seconds), hz),
        )


def list_watch(active_only: bool = True) -> list[dict[str, Any]]:
    from db.database import fetch_all

    where = "WHERE IsActive=1" if active_only else ""
    return fetch_all(f"SELECT * FROM TLiveWatch {where} ORDER BY WatchId")


def watch_exists(user_id: int, symbol: str) -> bool:
    """True once a watch row exists, including one the user turned off."""
    from db.database import fetch_one

    row = fetch_one(
        "SELECT WatchId FROM TLiveWatch WHERE UserId=? AND Symbol=?",
        (int(user_id), symbol.upper()),
    )
    return row is not None


def is_watched(user_id: int, symbol: str) -> bool:
    from db.database import fetch_one

    row = fetch_one(
        "SELECT 1 FROM TLiveWatch WHERE UserId=? AND Symbol=? AND IsActive=1",
        (int(user_id), symbol.upper()),
    )
    return row is not None


# ---------------------------------------------------------------------------
# Core tick
# ---------------------------------------------------------------------------

def run_tick(settings: dict | None = None) -> dict[str, int]:
    """One scheduling pass: evaluate due targets, then generate new predictions.

    Safe to call from tests; returns counters.
    """
    from config.loader import load_settings
    from market_calendar import SessionPhase, get_market_status
    from prediction import archive
    from services.market_service import MarketService

    settings = settings or load_settings()
    engine_cfg = settings.get("prediction_engine", {}) or {}
    market = MarketService(settings)
    now_ist = datetime.now(IST)
    ms = get_market_status(now_ist)
    counters = {"generated": 0, "evaluated": 0, "skipped": 0, "errors": 0}
    seen: set[tuple[int, str]] = set()

    for watch in list_watch():
        uid, symbol = int(watch["UserId"]), str(watch["Symbol"])
        key = (uid, symbol)
        if key in seen:
            continue
        seen.add(key)
        horizons = [h for h in str(watch["Horizons"] or "").split(",") if h] or list(DEFAULT_HORIZONS)
        try:
            counters["evaluated"] += _evaluate(market, uid, symbol)
            if ms.phase == SessionPhase.OPEN:
                counters["generated"] += _generate(market, ms, uid, symbol, horizons, now_ist)
            else:
                counters["skipped"] += 1
        except Exception as exc:
            counters["errors"] += 1
            logger.warning("prediction tick failed for %s: %s", symbol, exc)
            logger.debug(traceback.format_exc())
    return counters


def _stale_bars(bars, now_ist: datetime) -> bool:
    """True when the newest bar is too old to trust for a live prediction."""
    if bars is None or len(bars) == 0:
        return True
    last = bars.index[-1]
    if getattr(last, "tzinfo", None) is None:
        last = last.replace(tzinfo=IST)
    return (now_ist - last.astimezone(IST)).total_seconds() > 12 * 60


def _evaluate(market, user_id: int, symbol: str) -> int:
    from prediction import archive

    bars = market.get_session_ohlcv(symbol)
    if bars is None or bars.empty:
        bars = market.get_ohlcv(symbol, "5d", "1d")
    if bars is None or bars.empty:
        return 0
    return archive.evaluate_due(user_id, symbol, bars, datetime.now(timezone.utc))


def _frame_score(frame) -> tuple[float, str] | None:
    """Rule score for a higher timeframe. None when the frame is too short to trust."""
    from indicators.calculator import apply_all_indicators, build_indicator_context
    from prediction.rule_engine import predict_rule_based

    if frame is None or len(frame) < 20:
        return None
    try:
        ind = apply_all_indicators(frame)
        ctx = build_indicator_context(ind)
    except Exception:
        return None
    if not ctx.get("atr"):
        return None
    rule = predict_rule_based(ind, ctx)
    return float(rule.score), str(ctx.get("trend_dir") or "neutral")


def _higher_frames(market, symbol: str, raw_5m):
    """15m/30m/60m from the 5m tape, plus daily and weekly when those fetches work.

    Each frame is scored on its own. Missing frames are reported as None so the
    blend can say what it did not see.
    """
    from prediction.horizon_engine import resample_ohlcv

    yield "15m", _frame_score(resample_ohlcv(raw_5m, "15min"))
    yield "30m", _frame_score(resample_ohlcv(raw_5m, "30min"))
    yield "60m", _frame_score(resample_ohlcv(raw_5m, "60min"))
    daily = None
    try:
        daily = market.get_ohlcv(symbol, "1y", "1d")
    except Exception:
        daily = None
    yield "1d", _frame_score(daily)
    weekly = None
    try:
        weekly = resample_ohlcv(daily, "W-FRI") if daily is not None else None
    except Exception:
        weekly = None
    yield "1w", _frame_score(weekly)


def _generate(market, ms, user_id: int, symbol: str, horizons: list[str], now_ist: datetime) -> int:
    from analyst.regime import detect_regime
    from analyst.strategy_registry import choose_primary, record_signal
    from indicators.calculator import apply_all_indicators, build_indicator_context
    from prediction import archive
    from prediction.horizon_engine import blend_timeframe_score, horizon_prediction, signal_from_probs
    from prediction.models import PredictionResult
    from prediction.rule_engine import predict_rule_based

    raw = market.get_analysis_ohlcv(symbol, "5d", "5m")
    if raw is None or raw.empty:
        return 0
    df = apply_all_indicators(raw)
    if _stale_bars(df, now_ist):
        return 0  # provider failure / stale tape: never fabricate a prediction
    ctx = build_indicator_context(df)
    rule = predict_rule_based(df, ctx)
    regime = detect_regime(ctx, None)

    score = float(rule.score)
    trend = str(ctx.get("trend_dir") or "neutral")
    notes: list[str] = []
    for label, frame in _higher_frames(market, symbol, raw):
        if frame is None:
            notes.append(f"{label}: not enough bars — left out of the context blend.")
            continue
        score, extra = blend_timeframe_score(score, trend, frame[0], frame[1])
        score = max(-6.0, min(6.0, score))
        notes.extend(extra)

    default_strategy = str(
        (rule.raw or {}).get("trade_plan", {}).get("strategy_id")
        or regime.regime.split("_")[0]
        or "Alpha"
    )
    chosen, selection = choose_primary(
        default_strategy,
        regime.regime,
        "5m",
        ["Alpha", "Beta", "Gamma", default_strategy],
    )
    strategy_id = chosen
    if selection.get("selection_note"):
        notes.append(str(selection["selection_note"]))

    base = float(df["Close"].iloc[-1])
    atr = float(ctx.get("atr") or 0)
    bars_available = int(len(df))
    gen_minute = now_ist.replace(second=0, microsecond=0)
    created = 0
    for horizon in horizons:
        p = horizon_prediction(
            base_price=base,
            atr_bar=atr,
            score=score,
            horizon=horizon,
            bar_minutes=5,
            now_ist=now_ist,
            session_close_ist=ms.session_close_ist,
            bars_available=bars_available,
        )
        if p is None:
            continue  # NO_PREDICTION / UNCERTAIN — nothing stored, nothing faked
        signal = signal_from_probs((p["prob_up"], p["prob_sideways"], p["prob_down"]))
        if signal == "BUY":
            stop = round(base - 1.5 * p["sigma"], 2)
        elif signal == "SELL":
            stop = round(base + 1.5 * p["sigma"], 2)
        else:
            stop = round(base - 1.0 * p["sigma"], 2)
        reasons = list(rule.reasons_simple[:4]) + notes + [
            f"Horizon {horizon}: drift {p['drift']:+.2f}, sigma {p['sigma']:.2f}; "
            f"P(up/side/down)={p['prob_up']}/{p['prob_sideways']}/{p['prob_down']} "
            f"({p['prob_source']})."
        ]
        result = PredictionResult(
            signal=signal,
            confidence=p["confidence"],
            predicted_price=p["predicted_price"],
            target_price=p["predicted_price"],
            stop_loss=stop,
            price_low=p["price_low"],
            price_high=p["price_high"],
            trend=ctx.get("trend_dir", "neutral"),
            risk_level=rule.risk_level,
            score=round(score, 3),
            market_regime=regime.regime,
            reasons=reasons,
            reasons_simple=reasons,
            indicator_snapshot=ctx,
            source="HORIZON_ENGINE",
            raw={"horizon": p, "strategies": {"master_regime": regime.regime, "primary_strategy": strategy_id}},
        )
        pid = archive.save_prediction(
            user_id=user_id,
            symbol=symbol,
            result=result,
            market_price=base,
            horizon=horizon,
            timeframe=horizon,
            target_time=p["target_time"],
            scheduled_key=archive.make_scheduled_key(user_id, symbol, horizon, gen_minute),
            model_version=p["model_version"],
            probs=(p["prob_up"], p["prob_sideways"], p["prob_down"]),
            strategy_id=strategy_id,
        )
        if pid:
            created += 1
            try:
                record_signal(strategy_id, f"{strategy_id} horizon", regime.regime, horizon)
            except Exception:
                pass
    return created


# ---------------------------------------------------------------------------
# Thread lifecycle
# ---------------------------------------------------------------------------

def _loop(settings: dict) -> None:
    interval = int((settings.get("prediction_engine", {}) or {}).get("interval_seconds", 60))
    interval = max(15, min(interval, MAX_TICK_SECONDS))
    logger.info("prediction scheduler online every %ss", interval)
    while not _stop.is_set():
        started = time.monotonic()
        try:
            if str(__import__("os").environ.get("ANGAD_SCHEDULER", "1")) != "0":
                run_tick(settings)
        except Exception as exc:
            logger.warning("prediction scheduler tick error: %s", exc)
        elapsed = time.monotonic() - started
        _stop.wait(max(interval - elapsed, 1.0))


def start(settings: dict) -> None:
    """Start the scheduler exactly once per process (idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(settings,), daemon=True, name="angad-predictions")
    _thread.start()


def stop() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
        _thread = None
