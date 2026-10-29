"""In-process trading gateway used by FastAPI and Streamlit. No third-party keys leave this layer."""

from __future__ import annotations

from typing import Any

from api.jsonutil import jsonable
from config.loader import load_settings
from knowledge.search import search_knowledge
from services.api_monitor import log_usage
from services.analysis_service import AnalysisService
from utils.logging import get_logger

logger = get_logger(__name__)

_analysis: AnalysisService | None = None


def analysis_service() -> AnalysisService:
    global _analysis
    if _analysis is None:
        _analysis = AnalysisService(load_settings())
    return _analysis


def _log_internal(operation: str, *, success: bool, error: str | None = None) -> None:
    log_usage(
        "angad_internal",
        operation=operation,
        success=success,
        endpoint=f"internal://{operation}",
        error=error,
    )


def _provider_meta(df) -> dict[str, Any]:
    attrs = getattr(df, "attrs", None) or {}
    fallback = str(attrs.get("fallback_api") or "")
    note = str(attrs.get("unavailable_note") or "")
    provider = fallback or "yfinance"
    delay = "Daily close from a free unofficial source (Yahoo or Stooq). Not a live NSE/BSE tape."
    if fallback == "stooq":
        delay = "Stooq daily CSV fallback. Intraday tape is unavailable."
    as_of = None
    if df is not None and not df.empty:
        as_of = str(df.index[-1])
    return {
        "provider": provider,
        "fallback_used": bool(fallback),
        "delay_note": delay,
        "unavailable_note": note or None,
        "as_of": as_of,
        "fresh": bool(as_of) and not note,
    }


def get_quote(symbol: str) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "Symbol is required.", "code": "validation"}
    try:
        svc = analysis_service().market
        df = svc.get_ohlcv(symbol, "5d", "1d")
        if df is None or df.empty:
            df = svc.get_ohlcv(symbol, "1mo", "1d")
        if df is None or df.empty:
            df = svc.get_ohlcv(symbol, "3mo", "1d")
        if df is None or df.empty:
            _log_internal("quote", success=False, error="no_data")
            return {
                "ok": False,
                "error": f"No free market data for {symbol}. Yahoo and Stooq returned no bars.",
                "code": "unavailable",
                "symbol": symbol,
                **_provider_meta(df),
            }
        last = df.iloc[-1]
        prev_close = None
        if len(df) >= 2:
            try:
                prev_close = jsonable(float(df.iloc[-2]["Close"]))
            except (TypeError, ValueError, KeyError):
                prev_close = None
        _log_internal("quote", success=True)
        return {
            "ok": True,
            "symbol": symbol,
            "open": jsonable(float(last["Open"])),
            "high": jsonable(float(last["High"])),
            "low": jsonable(float(last["Low"])),
            "price": jsonable(float(last["Close"])),
            "previous_close": prev_close,
            "volume": jsonable(float(last["Volume"])),
            **_provider_meta(df),
        }
    except Exception as exc:
        logger.exception("quote failed")
        _log_internal("quote", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Market quote failed.", "code": "error", "symbol": symbol}


def get_history(symbol: str, period: str = "3mo", interval: str = "1d") -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    try:
        df = analysis_service().market.get_ohlcv(symbol, period, interval)
        if df is None or df.empty:
            _log_internal("history", success=False, error="no_data")
            return {
                "ok": False,
                "error": f"No OHLCV for {symbol} ({period}/{interval}).",
                "code": "unavailable",
                "symbol": symbol,
            }
        bars = []
        for ts, row in df.tail(400).iterrows():
            bars.append(
                {
                    "t": str(ts),
                    "open": jsonable(float(row["Open"])),
                    "high": jsonable(float(row["High"])),
                    "low": jsonable(float(row["Low"])),
                    "close": jsonable(float(row["Close"])),
                    "volume": jsonable(float(row["Volume"])),
                }
            )
        meta = _provider_meta(df)
        _log_internal("history", success=True)
        return {
            "ok": True,
            "symbol": symbol,
            "period": period,
            "interval": str((df.attrs or {}).get("resolved_interval") or interval),
            "bars": bars,
            "bar_count": len(bars),
            **meta,
        }
    except Exception as exc:
        logger.exception("history failed")
        _log_internal("history", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "History fetch failed.", "code": "error", "symbol": symbol}


def get_indicators(symbol: str, period: str = "3mo", interval: str = "1d") -> dict[str, Any]:
    from indicators.calculator import apply_all_indicators, build_indicator_context

    hist = get_history(symbol, period, interval)
    if not hist.get("ok"):
        return hist
    df = analysis_service().market.get_ohlcv(symbol, period, interval)
    ctx = build_indicator_context(apply_all_indicators(df))
    snap = dict(ctx)
    fib = snap.get("fibonacci")
    if fib is not None and hasattr(fib, "retracements"):
        snap["fibonacci"] = {
            "swing_high": jsonable(fib.swing_high),
            "swing_low": jsonable(fib.swing_low),
            "trend": fib.trend,
            "nearest_support": jsonable(fib.nearest_support),
            "nearest_resistance": jsonable(fib.nearest_resistance),
        }
    _log_internal("indicators", success=True)
    log_usage("local_ta", operation="indicators_api", success=True, endpoint="local://indicators.technical")
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "indicators": jsonable(snap),
        "provider": hist.get("provider"),
        "delay_note": hist.get("delay_note"),
        "as_of": hist.get("as_of"),
        "fallback_used": hist.get("fallback_used"),
    }


def get_analysis(
    symbol: str,
    *,
    period: str = "3mo",
    interval: str = "1d",
    user_id: int | None = None,
    include_world_news: bool = True,
) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    try:
        result = analysis_service().analyze(
            symbol=symbol,
            period=period,
            interval=interval,
            use_genai=False,
            include_world_news=include_world_news,
            user_id=user_id,
        )
        if result.get("error"):
            _log_internal("analysis", success=False, error=str(result["error"]))
            return {"ok": False, "error": result["error"], "code": "unavailable", "symbol": symbol}
        primary = result["primary"]
        payload = primary.to_dict()
        payload.pop("raw", None)
        raw = primary.raw or {}
        _log_internal("analysis", success=True)
        return {
            "ok": True,
            "symbol": symbol,
            "latest_price": jsonable(result.get("latest_price")),
            "prediction": jsonable(payload),
            "explanation": jsonable(result.get("explanation") or {}),
            "regime": jsonable(getattr(result.get("regime"), "__dict__", result.get("regime"))),
            "trade_plan": jsonable(raw.get("trade_plan") or result.get("trade_plan")),
            "market_frames": jsonable(raw.get("market_frames") or result.get("market_frames")),
            "scenarios": jsonable(raw.get("scenarios") or []),
            "similar_setups": jsonable(raw.get("similar_setups") or result.get("similar_setups") or {}),
            "fallback_note": result.get("fallback_note") or None,
            "disclaimer": "Educational analysis only — a model path, not a guaranteed outcome and not financial advice.",
            **_provider_meta(result.get("df_ist")),
        }
    except Exception as exc:
        logger.exception("analysis failed")
        _log_internal("analysis", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Analysis failed.", "code": "error", "symbol": symbol}


def get_option_chain(
    symbol: str,
    *,
    expiry: str | None = None,
    nearest: bool = False,
    right: str | None = None,
    strike: float | None = None,
    view: str = "all",
    user_id: int | None = None,
    include_rec: bool = False,
) -> dict[str, Any]:
    from options.chain import expiry_meta, fetch_chain, list_expiries
    from options.intelligence import display_chain, recommend

    symbol = (symbol or "").strip().upper()
    try:
        resolved, expiries = list_expiries(symbol)
        if not expiries:
            _log_internal("option_chain", success=False, error="no_expiries")
            return {
                "ok": False,
                "error": "Option-chain data is currently unavailable. Please try again.",
                "code": "unavailable",
                "symbol": symbol,
            }
        chosen = expiry if expiry in expiries else (expiries[0] if nearest or not expiry else expiry)
        if chosen not in expiries:
            chosen = expiries[0]
        chain = fetch_chain(symbol, chosen)
        calls = chain.get("calls")
        puts = chain.get("puts")
        spot = chain.get("spot")
        if spot is None:
            q = get_quote(symbol)
            spot = q.get("price") if q.get("ok") else None
        spot_f = float(spot) if spot is not None else None
        n_atm = 11 if view in ("atm", "all") else 21
        if view == "high_oi":
            n_atm = 21
        call_tbl = display_chain(calls, spot_f or 0, limit=n_atm) if spot_f else calls
        put_tbl = display_chain(puts, spot_f or 0, limit=n_atm) if spot_f else puts
        if view == "calls":
            put_tbl = put_tbl.iloc[0:0] if hasattr(put_tbl, "iloc") else put_tbl
        elif view == "puts":
            call_tbl = call_tbl.iloc[0:0] if hasattr(call_tbl, "iloc") else call_tbl
        elif view == "high_oi":
            if call_tbl is not None and not getattr(call_tbl, "empty", True) and "open_interest" in call_tbl.columns:
                call_tbl = call_tbl.sort_values("open_interest", ascending=False).head(8)
            if put_tbl is not None and not getattr(put_tbl, "empty", True) and "open_interest" in put_tbl.columns:
                put_tbl = put_tbl.sort_values("open_interest", ascending=False).head(8)
        contract_row = None
        if strike is not None and right:
            side = calls if str(right).upper() == "CE" else puts
            if side is not None and not getattr(side, "empty", True) and "strike" in side.columns:
                ranked = (side["strike"] - float(strike)).abs()
                contract_row = side.loc[ranked.idxmin()].to_dict()
        rec = None
        if spot_f and include_rec:
            analysis = get_analysis(symbol, user_id=user_id, include_world_news=False)
            pred = (analysis.get("prediction") or {}) if analysis.get("ok") else {}
            rec = recommend(
                underlying=symbol,
                spot=spot_f,
                predicted_underlying=float(pred.get("predicted_price") or spot_f),
                signal=str(pred.get("signal") or "HOLD"),
                trend=str(pred.get("trend") or ""),
                confidence=float(pred.get("confidence") or 0),
                rsi=None,
                macd=None,
                atr=None,
                vwap=None,
                expiry=chosen,
                days_remaining=int(expiry_meta(chosen).get("days_remaining") or -1),
                calls=calls,
                puts=puts,
            )
        empty = (call_tbl is None or getattr(call_tbl, "empty", True)) and (put_tbl is None or getattr(put_tbl, "empty", True))
        _log_internal("option_chain", success=not empty)
        return {
            "ok": not empty,
            "symbol": symbol,
            "resolved": resolved,
            "source": chain.get("source"),
            "expiry": chosen,
            "expiries": expiries[:12],
            "spot": jsonable(spot_f),
            "meta": expiry_meta(chosen),
            "calls": jsonable(
                call_tbl.fillna("").to_dict(orient="records") if call_tbl is not None and hasattr(call_tbl, "to_dict") else []
            ),
            "puts": jsonable(
                put_tbl.fillna("").to_dict(orient="records") if put_tbl is not None and hasattr(put_tbl, "to_dict") else []
            ),
            "contract": jsonable(contract_row),
            "recommendation": jsonable(
                {
                    "action": rec.get("action"),
                    "setup_status": rec.get("setup_status"),
                    "bias": (rec.get("prediction") or {}).get("bias"),
                    "confidence": (rec.get("prediction") or {}).get("confidence"),
                    "contract": rec.get("contract"),
                    "strike": rec.get("strike"),
                    "entry_low": rec.get("entry_low"),
                    "entry_high": rec.get("entry_high"),
                    "stop": rec.get("stop"),
                    "stop_reason": rec.get("stop_reason"),
                    "target1": rec.get("target1"),
                    "target2": rec.get("target2"),
                    "wait_text": rec.get("wait_text"),
                    "reasons": rec.get("reasons"),
                    "candidates": rec.get("candidates"),
                    "separate_from_trade": True,
                }
                if rec
                else None
            ),
            "note": chain.get("note") or (None if not empty else "Option-chain data is currently unavailable. Please try again."),
            "error": None if not empty else "Option-chain data is currently unavailable. Please try again.",
        }
    except Exception as exc:
        logger.exception("option chain failed")
        _log_internal("option_chain", success=False, error=str(exc)[:400])
        return {
            "ok": False,
            "error": "Option-chain data is currently unavailable. Please try again.",
            "code": "error",
            "symbol": symbol,
        }


def get_screener() -> dict[str, Any]:
    from analyst.screener import scan_universe

    try:
        rows = scan_universe(analysis_service().market)
        _log_internal("screener", success=True)
        return {
            "ok": True,
            "rows": jsonable(rows),
            "disclaimer": "Ranked by confirmation, liquidity proxy, and risk/reward — not highest model probability alone. Not a buy list.",
        }
    except Exception as exc:
        logger.exception("screener failed")
        _log_internal("screener", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Universe scan failed.", "code": "error"}


def get_compare(symbol_a: str, symbol_b: str, *, user_id: int | None = None) -> dict[str, Any]:
    """Read-only side-by-side using the existing analysis pipeline. Not a trade."""
    a = get_analysis(symbol_a, user_id=user_id, include_world_news=False)
    b = get_analysis(symbol_b, user_id=user_id, include_world_news=False)
    return {
        "ok": bool(a.get("ok") or b.get("ok")),
        "a": a,
        "b": b,
        "disclaimer": "Comparison of two desk analyses. Directional views are not P&L.",
    }


def get_trade_plan(symbol: str, *, user_id: int | None = None) -> dict[str, Any]:
    analysis = get_analysis(symbol, user_id=user_id, include_world_news=False)
    if not analysis.get("ok"):
        return analysis
    return {
        "ok": True,
        "symbol": analysis.get("symbol"),
        "trade_plan": analysis.get("trade_plan"),
        "market_frames": analysis.get("market_frames"),
        "scenarios": analysis.get("scenarios"),
        "similar_setups": analysis.get("similar_setups"),
        "disclaimer": analysis.get("disclaimer"),
    }


def get_prediction_history(symbol: str, user_id: int, *, limit: int = 40) -> dict[str, Any]:
    from prediction import archive

    rows = archive.list_predictions(int(user_id), symbol.upper() if symbol else None, limit=limit)
    slim = []
    for r in rows:
        slim.append(
            {
                "created_at": r.get("CreatedAt"),
                "symbol": r.get("Symbol"),
                "horizon": r.get("Timeframe"),
                "target_time": r.get("TargetTime"),
                "status": r.get("Status") or ("evaluated" if r.get("ActualPrice") is not None else "pending"),
                "market_price": r.get("MarketPrice"),
                "predicted_price": r.get("PredictedPrice"),
                "price_low": r.get("PriceLow"),
                "price_high": r.get("PriceHigh"),
                "signal": r.get("Signal"),
                "confidence": r.get("Confidence"),
                "regime": r.get("MarketRegime"),
                "actual_price": r.get("ActualPrice"),
                "abs_error": r.get("AbsError"),
                "error_pct": r.get("ErrorPct"),
                "direction_ok": r.get("DirectionOk"),
                "range_ok": r.get("RangeOk"),
                "model_version": r.get("ModelVersion"),
            }
        )
    _log_internal("prediction_history", success=True)
    return {"ok": True, "symbol": (symbol or "").upper() or None, "rows": slim}


def get_prediction_explain(symbol: str, user_id: int) -> dict[str, Any]:
    """Original prediction-time snapshot — do not reconstruct from later prices."""
    import json as _json

    from prediction import archive

    rows = archive.list_predictions(int(user_id), symbol.upper() if symbol else None, limit=10)
    if not rows:
        return {"ok": True, "symbol": (symbol or "").upper(), "rows": [], "note": "No stored predictions."}
    out = []
    for r in rows:
        feats = {}
        raw = r.get("FeaturesJson")
        if raw:
            try:
                feats = _json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception:
                feats = {}
        reasons = r.get("ReasonsJson")
        try:
            reasons = _json.loads(reasons) if isinstance(reasons, str) else reasons
        except Exception:
            reasons = [str(reasons)] if reasons else []
        out.append(
            {
                "prediction_id": r.get("PredictionId"),
                "created_at": r.get("CreatedAt"),
                "instrument": r.get("Symbol"),
                "horizon": r.get("Timeframe"),
                "status": r.get("Status"),
                "facts_at_prediction": {
                    "market_price": r.get("MarketPrice"),
                    "regime": r.get("MarketRegime"),
                    "indicators": {k: feats.get(k) for k in ("rsi", "macd", "atr", "ema9", "ema20", "vwap", "adx", "trend")},
                    "input_note": "These fields were stored at prediction time, not recomputed after the outcome.",
                },
                "model_forecast": {
                    "signal": r.get("Signal"),
                    "predicted_price": r.get("PredictedPrice"),
                    "range": [r.get("PriceLow"), r.get("PriceHigh")],
                    "confidence": r.get("Confidence"),
                    "prob_up": r.get("ProbUp"),
                    "model_version": r.get("ModelVersion"),
                    "strategy_id": feats.get("strategy_id"),
                    "reasons": reasons,
                },
                "outcome": {
                    "actual_price": r.get("ActualPrice"),
                    "direction_ok": r.get("DirectionOk"),
                    "abs_error": r.get("AbsError"),
                    "pending": r.get("Status") == "pending" or r.get("ActualPrice") is None,
                },
            }
        )
    return {"ok": True, "symbol": (symbol or "").upper(), "rows": out}


def get_prediction_performance(symbol: str | None, user_id: int) -> dict[str, Any]:
    """Honest, storage-derived accuracy stats. No fabricated numbers."""
    from prediction import archive

    try:
        stats = archive.performance_stats(int(user_id), symbol.upper() if symbol else None)
        _log_internal("prediction_performance", success=True)
        return {
            "ok": True,
            "symbol": (symbol or "").upper() or None,
            "stats": stats,
            "disclaimer": (
                "Statistics describe stored, completed forecasts only. Pending predictions are "
                "excluded and past accuracy does not guarantee future results."
            ),
        }
    except Exception as exc:
        logger.exception("prediction performance failed")
        _log_internal("prediction_performance", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Prediction statistics unavailable.", "code": "error"}


def get_strategy_registry(regime: str | None = None) -> dict[str, Any]:
    from analyst.strategy_registry import list_registry

    try:
        rows = list_registry(limit=60)
        if regime:
            key = (regime or "").strip().lower().replace(" ", "_")
            rows = [r for r in rows if str(r.get("MarketRegime") or "").lower() == key]
        _log_internal("strategy_registry", success=True)
        return {
            "ok": True,
            "rows": jsonable(rows),
            "disclaimer": "Selection needs at least 20 completed setups per strategy/regime/timeframe; below that, regime defaults are used.",
        }
    except Exception as exc:
        logger.exception("strategy registry failed")
        _log_internal("strategy_registry", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Strategy registry unavailable.", "code": "error"}


def get_news(symbol: str, *, include_world: bool = True) -> dict[str, Any]:
    try:
        equity, world = analysis_service().news.gather(symbol.strip(), include_world)
        _log_internal("news", success=True)
        return {
            "ok": True,
            "symbol": symbol.strip().upper(),
            "equity": jsonable(_news_items(equity)),
            "world": jsonable(_news_items(world)) if include_world else [],
            "delay_note": "Headlines from free Yahoo/RSS sources. Not a complete news wire.",
        }
    except Exception as exc:
        logger.exception("news failed")
        _log_internal("news", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "News is temporarily unavailable.", "code": "unavailable"}


def _news_items(items: list) -> list[dict[str, Any]]:
    out = []
    for h in (items or [])[:12]:
        if isinstance(h, dict):
            out.append(
                {
                    "title": h.get("title") or h.get("headline"),
                    "source": h.get("source") or h.get("publisher"),
                    "published": h.get("published") or h.get("time"),
                }
            )
        else:
            out.append(
                {
                    "title": getattr(h, "title", str(h)),
                    "source": getattr(h, "source", None),
                    "published": str(getattr(h, "published", "") or ""),
                }
            )
    return out


def knowledge_search(query: str, *, limit: int = 5) -> dict[str, Any]:
    hits = search_knowledge(query, limit=limit)
    _log_internal("knowledge", success=True)
    return {"ok": True, "query": query, "hits": hits}


def create_worker_task(*, user_id: int, request_text: str, symbol: str | None = None) -> dict[str, Any]:
    from tasks import store

    task = store.create_task(
        user_id=int(user_id),
        request_text=request_text,
        source="internal_api",
        symbol=symbol,
    )
    _log_internal("task_create", success=True)
    return {
        "ok": True,
        "task_id": task.get("TaskId"),
        "public_id": task.get("PublicId"),
        "status": task.get("Status"),
        "symbol": task.get("Symbol"),
        "note": "Paper/worker task only. This is not a live broker order.",
    }


def list_worker_tasks(user_id: int, *, limit: int = 20) -> dict[str, Any]:
    from tasks import store

    rows = store.list_tasks(int(user_id), limit=limit)
    slim = [
        {
            "task_id": r.get("TaskId"),
            "public_id": r.get("PublicId"),
            "status": r.get("Status"),
            "symbol": r.get("Symbol"),
            "request": r.get("RequestText"),
            "created_at": r.get("CreatedAt"),
        }
        for r in rows
    ]
    return {"ok": True, "tasks": slim}


def system_status() -> dict[str, Any]:
    from services.api_monitor import derive_status, usage_summary

    rows = []
    for row in usage_summary():
        rows.append(
            {
                "code": row.get("ApiCode"),
                "name": row.get("ApiName"),
                "purpose": row.get("Purpose"),
                "category": row.get("Category"),
                "api_type": row.get("ApiType") or "external",
                "endpoint": row.get("Endpoint"),
                "free": bool(row.get("IsFree")),
                "free_limit": row.get("FreeUsageLimit"),
                "enabled": bool(row.get("IsEnabled")),
                "status": derive_status(row),
                "today_usage": int(row.get("TodayUsage") or 0),
                "today_success": int(row.get("TodaySuccess") or 0),
                "today_failure": int(row.get("TodayFailure") or 0),
                "remaining": "Not provided by API",
                "last_success": row.get("LastSuccessUtc"),
                "last_error": row.get("LastError"),
                "fallback": row.get("FallbackApiCode"),
                "requires_key": bool(row.get("RequiresApiKey")),
                "pricing_note": row.get("PricingNote"),
            }
        )
    _log_internal("system_status", success=True)
    return {"ok": True, "apis": rows}
