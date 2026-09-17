# Technical indicators used by Angad

All indicators run locally on downloaded OHLCV. They are not a separate paid vendor.

- **Trend:** EMA stack, MACD, ADX when available.
- **Momentum:** RSI. Overbought/oversold is context, not an automatic reverse.
- **Volatility:** ATR, Bollinger width. Wide ATR raises risk.
- Volume: volume vs average; VWAP on intraday when those bars exist. Daily mode uses daily volume.
- **Structure:** swing support/resistance and Fibonacci retracements/extensions.
- **Candles/patterns:** local pattern tags, used as confirmation not as a standalone system.

If the chart window is too short, Angad fetches a longer lookback for indicators while the visible chart stays on the user’s period.
