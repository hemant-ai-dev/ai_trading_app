"""Unified indicator pipeline."""

from __future__ import annotations

import pandas as pd

from indicators.fibonacci import FibonacciLevels, calculate_fibonacci_levels
from indicators.patterns import detect_candlestick_patterns
from indicators.support_resistance import find_support_resistance
from indicators.technical import apply_technical_indicators


def apply_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all technical indicators to OHLCV data."""
    return apply_technical_indicators(df)


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        x = float(val)
        if x != x:
            return default
        return x
    except (TypeError, ValueError):
        return default


def build_indicator_context(df: pd.DataFrame) -> dict:
    """Build a snapshot of all indicator readings for prediction and display."""
    last = df.iloc[-1]
    fib = calculate_fibonacci_levels(df)
    sr = find_support_resistance(df)
    patterns = detect_candlestick_patterns(df)

    return {
        "ohlcv": {
            "close": float(last["Close"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "open": float(last["Open"]),
            "volume": float(last["Volume"]),
        },
        "rsi": _safe_float(last.get("RSI"), 50.0),
        "ema9": _safe_float(last.get("EMA9"), float(last["Close"])),
        "ema20": _safe_float(last.get("EMA20"), float(last["Close"])),
        "ema50": _safe_float(last.get("EMA50"), float(last["Close"])),
        "sma20": _safe_float(last.get("SMA20"), float(last["Close"])),
        "sma50": _safe_float(last.get("SMA50"), float(last["Close"])),
        "macd": _safe_float(last.get("MACD"), 0.0),
        "macd_signal": _safe_float(last.get("MACD_SIGNAL"), 0.0),
        "macd_hist": _safe_float(last.get("MACD_HIST"), 0.0),
        "vwap": _safe_float(last.get("VWAP"), float(last["Close"])),
        "atr": _safe_float(last.get("ATR"), 1.0),
        "adx": _safe_float(last.get("ADX"), 0.0),
        "di_plus": _safe_float(last.get("DI_PLUS"), 0.0),
        "di_minus": _safe_float(last.get("DI_MINUS"), 0.0),
        "bb_upper": _safe_float(last.get("BB_UPPER"), float(last["Close"])),
        "bb_middle": _safe_float(last.get("BB_MIDDLE"), float(last["Close"])),
        "bb_lower": _safe_float(last.get("BB_LOWER"), float(last["Close"])),
        "vol_ma20": _safe_float(last.get("VOL_MA20"), float(last["Volume"])),
        "vol_ratio": _safe_float(last.get("VOL_RATIO"), 1.0),
        "trend_dir": str(last.get("TREND_DIR", "neutral")),
        "fibonacci": fib,
        "support_resistance": sr,
        "patterns": patterns,
    }


def indicator_summary_text(ctx: dict) -> str:
    """Compact text summary for LLM prompts."""
    return (
        f"Close={ctx['ohlcv']['close']:.2f}, RSI={ctx['rsi']:.1f}, "
        f"EMA9={ctx['ema9']:.2f}, EMA20={ctx['ema20']:.2f}, "
        f"MACD={ctx['macd']:.4f}, VWAP={ctx['vwap']:.2f}, ADX={ctx['adx']:.1f}"
    )
