"""Technical indicators — RSI, MACD, EMA, SMA, VWAP, Bollinger, ATR, ADX, volume."""

from __future__ import annotations

import pandas as pd
import ta


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"].squeeze()
    df["EMA9"] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df["EMA20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    df["EMA50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df["SMA20"] = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    df["SMA50"] = ta.trend.SMAIndicator(close, window=50).sma_indicator()
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
    df["VOL_MA20"] = volume.rolling(20).mean()
    df["VOL_RATIO"] = volume / df["VOL_MA20"].replace(0, pd.NA)
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
    add_moving_averages(out)
    add_momentum(out)
    add_volatility(out)
    add_trend_strength(out)
    add_volume_indicators(out)
    add_trend_label(out)
    return out
