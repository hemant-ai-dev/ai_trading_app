"""Technical indicators — RSI, MACD, EMA, SMA, VWAP, Bollinger, ATR, ADX, volume."""

from __future__ import annotations

import pandas as pd
import ta


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"].squeeze()
    df["EMA9"] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df["EMA20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    df["EMA50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df["SMA9"] = ta.trend.SMAIndicator(close, window=9).sma_indicator()
    df["SMA20"] = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    df["SMA50"] = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    if len(close) >= 100:
        df["SMA100"] = ta.trend.SMAIndicator(close, window=100).sma_indicator()
    if len(close) >= 200:
        df["SMA200"] = ta.trend.SMAIndicator(close, window=200).sma_indicator()
        df["EMA200"] = ta.trend.EMAIndicator(close, window=200).ema_indicator()
    df["EMA20_SLOPE"] = df["EMA20"].diff()
    return df


def add_momentum(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"].squeeze()
    df["RSI"] = ta.momentum.RSIIndicator(close).rsi()
    macd = ta.trend.MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    df["MACD_HIST"] = macd.macd_diff()
    return df


def add_volatility(df: pd.DataFrame) -> pd.DataFrame:
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()
    df["ATR"] = ta.volatility.AverageTrueRange(high=high, low=low, close=close).average_true_range()
    bb = ta.volatility.BollingerBands(close=close)
    df["BB_UPPER"] = bb.bollinger_hband()
    df["BB_MIDDLE"] = bb.bollinger_mavg()
    df["BB_LOWER"] = bb.bollinger_lband()
    mid = df["BB_MIDDLE"].replace(0, float("nan"))
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / mid
    df["BB_SQUEEZE"] = df["BB_WIDTH"] <= df["BB_WIDTH"].rolling(60, min_periods=20).quantile(0.2)
    return df


def add_momentum_detail(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"].squeeze()
    df["MOM"] = close.diff()
    df["MOM_ACCEL"] = df["MOM"].diff()
    rsi = ta.momentum.RSIIndicator(close).rsi()
    df["RSI_SLOPE"] = rsi.diff(3)
    return df


def add_session_levels(df: pd.DataFrame) -> pd.DataFrame:
    """Previous-day and previous-week levels from correctly ordered bars."""
    try:
        days = pd.to_datetime(df.index).normalize()
        week = pd.to_datetime(df.index).isocalendar()
        day_keys = pd.Series(days, index=df.index)
        grp = df.groupby(day_keys.values)
        per_day = grp.agg(H=("High", "max"), L=("Low", "min"), C=("Close", "last"))
        if len(per_day) >= 2:
            prev = per_day.shift(1)
            df["PREV_DAY_HIGH"] = prev["H"].reindex(day_keys.values).values
            df["PREV_DAY_LOW"] = prev["L"].reindex(day_keys.values).values
            df["PREV_DAY_CLOSE"] = prev["C"].reindex(day_keys.values).values
        wk_keys = pd.Series(list(zip(week.year.values if hasattr(week, "year") else [], week.week.values if hasattr(week, "week") else [])), index=df.index)
        per_week = df.groupby(wk_keys.values).agg(H=("High", "max"), L=("Low", "min"))
        if len(per_week) >= 2:
            prevw = per_week.shift(1)
            df["PREV_WEEK_HIGH"] = prevw["H"].reindex(wk_keys.values).values
            df["PREV_WEEK_LOW"] = prevw["L"].reindex(wk_keys.values).values
        df["GAP_PCT"] = (df["Open"] - df["PREV_DAY_CLOSE"]) / df["PREV_DAY_CLOSE"].replace(0, float("nan")) * 100
    except Exception:
        pass
    return df


def add_trend_strength(df: pd.DataFrame) -> pd.DataFrame:
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()
    adx = ta.trend.ADXIndicator(high=high, low=low, close=close)
    df["ADX"] = adx.adx()
    df["DI_PLUS"] = adx.adx_pos()
    df["DI_MINUS"] = adx.adx_neg()
    return df


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    close = df["Close"].squeeze()
    volume = df["Volume"].squeeze()
    df["VWAP"] = ta.volume.VolumeWeightedAveragePrice(
        high=high, low=low, close=close, volume=volume
    ).volume_weighted_average_price()
    df["VWAP_SLOPE"] = df["VWAP"].diff()
    df["VOL_MA20"] = volume.rolling(20).mean()
    df["VOL_RATIO"] = volume / df["VOL_MA20"].replace(0, float("nan"))
    return df


def add_price_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Candle anatomy, swings, and breakout flags from bars already closed.

    Swings use a 2-bar fractal on prior bars only (the last bar is not
    confirmed as a swing). Breakouts compare the current close with the
    previous session high/low or the prior 20-bar extreme — never the
    current bar's own high as the breakout level.
    """
    o = df["Open"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    body_top = pd.concat([o, c], axis=1).max(axis=1)
    body_bot = pd.concat([o, c], axis=1).min(axis=1)
    df["BODY"] = (c - o).abs()
    df["UPPER_WICK"] = h - body_top
    df["LOWER_WICK"] = body_bot - l
    prev_high = h.shift(1)
    prev_low = l.shift(1)
    swing_high = (prev_high > h.shift(2)) & (prev_high > h.shift(3)) & (prev_high > h) & (prev_high > h.shift(4))
    swing_low = (prev_low < l.shift(2)) & (prev_low < l.shift(3)) & (prev_low < l) & (prev_low < l.shift(4))
    df["SWING_HIGH"] = swing_high.fillna(False)
    df["SWING_LOW"] = swing_low.fillna(False)
    prior_high_20 = h.shift(1).rolling(20, min_periods=10).max()
    prior_low_20 = l.shift(1).rolling(20, min_periods=10).min()
    vol_ok = df["VOL_RATIO"].fillna(1) >= 1.3 if "VOL_RATIO" in df.columns else True
    day_high = df["PREV_DAY_HIGH"] if "PREV_DAY_HIGH" in df.columns else prior_high_20
    day_low = df["PREV_DAY_LOW"] if "PREV_DAY_LOW" in df.columns else prior_low_20
    df["BREAKOUT_UP"] = (c > prior_high_20) & vol_ok | (c > day_high)
    df["BREAKDOWN"] = (c < prior_low_20) & vol_ok | (c < day_low)
    df["EMA_CROSS"] = 0
    if "EMA9" in df.columns and "EMA20" in df.columns:
        spread = df["EMA9"] - df["EMA20"]
        prev = spread.shift(1)
        df.loc[(spread > 0) & (prev <= 0), "EMA_CROSS"] = 1
        df.loc[(spread < 0) & (prev >= 0), "EMA_CROSS"] = -1
    if "EMA20" in df.columns:
        df["PX_VS_EMA20"] = (c - df["EMA20"]) / df["EMA20"].replace(0, float("nan"))
    if "VWAP" in df.columns:
        df["PX_VS_VWAP"] = (c - df["VWAP"]) / df["VWAP"].replace(0, float("nan"))
    return df


def add_trend_label(df: pd.DataFrame) -> pd.DataFrame:
    df["Trend"] = df["EMA9"] - df["EMA20"]
    df["TREND_DIR"] = "neutral"
    df.loc[df["EMA9"] > df["EMA20"], "TREND_DIR"] = "bullish"
    df.loc[df["EMA9"] < df["EMA20"], "TREND_DIR"] = "bearish"
    return df


def apply_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all standard technical indicators to OHLCV data."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for fn in (
        add_moving_averages,
        add_momentum,
        add_volatility,
        add_momentum_detail,
        add_trend_strength,
        add_volume_indicators,
        add_session_levels,
        add_price_structure,
        add_trend_label,
    ):
        try:
            fn(out)
        except Exception:
            continue
    return out
