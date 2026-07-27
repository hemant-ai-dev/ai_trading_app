"""Yahoo Finance market data provider."""

from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from utils.logging import get_logger

logger = get_logger(__name__)


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    out = out.dropna(how="all")
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        return pd.DataFrame()
    out = out[required].copy()
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    return out.sort_index()


class YfinanceMarketData:
    """Fetch OHLCV and live quotes via yfinance."""

    __slots__ = ("_opts",)

    def __init__(self, opts: dict[str, Any] | None = None) -> None:
        self._opts = opts or {}

    def download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        sym = symbol.strip()
        auto_adjust = bool(self._opts.get("auto_adjust", True))
        prepost = bool(self._opts.get("prepost", False))

        ticker = yf.Ticker(sym)
        df = ticker.history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            prepost=prepost,
            actions=False,
        )
        df = _normalize_ohlcv(df)

        if df.empty:
            raw = yf.download(
                sym,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=auto_adjust,
                prepost=prepost,
                threads=False,
            )
            df = _normalize_ohlcv(raw)

        if df.empty:
            return df

        try:
            info = ticker.fast_info
            last_px = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
            if last_px and float(last_px) > 0:
                last_px = float(last_px)
                last_hist = float(df["Close"].iloc[-1])
                if abs(last_px - last_hist) / max(last_hist, 1e-6) > 0.0001:
                    ts = pd.Timestamp.utcnow().tz_localize(None)
                    if ts <= df.index[-1]:
                        ts = df.index[-1] + pd.Timedelta(seconds=1)
                    row = {
                        "Open": last_px,
                        "High": max(last_px, float(df["High"].iloc[-1])),
                        "Low": min(last_px, float(df["Low"].iloc[-1])),
                        "Close": last_px,
                        "Volume": float(df["Volume"].iloc[-1]),
                    }
                    df.loc[ts] = row
                    df = df.sort_index()
        except Exception as exc:
            logger.debug("Could not append live quote for %s: %s", sym, exc)

        return df

    def get_latest_price(self, symbol: str) -> float | None:
        try:
            info = yf.Ticker(symbol.strip()).fast_info
            px = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
            return float(px) if px else None
        except Exception:
            return None
