from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf


class YfinanceMarketData:
    __slots__ = ("_opts",)

    def __init__(self, opts: dict[str, Any] | None = None) -> None:
        self._opts = opts or {}

    def download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
        )
        if df.empty:
            return pd.DataFrame()
        df = df.dropna()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
