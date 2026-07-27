"""Gen AI prediction model — optional LLM enhancement."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from intraday_forecast import linear_projection, nse_regular_5m_index
from market_calendar import MarketStatus, SessionPhase
from prediction.models import PredictionResult
from utils.time_utils import IST


def _path_to_series(path_raw: list, anchor: float, ms: MarketStatus) -> pd.Series:
    today = ms.now_ist.date()
    if ms.phase in (SessionPhase.HOLIDAY_OR_WEEKEND, SessionPhase.POST_CLOSE) and not ms.is_trading_day:
        idx_day = ms.next_session_date
    elif ms.phase == SessionPhase.POST_CLOSE:
        idx_day = ms.next_session_date
    else:
        idx_day = today

    idx = nse_regular_5m_index(idx_day)
    if not path_raw:
        return linear_projection(idx, anchor, anchor * 1.002)

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

    pts = pd.DataFrame(points, columns=["t", "price"]).drop_duplicates("t").sort_values("t")
    pts["t"] = pd.to_datetime(pts["t"])
    if pts["t"].dt.tz is None:
        pts["t"] = pts["t"].dt.tz_localize(IST)
    else:
        pts["t"] = pts["t"].dt.tz_convert(IST)

    s = pd.Series(pts["price"].values, index=pts["t"])
    s = s.reindex(idx, method="nearest")
    s.iloc[0] = anchor
    return s.interpolate(method="linear").ffill().bfill()


def predict_genai(
    *,
    stock: str,
    df: pd.DataFrame,
    rule_result: PredictionResult,
    indicator_summary: str,
    indicator_ctx: dict,
    market_context: str,
    headline_block: str,
    ms: MarketStatus,
    llm: Any,
    settings: dict | None,
) -> PredictionResult | None:
    """LLM makes its own prediction using technical context and news."""
    if llm is None:
        return None

    sec = (settings or {}).get("llm", {}).get("openai") or {}
    max_tokens = int(sec.get("max_tokens_genai_predict") or sec.get("max_tokens_json") or 2800)
    temperature = float(sec.get("temperature_genai_predict") or 0.45)
    last_close = float(df["Close"].iloc[-1])

    schema = """
Return ONLY valid JSON. You are the PRIMARY prediction brain.

Required keys:
1) "signal": "BUY" | "SELL" | "HOLD"
2) "confidence_pct": number 35–92
3) "target_price": number
4) "stop_loss": number
5) "predicted_price": number — next expected price
6) "price_low": number — lower bound of expected range
7) "price_high": number — upper bound of expected range
8) "trend": "bullish" | "bearish" | "neutral"
9) "market_read": one paragraph in simple English for beginners
10) "reasoning_steps": array of simple English strings explaining WHY
11) "prediction_path": array of {"offset_minutes": int, "price": number} (8–20 points)
12) "risks": string
""".strip()

    rule_ref = {
        "signal": rule_result.signal,
        "confidence": rule_result.confidence,
        "target": rule_result.target_price,
        "reasons": rule_result.reasons[:6],
    }

    user = (
        f"SYMBOL: {stock}\nLAST_CLOSE: {last_close}\n"
        f"SESSION: {market_context}\nINDICATORS: {indicator_summary}\n"
        f"RULE_REFERENCE: {json.dumps(rule_ref)}\n"
        f"HEADLINES:\n{headline_block}\n"
    )

    data = llm.chat_json(
        system=(
            "You are an educational Indian markets analyst. "
            "Explain predictions in simple language for beginners. Output JSON only."
        ),
        user=schema + "\n\n" + user,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not data:
        return None

    sig = str(data.get("signal") or "HOLD").upper()
    if sig not in ("BUY", "SELL", "HOLD"):
        sig = "HOLD"

    try:
        conf = float(data.get("confidence_pct") or 50)
        target = float(data.get("target_price") or last_close)
        stop = float(data.get("stop_loss") or last_close)
        predicted = float(data.get("predicted_price") or last_close)
        price_low = float(data.get("price_low") or last_close * 0.99)
        price_high = float(data.get("price_high") or last_close * 1.01)
    except (TypeError, ValueError):
        return None

    conf = max(35.0, min(92.0, conf))
    series = _path_to_series(data.get("prediction_path") or [], last_close, ms)
    reasons = list(data.get("reasoning_steps") or [])

    return PredictionResult(
        signal=sig,
        confidence=round(conf, 1),
        predicted_price=round(predicted, 2),
        target_price=round(target, 2),
        stop_loss=round(stop, 2),
        price_low=round(price_low, 2),
        price_high=round(price_high, 2),
        trend=str(data.get("trend") or "neutral"),
        risk_level=rule_result.risk_level,
        score=rule_result.score,
        market_regime=rule_result.market_regime,
        reasons=reasons,
        reasons_simple=reasons,
        projection_series=series,
        indicator_snapshot=indicator_ctx,
        source="GENAI",
        raw=data,
    )
