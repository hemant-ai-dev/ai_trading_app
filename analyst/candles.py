"""Step 5 — Expanded candlestick pattern detection."""

from __future__ import annotations

import pandas as pd


def detect_candlestick_patterns_rich(df: pd.DataFrame) -> list[dict]:
    """
    Detect beginner-friendly candlestick patterns on recent bars.

    Returns list of {name, direction, strength, reason}.
    """
    if df is None or len(df) < 3:
        return []

    o = df["Open"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)

    body = (c - o).abs()
    rng = (h - l).replace(0, float("nan"))
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l

    out: list[dict] = []

    def add(name: str, direction: str, strength: float, reason: str) -> None:
        out.append({"name": name, "direction": direction, "strength": strength, "reason": reason})

    def _f(val, default: float = 0.0) -> float:
        try:
            x = float(val)
            if x != x:
                return default
            return x
        except (TypeError, ValueError):
            return default

    # Last bar
    lb = _f(body.iloc[-1])
    lr = _f(rng.iloc[-1])
    lu = _f(upper.iloc[-1])
    ll = _f(lower.iloc[-1])
    bull = _f(c.iloc[-1]) > _f(o.iloc[-1])

    if lr > 0 and lb / lr < 0.1:
        add("Doji", "neutral", 0.45, "Tiny body — market is undecided; wait for confirmation.")
    if lr > 0 and ll > lb * 2 and lu < lb * 0.5:
        add("Hammer", "bullish", 0.65, "Long lower wick — buyers defended lower prices.")
    if lr > 0 and lu > lb * 2 and ll < lb * 0.5:
        add("Shooting Star", "bearish", 0.65, "Long upper wick — sellers rejected higher prices.")

    # Engulfing
    po, pc = _f(o.iloc[-2]), _f(c.iloc[-2])
    co, cc = _f(o.iloc[-1]), _f(c.iloc[-1])
    if pc < po and cc > co and cc >= po and co <= pc:
        add("Bullish Engulfing", "bullish", 0.75, "Current green candle fully covers prior red candle.")
    if pc > po and cc < co and cc <= po and co >= pc:
        add("Bearish Engulfing", "bearish", 0.75, "Current red candle fully covers prior green candle.")

    # Harami
    if abs(pc - po) > 0 and abs(cc - co) < abs(pc - po) * 0.5:
        if min(po, pc) <= min(co, cc) and max(po, pc) >= max(co, cc):
            direction = "bearish" if pc > po else "bullish"
            add("Harami", direction, 0.5, "Small candle inside prior body — possible pause / reverse.")

    # Morning / Evening star (3 candles)
    if len(df) >= 3:
        b0 = float(c.iloc[-3] - o.iloc[-3])
        b1 = float(body.iloc[-2])
        b2 = float(c.iloc[-1] - o.iloc[-1])
        r0 = _f(rng.iloc[-3], 1.0)
        if b0 < 0 and b1 < abs(b0) * 0.4 and b2 > 0 and float(c.iloc[-1]) > (float(o.iloc[-3]) + float(c.iloc[-3])) / 2:
            add("Morning Star", "bullish", 0.8, "Three-candle bullish reversal sequence.")
        if b0 > 0 and b1 < abs(b0) * 0.4 and b2 < 0 and float(c.iloc[-1]) < (float(o.iloc[-3]) + float(c.iloc[-3])) / 2:
            add("Evening Star", "bearish", 0.8, "Three-candle bearish reversal sequence.")

    # Three white soldiers / black crows
    if len(df) >= 3:
        last3_bull = all(float(c.iloc[-i]) > float(o.iloc[-i]) for i in (1, 2, 3))
        last3_bear = all(float(c.iloc[-i]) < float(o.iloc[-i]) for i in (1, 2, 3))
        rising = float(c.iloc[-1]) > float(c.iloc[-2]) > float(c.iloc[-3])
        falling = float(c.iloc[-1]) < float(c.iloc[-2]) < float(c.iloc[-3])
        if last3_bull and rising:
            add("Three White Soldiers", "bullish", 0.7, "Three strong green candles in a row — bullish continuation.")
        if last3_bear and falling:
            add("Three Black Crows", "bearish", 0.7, "Three strong red candles in a row — bearish continuation.")

    # Suppress unused variable warning style (bull used for potential extensions)
    _ = bull
    return out


def patterns_as_strings(patterns: list[dict]) -> list[str]:
    """Convert rich pattern dicts to beginner-friendly strings."""
    return [f"{p['name']} — {p['reason']}" for p in patterns]
