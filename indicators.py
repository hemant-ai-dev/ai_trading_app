import ta

def apply_indicators(df):
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    # -------------------------
    # RSI
    # -------------------------
    df["RSI"] = ta.momentum.RSIIndicator(
        close
    ).rsi()

    # -------------------------
    # EMA
    # -------------------------
    df["EMA9"] = ta.trend.EMAIndicator(
        close, window=9
    ).ema_indicator()

    df["EMA20"] = ta.trend.EMAIndicator(
        close, window=20
    ).ema_indicator()

    df["EMA50"] = ta.trend.EMAIndicator(
        close, window=50
    ).ema_indicator()

    # -------------------------
    # MACD
    # -------------------------
    macd = ta.trend.MACD(close)

    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    # -------------------------
    # VWAP
    # -------------------------
    df["VWAP"] = ta.volume.VolumeWeightedAveragePrice(
        high=high,
        low=low,
        close=close,
        volume=volume
    ).volume_weighted_average_price()

    # -------------------------
    # ATR (Volatility)
    # -------------------------
    df["ATR"] = ta.volatility.AverageTrueRange(
        high=high,
        low=low,
        close=close
    ).average_true_range()

    # -------------------------
    # Volume Moving Avg
    # -------------------------
    df["VOL_MA20"] = volume.rolling(20).mean()

    # -------------------------
    # Trend Strength
    # -------------------------
    df["Trend"] = df["EMA9"] - df["EMA20"]

    return df