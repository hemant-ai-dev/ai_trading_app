"""Stooq public daily CSV — free fallback for OHLCV (no API key)."""

from __future__ import annotations

from io import StringIO
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

from services.api_monitor import track_call
from utils.logging import get_logger

logger = get_logger(__name__)

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def _stooq_symbol(symbol: str) -> str | None:
    s = symbol.strip().lower()
    if s.startswith("^"):
        # Common index aliases; many NSE indices are unavailable on Stooq.
        aliases = {"^nsei": "^nsei", "^bsesn": "^bsesn", "^nsebank": None}
        return aliases.get(s, s)
    if s.endswith(".ns"):
        return s[:-3] + ".in"
    if s.endswith(".bo"):
        return s[:-3] + ".in"
    return s


def fetch_stooq_daily(symbol: str, period: str = "1y") -> pd.DataFrame:
    mapped = _stooq_symbol(symbol)
    if not mapped:
        return pd.DataFrame()
    url = STOOQ_URL.format(symbol=quote(mapped))
    with track_call("stooq", "daily_csv", url) as meta:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AngadTrading/1.0)"})
        with urlopen(req, timeout=12) as resp:
            meta["http_status"] = getattr(resp, "status", 200)
            raw = resp.read().decode("utf-8", errors="replace")
        if not raw or raw.lower().startswith("no data") or "<html" in raw.lower():
            meta["success"] = False
            meta["error"] = "Stooq returned no CSV data for this symbol."
            return pd.DataFrame()
        df = pd.read_csv(StringIO(raw))
        cols = {c.lower(): c for c in df.columns}
        if "date" not in cols or "close" not in cols:
            meta["success"] = False
            meta["error"] = "Unexpected Stooq CSV columns."
            return pd.DataFrame()
        df = df.rename(
            columns={
                cols.get("date"): "Date",
                cols.get("open", "Open"): "Open",
                cols.get("high", "High"): "High",
                cols.get("low", "Low"): "Low",
                cols.get("close"): "Close",
                cols.get("volume", "Volume"): "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col not in df.columns:
                df[col] = 0 if col == "Volume" else df["Close"]
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        days = {"1d": 5, "5d": 10, "1mo": 31, "3mo": 95, "6mo": 186, "1y": 370, "2y": 740}.get(period, 370)
        out = df.tail(days)
        if out.empty:
            meta["success"] = False
            meta["error"] = "Stooq CSV parsed but was empty."
        else:
            meta["success"] = True
        return out[["Open", "High", "Low", "Close", "Volume"]]


class StooqMarketData:
    def __init__(self, opts: dict[str, Any] | None = None) -> None:
        self._opts = opts or {}

    def download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        if interval not in ("1d", "1wk"):
            logger.info("Stooq fallback skipped for intraday interval %s", interval)
            return pd.DataFrame()
        return fetch_stooq_daily(symbol, period)

    def get_latest_price(self, symbol: str) -> float | None:
        df = fetch_stooq_daily(symbol, "1mo")
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
