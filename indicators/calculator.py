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


def _detect_divergences(df: pd.DataFrame) -> list[str]:
    """Two-swing divergence check over the last ~30 completed bars."""
    out: list[str] = []
    try:
        window = df.tail(30)
        if "RSI" not in window.columns or len(window) < 15:
            return out
        price = window["Close"]
        rsi = window["RSI"]
        mid = len(window) // 2
        p1, p2 = price.iloc[:mid].min(), price.iloc[mid:].min()
        r1, r2 = rsi.iloc[:mid].min(), rsi.iloc[mid:].min()
        if p2 < p1 and r2 > r1 + 3:
            out.append("bullish_price_low_divergence")
        if p2 > p1 and r2 < r1 - 3:
            out.append("bearish_price_high_divergence")
    except Exception:
        pass
    return out


def build_indicator_context(df: pd.DataFrame) -> dict:
    """Build a snapshot of all indicator readings for prediction and display."""
    last = df.iloc[-1]
    fib = calculate_fibonacci_levels(df)
    sr = find_support_resistance(df)
    patterns = detect_candlestick_patterns(df)

    def _opt(key: str) -> float:
        val = last.get(key)
        try:
            f = float(val)
            return f if f == f else 0.0
        except (TypeError, ValueError):
            return 0.0

    return {
        "ohlcv": {
            "close": float(last["Close"]),
            "high": float(last["High"]),
            "low": float(last["Low"]),
            "open": float(last["Open"]),
            "volume": float(last["Volume"]),
        },
        "rsi": _safe_float(last.get("RSI"), 50.0),
        "rsi_slope": _opt("RSI_SLOPE"),
        "momentum_accel": _opt("MOM_ACCEL"),
        "ema9": _safe_float(last.get("EMA9"), float(last["Close"])),
        "ema20": _safe_float(last.get("EMA20"), float(last["Close"])),
        "ema50": _safe_float(last.get("EMA50"), float(last["Close"])),
        "ema200": _opt("EMA200"),
        "ema20_slope": _opt("EMA20_SLOPE"),
        "sma9": _safe_float(last.get("SMA9"), float(last["Close"])),
        "sma20": _safe_float(last.get("SMA20"), float(last["Close"])),
        "sma50": _safe_float(last.get("SMA50"), float(last["Close"])),
        "sma100": _opt("SMA100"),
        "sma200": _opt("SMA200"),
        "macd": _safe_float(last.get("MACD"), 0.0),
        "macd_signal": _safe_float(last.get("MACD_SIGNAL"), 0.0),
        "macd_hist": _safe_float(last.get("MACD_HIST"), 0.0),
        "vwap": _safe_float(last.get("VWAP"), float(last["Close"])),
        "vwap_slope": _opt("VWAP_SLOPE"),
        "body": _opt("BODY"),
        "upper_wick": _opt("UPPER_WICK"),
        "lower_wick": _opt("LOWER_WICK"),
        "px_vs_ema20": _opt("PX_VS_EMA20"),
        "px_vs_vwap": _opt("PX_VS_VWAP"),
        "ema_cross": int(_opt("EMA_CROSS")),
        "breakout_up": bool(last.get("BREAKOUT_UP") is True or last.get("BREAKOUT_UP") == 1),
        "breakdown": bool(last.get("BREAKDOWN") is True or last.get("BREAKDOWN") == 1),
        "atr": _safe_float(last.get("ATR"), 1.0),
        "adx": _safe_float(last.get("ADX"), 0.0),
        "di_plus": _safe_float(last.get("DI_PLUS"), 0.0),
        "di_minus": _safe_float(last.get("DI_MINUS"), 0.0),
        "bb_upper": _safe_float(last.get("BB_UPPER"), float(last["Close"])),
        "bb_middle": _safe_float(last.get("BB_MIDDLE"), float(last["Close"])),
        "bb_lower": _safe_float(last.get("BB_LOWER"), float(last["Close"])),
        "bb_width": _opt("BB_WIDTH"),
        "bb_squeeze": last.get("BB_SQUEEZE") is True,
        "vol_ma20": _safe_float(last.get("VOL_MA20"), float(last["Volume"])),
        "vol_ratio": _safe_float(last.get("VOL_RATIO"), 1.0),
        "prev_day_high": _opt("PREV_DAY_HIGH"),
        "prev_day_low": _opt("PREV_DAY_LOW"),
        "prev_day_close": _opt("PREV_DAY_CLOSE"),
        "prev_week_high": _opt("PREV_WEEK_HIGH"),
        "prev_week_low": _opt("PREV_WEEK_LOW"),
        "gap_pct": _opt("GAP_PCT"),
        "divergences": _detect_divergences(df),
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
