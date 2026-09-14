"""Smart Box — glanceable BUY / SELL / HOLD from indicator-backed analysis."""

from __future__ import annotations

from typing import Any

from prediction.models import PredictionResult


def build_smart_box(primary: PredictionResult, latest: float) -> dict[str, Any]:
    """
    Compact action card derived from the analyst risk plan and structure levels.

    HOLD still exposes buy/sell consideration prices so the user is not stuck
    reading the full desk. This is educational logic, not a profit guarantee.
    """
    snap = primary.indicator_snapshot or {}
    fib = snap.get("fibonacci")
    sr = snap.get("support_resistance") or {}
    supports = list(sr.get("support") or [])
    resistances = list(sr.get("resistance") or [])

    def _fib_val(name: str) -> float | None:
        if fib is None:
            return None
        if isinstance(fib, dict):
            val = fib.get(name)
        else:
            val = getattr(fib, name, None)
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    nearest_support = None
    if supports:
        nearest_support = float(supports[0])
    elif _fib_val("nearest_support"):
        nearest_support = _fib_val("nearest_support")

    nearest_resistance = None
    if resistances:
        nearest_resistance = float(resistances[0])
    elif _fib_val("nearest_resistance"):
        nearest_resistance = _fib_val("nearest_resistance")

    signal = (primary.signal or "HOLD").upper()
    entry = round(float(latest), 2)
    target = round(float(primary.target_price or 0), 2)
    stop = round(float(primary.stop_loss or 0), 2)

    consider_buy = round(float(nearest_support or primary.price_low or entry), 2)
    consider_sell = round(float(nearest_resistance or primary.price_high or entry), 2)

    if signal == "BUY":
        headline = "BUY"
        summary = (
            f"Indicators and strategy filters lean bullish. "
            f"Suggested entry near ₹{entry:,.2f}, target ₹{target:,.2f}, stop ₹{stop:,.2f}."
        )
    elif signal == "SELL":
        headline = "SELL"
        summary = (
            f"Indicators and strategy filters lean bearish. "
            f"Suggested entry near ₹{entry:,.2f}, target ₹{target:,.2f}, stop ₹{stop:,.2f}."
        )
    else:
        headline = "HOLD"
        summary = (
            f"No high-conviction setup right now. Consider buying near ₹{consider_buy:,.2f} "
            f"and selling / reducing near ₹{consider_sell:,.2f} if those levels trade with confirmation."
        )

    return {
        "signal": signal,
        "headline": headline,
        "summary": summary,
        "entry": entry,
        "target": target,
        "stop": stop,
        "confidence": float(primary.confidence or 0),
        "risk_level": primary.risk_level or "Medium",
        "regime": primary.market_regime or "—",
        "consider_buy": consider_buy,
        "consider_sell": consider_sell,
        "trend": (primary.trend or "neutral").title(),
    }


def smart_box_html(box: dict[str, Any], theme_dark: bool = True) -> str:
    signal = box["signal"]
    color = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#f0b90b"}.get(signal, "#94a3b8")
    bg = "rgba(18, 22, 28, 0.92)" if theme_dark else "rgba(255,255,255,0.96)"
    text = "#e8eaed" if theme_dark else "#0f172a"
    muted = "#94a3b8"

    if signal == "HOLD":
        levels = f"""
          <div class="smart-grid">
            <div><span>Consider buy</span><b>₹{box['consider_buy']:,.2f}</b></div>
            <div><span>Consider sell</span><b>₹{box['consider_sell']:,.2f}</b></div>
            <div><span>Confidence</span><b>{box['confidence']:.0f}%</b></div>
            <div><span>Risk</span><b>{box['risk_level']}</b></div>
          </div>
        """
    else:
        levels = f"""
          <div class="smart-grid">
            <div><span>Entry</span><b>₹{box['entry']:,.2f}</b></div>
            <div><span>Target</span><b>₹{box['target']:,.2f}</b></div>
            <div><span>Stop-loss</span><b>₹{box['stop']:,.2f}</b></div>
            <div><span>Confidence</span><b>{box['confidence']:.0f}%</b></div>
            <div><span>Risk</span><b>{box['risk_level']}</b></div>
          </div>
        """

    return f"""
    <div class="smart-box" style="border-color:{color};background:{bg};color:{text}">
      <div class="smart-kicker">Smart Box · algorithmic read</div>
      <div class="smart-signal" style="color:{color}">{box['headline']}</div>
      <div class="smart-summary">{box['summary']}</div>
      {levels}
      <div class="smart-meta" style="color:{muted}">
        Regime {box['regime']} · Trend {box['trend']} · Not a profit guarantee
      </div>
    </div>
    """
