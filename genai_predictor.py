"""Gen AI brain — independent predictions with full reasoning stored for SQL audit."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

from intraday_forecast import ensure_ist_index, linear_projection, nse_regular_5m_index
from market_calendar import MarketStatus, SessionPhase

IST = ZoneInfo("Asia/Kolkata")


def build_indicators_summary(df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    return (
        f"Close={float(last['Close']):.2f}, RSI={float(last['RSI']):.1f}, "
        f"EMA9={float(last['EMA9']):.2f}, EMA20={float(last['EMA20']):.2f}, "
        f"MACD={float(last['MACD']):.4f}, VWAP={float(last['VWAP']):.2f}"
    )


def build_logic_snapshot(df: pd.DataFrame, rule_result: dict) -> dict:
    """Serializable snapshot of inputs the brain + rules saw."""
    last = df.iloc[-1]
    return {
        "timestamp_ist": datetime.now(IST).isoformat(),
        "ohlcv_last": {
            "close": float(last["Close"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "open": float(last["Open"]),
            "volume": float(last["Volume"]),
        },
        "indicators": {
            "rsi": float(last["RSI"]),
            "ema9": float(last["EMA9"]),
            "ema20": float(last["EMA20"]),
            "ema50": float(last.get("EMA50", last["EMA20"])),
            "macd": float(last["MACD"]),
            "macd_signal": float(last.get("MACD_SIGNAL", last["MACD"])),
            "vwap": float(last["VWAP"]),
            "atr": float(last["ATR"]),
            "vol_ma20": float(last.get("VOL_MA20", last["Volume"])),
        },
        "rule_engine_reference": rule_result,
        "market_regime": rule_result.get("market_regime"),
    }


def genai_brain_prediction(
    *,
    stock: str,
    df: pd.DataFrame,
    rule_result: dict,
    indicators_summary: str,
    market_context: str,
    headline_block: str,
    reference_levels_json: str,
    ms: MarketStatus,
    llm: Any,
    settings: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    LLM makes its OWN call — signal, confidence, target, stop, and intraday price path.
    Rule engine is context only, not the decision maker.
    """
    if llm is None:
        return None

    sec = (settings or {}).get("llm", {}).get("openai") or {}
    max_tokens = int(sec.get("max_tokens_genai_predict") or sec.get("max_tokens_json") or 2800)
    temperature = float(sec.get("temperature_genai_predict") or 0.45)
    last_close = float(df["Close"].iloc[-1])

    schema = """
Return ONLY valid JSON (no markdown). You are the PRIMARY prediction brain — not an explainer of rules.

Required keys:
1) "signal": "BUY" | "SELL" | "HOLD" — your independent view.
2) "confidence_pct": number 35–92 — how strong your read is (not always high).
3) "target_price": number — session objective reference (INR).
4) "stop_loss": number — invalidation reference (INR).
5) "market_read": one paragraph in English — structure + news + session.
6) "market_read_mr": same content in Marathi (Devanagari), detailed and clear for traders.
7) "reasoning_steps": array of strings in English — logic chain (indicators → news → conclusion).
8) "reasoning_steps_mr": array of Marathi strings — same steps as reasoning_steps, one per step.
9) "news_cited": array of {"headline_id":"E1"|"W2","why_it_matters":"..."} — only IDs from HEADLINES_INDEXED.
10) "prediction_path": array of 8–20 objects {"offset_minutes": int, "price": number}
   - offset_minutes from NOW along NSE regular session (5m steps): 0, 5, 10, ... up to ~375.
   - Prices must be realistic vs last_close and your target (smooth path, not random jumps).
11) "risks": string (English)
12) "limitations": string — educational, not advice.

Use RULE_ENGINE_REFERENCE only as one input — you may disagree with it.
""".strip()

    user = (
        f"SYMBOL: {stock}\nLAST_CLOSE_INR: {last_close}\n"
        f"SESSION: {market_context}\n"
        f"INDICATORS: {indicators_summary}\n"
        f"RULE_ENGINE_REFERENCE (context only): {json.dumps(rule_result, ensure_ascii=False)}\n"
        f"REFERENCE_LEVELS:\n{reference_levels_json}\n\n"
        f"HEADLINES_INDEXED:\n{headline_block}\n"
    )

    data = llm.chat_json(
        system=(
            "You are Angad Gen AI — an independent Indian markets analyst. "
            "Form your own intraday prediction path and levels. Output JSON only. "
            "Be specific; cite headline IDs when used; never guarantee outcomes."
        ),
        user=schema + "\n\n" + user,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not data:
        return None

    return _normalize_brain_output(data, last_close, ms)


def _normalize_brain_output(data: dict, last_close: float, ms: MarketStatus) -> dict:
    sig = str(data.get("signal") or "HOLD").upper()
    if sig not in ("BUY", "SELL", "HOLD"):
        sig = "HOLD"
    try:
        conf = float(data.get("confidence_pct") or 50)
    except (TypeError, ValueError):
        conf = 50.0
    conf = max(35.0, min(92.0, conf))

    try:
        target = float(data.get("target_price") or last_close)
        stop = float(data.get("stop_loss") or last_close)
    except (TypeError, ValueError):
        target = last_close
        stop = last_close

    path_raw = data.get("prediction_path") or []
    series = _path_to_series(path_raw, last_close, ms)

    return {
        "signal": sig,
        "confidence": round(conf, 1),
        "target": round(target, 2),
        "stop_loss": round(stop, 2),
        "market_read": str(data.get("market_read") or ""),
        "market_read_mr": str(data.get("market_read_mr") or ""),
        "reasoning_steps": list(data.get("reasoning_steps") or []),
        "reasoning_steps_mr": list(data.get("reasoning_steps_mr") or []),
        "news_cited": list(data.get("news_cited") or []),
        "risks": str(data.get("risks") or ""),
        "limitations": str(data.get("limitations") or ""),
        "projection_series": series,
        "raw_json": data,
    }


def _path_to_series(path_raw: list, anchor: float, ms: MarketStatus) -> pd.Series:
    """Turn LLM offset_minutes path into IST-indexed series for chart + SQL."""
    today = ms.now_ist.date()
    if ms.phase in (SessionPhase.HOLIDAY_OR_WEEKEND, SessionPhase.POST_CLOSE) and not ms.is_trading_day:
        idx_day = ms.next_session_date
    elif ms.phase == SessionPhase.POST_CLOSE:
        idx_day = ms.next_session_date
    else:
        idx_day = today

    idx = nse_regular_5m_index(idx_day)
    if not path_raw:
        end = anchor * 1.002
        return linear_projection(idx, anchor, end)

    points: list[tuple[datetime, float]] = []
    base = ms.now_ist
    for row in path_raw:
        if not isinstance(row, dict):
            continue
        try:
            off = int(row.get("offset_minutes", 0))
            px = float(row.get("price", anchor))
        except (TypeError, ValueError):
            continue
        t = base + pd.Timedelta(minutes=off)
        points.append((t.to_pydatetime() if hasattr(t, "to_pydatetime") else t, px))

    if not points:
        return linear_projection(idx, anchor, anchor)

    # Resample onto session grid via interpolation
    pts = pd.DataFrame(points, columns=["t", "price"]).drop_duplicates("t").sort_values("t")
    pts["t"] = pd.to_datetime(pts["t"])
    if pts["t"].dt.tz is None:
        pts["t"] = pts["t"].dt.tz_localize(IST)
    else:
        pts["t"] = pts["t"].dt.tz_convert(IST)

    s = pd.Series(pts["price"].values, index=pts["t"])
    s = s.reindex(idx, method="nearest")
    s.iloc[0] = anchor
    s = s.interpolate(method="linear").ffill().bfill()
    return s
