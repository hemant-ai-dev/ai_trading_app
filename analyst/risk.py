"""Risk Management Agent — stops, targets, R:R, and position sizing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RiskPlan:
    """Actionable risk plan for the current prediction."""

    risk_level: str  # Low | Medium | High
    stop_loss: float
    target_price: float
    predicted_price: float
    price_low: float
    price_high: float
    risk_reward_ratio: float
    position_size_pct: float  # suggested % of capital
    risk_per_trade_pct: float
    atr: float
    atr_pct: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _risk_level(atr_pct: float, confidence: float, regime: str) -> str:
    if atr_pct > 2.5 or confidence < 55 or regime == "volatile":
        return "High"
    if atr_pct > 1.2 or confidence < 70 or regime == "breakout":
        return "Medium"
    return "Low"


def build_risk_plan(
    *,
    close: float,
    atr: float,
    signal: str,
    confidence: float,
    regime: str = "sideways",
    capital: float | None = None,
    max_risk_pct: float = 1.0,
) -> RiskPlan:
    """
    Compute stop, targets, R:R. Share count is only filled when the user
    has configured capital — no default account size is assumed.
    """
    close = float(close)
    atr = float(max(atr, close * 0.002, 0.01))
    atr_pct = atr / close * 100 if close else 0.0
    level = _risk_level(atr_pct, confidence, regime)

    # ATR multiples by regime / conviction
    if regime.startswith("trending") and confidence >= 70:
        target_mult, stop_mult = 3.0, 1.2
    elif regime == "breakout":
        target_mult, stop_mult = 2.5, 1.3
    elif regime == "volatile":
        target_mult, stop_mult = 2.0, 1.6
    elif regime == "sideways":
        target_mult, stop_mult = 1.5, 1.0
    else:
        target_mult, stop_mult = 2.2, 1.2

    if signal == "BUY":
        target = round(close + atr * target_mult, 2)
        stop = round(close - atr * stop_mult, 2)
        predicted = round(close + atr * (target_mult * 0.45), 2)
        price_low = round(close - atr * stop_mult * 0.7, 2)
        price_high = round(close + atr * (target_mult + 0.3), 2)
        risk_abs = max(close - stop, atr * 0.5)
        reward_abs = max(target - close, atr * 0.5)
    elif signal == "SELL":
        target = round(close - atr * target_mult, 2)
        stop = round(close + atr * stop_mult, 2)
        predicted = round(close - atr * (target_mult * 0.45), 2)
        price_low = round(close - atr * (target_mult + 0.3), 2)
        price_high = round(close + atr * stop_mult * 0.7, 2)
        risk_abs = max(stop - close, atr * 0.5)
        reward_abs = max(close - target, atr * 0.5)
    else:
        target = round(close + atr * 0.6, 2)
        stop = round(close - atr * 0.6, 2)
        predicted = round(close, 2)
        price_low = round(close - atr * 1.2, 2)
        price_high = round(close + atr * 1.2, 2)
        risk_abs = max(close - stop, atr * 0.4)
        reward_abs = max(target - close, atr * 0.4)

    rr = round(reward_abs / risk_abs, 2) if risk_abs else 0.0

    # Scale risk budget by risk level
    risk_scale = {"Low": 1.0, "Medium": 0.7, "High": 0.4}.get(level, 0.6)
    if signal == "HOLD":
        risk_scale *= 0.5
    risk_pct = round(max_risk_pct * risk_scale, 2)
    position_pct = 0.0
    notes = [f"Risk/Reward ≈ 1:{rr:.2f}."]
    if not capital or capital <= 0:
        notes.append(
            f"Suggested risk per trade ≈ {risk_pct:.2f}% of capital once you set an amount in Risk limits. "
            "No default capital is assumed."
        )
    else:
        from analyst.sizing import theoretical_size

        sized = theoretical_size(
            entry=close,
            stop=stop,
            capital=float(capital),
            max_risk_pct=risk_pct,
        )
        position_pct = float(sized.get("position_pct") or 0)
        notes.append(
            f"Theoretical size {sized.get('qty') or 0} shares · risk ₹{sized.get('risk_rupees')} "
            f"of ₹{sized.get('budget_rupees')} budget (not an order)."
        )
        if sized.get("warning"):
            notes.append(str(sized["warning"]))
    if level == "High":
        notes.append("High risk regime — prefer smaller size or wait for clearer setup.")
    if rr < 1.2 and signal != "HOLD":
        notes.append("R:R is modest — only take the trade if confirmation is strong.")

    return RiskPlan(
        risk_level=level,
        stop_loss=stop,
        target_price=target,
        predicted_price=predicted,
        price_low=price_low,
        price_high=price_high,
        risk_reward_ratio=rr,
        position_size_pct=position_pct,
        risk_per_trade_pct=risk_pct,
        atr=round(atr, 4),
        atr_pct=round(atr_pct, 3),
        notes=notes,
    )
