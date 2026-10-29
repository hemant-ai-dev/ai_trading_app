"""Login-page copy: how the portal is wired, by model."""

from __future__ import annotations

PORTAL_FLOW = (
    "Daily bars",
    "Indicators",
    "Analyst",
    "BUY / SELL / HOLD",
    "Chat & paper",
)

PORTAL_MODELS: list[dict[str, str]] = [
    {"code": "01", "name": "Auth", "blurb": "Hashed login, 15-minute session, lockout after failed tries."},
    {"code": "02", "name": "Market data", "blurb": "Free Yahoo daily bars, Stooq as fallback."},
    {"code": "03", "name": "Indicators", "blurb": "RSI, EMA, MACD, ATR, Fib, support and resistance."},
    {"code": "04", "name": "Analyst", "blurb": "Regime, news tilt, scenarios, and a risk plan."},
    {"code": "05", "name": "Prediction", "blurb": "BUY, SELL, or HOLD with a target and stop."},
    {"code": "06", "name": "Strategy desk", "blurb": "Candles, conviction, volume, and history."},
    {"code": "07", "name": "AI Chat", "blurb": "Natural language over real desk data."},
    {"code": "08", "name": "Workers", "blurb": "Paper tasks with approval. No live orders."},
]
