"""Scan the supported universe with existing market + indicator + rule engines."""

from __future__ import annotations

from typing import Any

from analyst.risk import build_risk_plan
from analyst.trade_plan import MIN_RR, build_trade_plan
from indicators.calculator import apply_all_indicators, build_indicator_context
from prediction.rule_engine import predict_rule_based

UNIVERSE: list[tuple[str, str]] = [
    ("Nifty 50", "^NSEI"),
    ("Bank Nifty", "^NSEBANK"),
    ("Reliance", "RELIANCE.NS"),
    ("TCS", "TCS.NS"),
    ("Infosys", "INFY.NS"),
    ("HDFC Bank", "HDFCBANK.NS"),
    ("ICICI Bank", "ICICIBANK.NS"),
    ("Tata Motors", "TATAMOTORS.NS"),
]


def _sr(ctx: dict) -> tuple[float | None, float | None]:
    block = ctx.get("support_resistance") or {}
    sup = block.get("support") if isinstance(block, dict) else None
    res = block.get("resistance") if isinstance(block, dict) else None
    s0 = float(sup[0]) if isinstance(sup, (list, tuple)) and sup else None
    r0 = float(res[0]) if isinstance(res, (list, tuple)) and res else None
    return s0, r0


def scan_universe(market, *, period: str = "3mo", interval: str = "1d") -> list[dict[str, Any]]:
    """Rank potential setups. Not 'highest probability wins' — R:R, liquidity proxy, confirmation."""
    rows: list[dict[str, Any]] = []
    for name, symbol in UNIVERSE:
        try:
            df = market.get_ohlcv(symbol, period, interval)
            if df is None or df.empty or len(df) < 25:
                continue
            ind = apply_all_indicators(df)
            ctx = build_indicator_context(ind)
            pred = predict_rule_based(ind, ctx)
            spot = float(ind["Close"].iloc[-1])
            atr = float(ctx.get("atr") or spot * 0.01)
            plan_risk = build_risk_plan(
                close=spot,
                atr=atr,
                signal=pred.signal,
                confidence=float(pred.confidence or 0),
                regime=str(pred.market_regime or ""),
            )
            s0, r0 = _sr(ctx)
            vol_ok = float(ctx.get("vol_ratio") or 1) >= 0.85
            setup = build_trade_plan(
                symbol=symbol,
                name=name,
                spot=spot,
                signal=pred.signal,
                trend=str(pred.trend or ctx.get("trend_dir") or ""),
                confidence=float(pred.confidence or 0),
                predicted_price=float(pred.predicted_price),
                atr=atr,
                support=s0,
                resistance=r0,
                regime=str(pred.market_regime or ""),
                strategy_id="screen-rules",
                strategy_name="Trend + Momentum + Volume (rule screen)",
                risk_plan=plan_risk.to_dict(),
                reasons=list(pred.reasons_simple or pred.reasons or [])[:4],
                horizon=f"{period}/{interval}",
            )
            quality = 0.0
            if setup["status"] in ("ENTRY", "HOLD", "WAIT") and pred.signal in ("BUY", "SELL"):
                quality += 2
            if setup["rr"] >= MIN_RR:
                quality += min(setup["rr"], 3)
            if vol_ok:
                quality += 1
            if pred.signal != "HOLD":
                quality += 0.5
            else:
                quality -= 1
            # Do not boost solely by confidence
            quality += min(float(pred.confidence or 0) / 100.0, 0.4)
            setup["screen_score"] = round(quality, 3)
            setup["volume_ok"] = vol_ok
            setup["signal"] = pred.signal
            rows.append(setup)
        except Exception:
            continue
    rows.sort(key=lambda r: r.get("screen_score") or 0, reverse=True)
    return rows
