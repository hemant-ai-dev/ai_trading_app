"""Rule-based signal engine with weighted scoring and dynamic confidence."""


def _safe_float(val, default=0.0):
    try:
        if val is None or val != val:  # NaN
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def get_signal(df):
    last = df.tail(1)

    close = _safe_float(last["Close"].values[0], 0)
    ema9 = _safe_float(last["EMA9"].values[0], close)
    ema20 = _safe_float(last["EMA20"].values[0], close)
    rsi = _safe_float(last["RSI"].values[0], 50)
    macd = _safe_float(last["MACD"].values[0], 0)
    macd_signal = _safe_float(last.get("MACD_SIGNAL", last["MACD"]).values[0], 0)
    vwap = _safe_float(last["VWAP"].values[0], close)
    atr = _safe_float(last["ATR"].values[0], max(close * 0.01, 1))
    volume = _safe_float(last["Volume"].values[0], 0)
    vol_ma = _safe_float(last.get("VOL_MA20", last["Volume"]).values[0], volume)

    score = 0.0
    reason = []

    # --- EMA trend (weight by separation %) ---
    if close > 0:
        ema_sep_pct = ((ema9 - ema20) / close) * 100
    else:
        ema_sep_pct = 0.0
    if ema9 > ema20:
        w = min(1.4, 0.45 + abs(ema_sep_pct) * 0.12)
        score += w
        reason.append(f"EMA Bullish ({ema_sep_pct:+.2f}%)")
    else:
        w = min(1.4, 0.45 + abs(ema_sep_pct) * 0.12)
        score -= w
        reason.append(f"EMA Bearish ({ema_sep_pct:+.2f}%)")

    # --- RSI (continuous, not flat 50/72 buckets) ---
    if rsi >= 60:
        score += min(1.3, (rsi - 50) / 25)
        reason.append(f"RSI Strong ({rsi:.1f})")
    elif rsi <= 40:
        score -= min(1.3, (50 - rsi) / 25)
        reason.append(f"RSI Weak ({rsi:.1f})")
    elif rsi > 52:
        score += 0.35
        reason.append(f"RSI Mild Bull ({rsi:.1f})")
    elif rsi < 48:
        score -= 0.35
        reason.append(f"RSI Mild Bear ({rsi:.1f})")
    else:
        reason.append(f"RSI Neutral ({rsi:.1f})")

    # --- MACD vs signal line ---
    if macd > macd_signal and macd > 0:
        score += 1.15
        reason.append("MACD Bullish cross")
    elif macd < macd_signal and macd < 0:
        score -= 1.15
        reason.append("MACD Bearish cross")
    elif macd > 0:
        score += 0.55
        reason.append("MACD Positive")
    else:
        score -= 0.55
        reason.append("MACD Negative")

    # --- VWAP (distance-weighted) ---
    if vwap > 0:
        vwap_dist_pct = ((close - vwap) / vwap) * 100
    else:
        vwap_dist_pct = 0.0
    if close > vwap:
        score += min(1.0, 0.25 + abs(vwap_dist_pct) * 0.08)
        reason.append(f"Above VWAP ({vwap_dist_pct:+.2f}%)")
    else:
        score -= min(1.0, 0.25 + abs(vwap_dist_pct) * 0.08)
        reason.append(f"Below VWAP ({vwap_dist_pct:+.2f}%)")

    # --- Volume confirmation (only nudges aligned direction) ---
    if vol_ma > 0 and volume > vol_ma * 1.15:
        if score > 0:
            score += 0.25
            reason.append("Volume supports up-move")
        elif score < 0:
            score -= 0.25
            reason.append("Volume supports down-move")
        else:
            reason.append("High volume, mixed trend")

    buy_cut = 2.4
    sell_cut = -2.4

    if score >= buy_cut:
        signal = "BUY"
    elif score <= sell_cut:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = _confidence_from_score(signal, score, buy_cut, sell_cut, rsi)

    if signal == "BUY":
        stop_loss = round(close - atr * 1.2, 2)
        target = round(close + atr * 2.2, 2)
    elif signal == "SELL":
        stop_loss = round(close + atr * 1.2, 2)
        target = round(close - atr * 2.2, 2)
    else:
        # HOLD: symmetric band around spot using ATR
        stop_loss = round(close - atr, 2)
        target = round(close + atr, 2)

    regime = _market_regime(close, ema9, ema20, rsi, vwap, atr)

    return {
        "signal": signal,
        "confidence": confidence,
        "score": round(score, 3),
        "stop_loss": stop_loss,
        "target": target,
        "reason": ", ".join(reason),
        "market_regime": regime,
    }


def _market_regime(close, ema9, ema20, rsi, vwap, atr):
    """Human-readable structure tag for SQL / Gen AI context."""
    if close > ema9 > ema20 and close > vwap and rsi >= 55:
        return "bullish_trend"
    if close < ema9 < ema20 and close < vwap and rsi <= 45:
        return "bearish_trend"
    if abs(close - vwap) < atr * 0.35:
        return "range_bound_vwap"
    if rsi >= 58:
        return "overbought_stretch"
    if rsi <= 42:
        return "oversold_stretch"
    return "mixed_transition"


def _confidence_from_score(signal, score, buy_cut, sell_cut, rsi):
    """Map continuous score to a readable confidence % — avoids fixed 72/50/75."""
    if signal == "HOLD":
        # Closer to 0 score → higher 'wait' confidence; near threshold → lower
        band = buy_cut
        neutrality = 1.0 - min(abs(score) / band, 1.0)
        # RSI near 50 reinforces neutral read
        rsi_neutral = 1.0 - min(abs(rsi - 50) / 25, 1.0)
        blend = 0.6 * neutrality + 0.4 * rsi_neutral
        return round(42 + blend * 28, 1)  # ~42–70%

    strength = min(abs(score) / 5.5, 1.0)
    base = 52
    conf = base + strength * 43  # ~52–95%
    if signal == "SELL" and rsi > 35:
        # Penalize sell confidence if RSI not yet weak
        conf -= min(8, (rsi - 35) * 0.3)
    if signal == "BUY" and rsi < 65:
        conf -= min(8, (65 - rsi) * 0.3)
    return round(max(48, min(94, conf)), 1)
