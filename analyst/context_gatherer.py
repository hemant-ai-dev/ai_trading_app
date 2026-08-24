"""Step 1 — Gather every available market input (modular providers)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from services.market_service import MarketService
from utils.logging import get_logger

logger = get_logger(__name__)

# Correlated / macro proxies available via Yahoo (NSE / global)
MACRO_SYMBOLS = {
    "nifty50": "^NSEI",
    "banknifty": "^NSEBANK",
    "india_vix": "^INDIAVIX",
    "us_vix": "^VIX",
    "usd_inr": "INR=X",
    "crude": "CL=F",
    "gold": "GC=F",
    "us_10y": "^TNX",
}


def _safe_last_close(df: pd.DataFrame) -> float | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    try:
        return float(df["Close"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None


def _pct_change(df: pd.DataFrame, bars: int = 5) -> float | None:
    if df is None or len(df) <= bars:
        return None
    try:
        a = float(df["Close"].iloc[-1])
        b = float(df["Close"].iloc[-1 - bars])
        if b == 0:
            return None
        return (a - b) / b * 100
    except (TypeError, ValueError, IndexError):
        return None


def gather_market_context(
    *,
    symbol: str,
    df: pd.DataFrame,
    market: MarketService,
    indicator_ctx: dict[str, Any],
) -> dict[str, Any]:
    """
    Collect live price, OHLCV stats, correlated assets, and availability flags
    for richer data sources (order book, OI, options — pluggable later).
    """
    last = df.iloc[-1] if not df.empty else None
    live = float(last["Close"]) if last is not None else None

    macros: dict[str, Any] = {}
    for name, ticker in MACRO_SYMBOLS.items():
        try:
            # Skip fetching the same symbol twice
            if ticker.upper() == symbol.upper():
                macros[name] = {
                    "symbol": ticker,
                    "last": live,
                    "chg_5bar_pct": _pct_change(df, 5),
                    "available": True,
                }
                continue
            mdf = market.get_ohlcv(ticker, period="5d", interval="1h")
            macros[name] = {
                "symbol": ticker,
                "last": _safe_last_close(mdf),
                "chg_5bar_pct": _pct_change(mdf, 5),
                "available": not mdf.empty,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("Macro fetch failed for %s: %s", ticker, exc)
            macros[name] = {"symbol": ticker, "last": None, "available": False}

    # Sector / index relative strength vs Nifty when possible
    nifty_chg = (macros.get("nifty50") or {}).get("chg_5bar_pct")
    stock_chg = _pct_change(df, 12)
    relative_strength = None
    if nifty_chg is not None and stock_chg is not None:
        relative_strength = round(stock_chg - nifty_chg, 3)

    unavailable = {
        "order_book": "Provider not configured — add a broker/market-depth adapter.",
        "open_interest": "Provider not configured — add F&O OI feed.",
        "options_chain": "Provider not configured — add options chain adapter.",
        "futures_data": "Partial via yfinance continuous futures when ticker supports it.",
        "institutional_flow": "Provider not configured — add FII/DII feed.",
        "insider_transactions": "Provider not configured.",
        "block_bulk_deals": "Provider not configured.",
        "economic_calendar": "Use news/macro proxies until calendar provider is plugged in.",
    }

    volume = float(last["Volume"]) if last is not None and "Volume" in df.columns else None
    return {
        "symbol": symbol.upper(),
        "live_price": live,
        "ohlcv_bars": int(len(df)),
        "open": float(last["Open"]) if last is not None else None,
        "high": float(last["High"]) if last is not None else None,
        "low": float(last["Low"]) if last is not None else None,
        "close": live,
        "volume": volume,
        "volume_ratio": indicator_ctx.get("vol_ratio"),
        "atr": indicator_ctx.get("atr"),
        "adx": indicator_ctx.get("adx"),
        "rsi": indicator_ctx.get("rsi"),
        "vwap": indicator_ctx.get("vwap"),
        "trend_dir": indicator_ctx.get("trend_dir"),
        "macros": macros,
        "relative_strength_vs_nifty_pct": relative_strength,
        "india_vix": (macros.get("india_vix") or {}).get("last"),
        "usd_inr": (macros.get("usd_inr") or {}).get("last"),
        "unavailable_sources": unavailable,
        "data_quality": "live_ohlcv+macro_proxies",
    }
