def get_signal(df):
    last = df.tail(1)

    close = last["Close"].values[0]
    ema9 = last["EMA9"].values[0]
    ema20 = last["EMA20"].values[0]
    rsi = last["RSI"].values[0]
    macd = last["MACD"].values[0]
    vwap = last["VWAP"].values[0]
    atr = last["ATR"].values[0]

    score = 0
    reason = []

    # -----------------------
    # EMA Trend
    # -----------------------
    if ema9 > ema20:
        score += 1
        reason.append("EMA Bullish")

    else:
        score -= 1
        reason.append("EMA Bearish")

    # -----------------------
    # RSI
    # -----------------------
    if rsi > 55:
        score += 1
        reason.append("RSI Strong")

    elif rsi < 45:
        score -= 1
        reason.append("RSI Weak")

    # -----------------------
    # MACD
    # -----------------------
    if macd > 0:
        score += 1
        reason.append("MACD Positive")

    else:
        score -= 1

    # -----------------------
    # VWAP
    # -----------------------
    if close > vwap:
        score += 1
        reason.append("Above VWAP")

    else:
        score -= 1

    # -----------------------
    # Final Decision
    # -----------------------
    if score >= 3:
        signal = "BUY"
        confidence = 75

    elif score <= -2:
        signal = "SELL"
        confidence = 72

    else:
        signal = "HOLD"
        confidence = 50

    # -----------------------
    # Stoploss & Target
    # -----------------------
    stop_loss = round(close - atr, 2)
    target = round(close + (atr * 2), 2)

    return {
        "signal": signal,
        "confidence": confidence,
        "stop_loss": stop_loss,
        "target": target,
        "reason": ", ".join(reason)
    }