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
        _log_internal("quote", success=True)
        return {
            "ok": True,
            "symbol": symbol,
            "open": jsonable(float(last["Open"])),
            "high": jsonable(float(last["High"])),
            "low": jsonable(float(last["Low"])),
            "price": jsonable(float(last["Close"])),
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
        _log_internal("analysis", success=True)
        return {
            "ok": True,
            "symbol": symbol,
            "latest_price": jsonable(result.get("latest_price")),
            "prediction": jsonable(payload),
            "explanation": jsonable(result.get("explanation") or {}),
            "regime": jsonable(getattr(result.get("regime"), "__dict__", result.get("regime"))),
            "fallback_note": result.get("fallback_note") or None,
            "disclaimer": "Educational analysis only — not financial advice and not a profit guarantee.",
            **_provider_meta(result.get("df_ist")),
        }
    except Exception as exc:
        logger.exception("analysis failed")
        _log_internal("analysis", success=False, error=str(exc)[:400])
        return {"ok": False, "error": "Analysis failed.", "code": "error", "symbol": symbol}


def get_prediction_history(symbol: str, user_id: int, *, limit: int = 40) -> dict[str, Any]:
    from prediction import archive

    rows = archive.list_predictions(int(user_id), symbol.upper() if symbol else None, limit=limit)
    slim = []
    for r in rows:
        slim.append(
            {
                "created_at": r.get("CreatedAt"),
                "symbol": r.get("Symbol"),
                "market_price": r.get("MarketPrice"),
                "predicted_price": r.get("PredictedPrice"),
                "price_low": r.get("PriceLow"),
                "price_high": r.get("PriceHigh"),
                "signal": r.get("Signal"),
                "confidence": r.get("Confidence"),
                "regime": r.get("MarketRegime"),
                "actual_price": r.get("ActualPrice"),
            }
        )
    _log_internal("prediction_history", success=True)
    return {"ok": True, "symbol": (symbol or "").upper() or None, "rows": slim}


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
