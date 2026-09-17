# Signals, Smart Box, and forecasts

Angad produces educational BUY, SELL, or HOLD labels from Python analysis, not from an LLM inventing prices.

## How a signal is formed

1. Free OHLCV is downloaded and validated.
2. Local indicators (RSI, EMA, MACD, ATR, VWAP, Bollinger, Fibonacci, support/resistance) are computed on that series.
3. Regime, news tilt, and prediction history can adjust weights.
4. The decision engine emits signal, confidence, target, stop, and reasons.
5. Optional LLM text only explains those numbers. It must not replace the calculator.

## How to read the output

- **Fact:** last close, indicator values, timestamps, stored prediction rows.
- **Analysis:** why the engine prefers BUY, SELL, or HOLD.
- **Forecast:** predicted price and range. This is a model path, not a guaranteed next print.
- **Uncertainty:** low confidence, high ATR, missing news, weekend/empty sessions, or fallback daily data.

HOLD means there is no strong, confirmed setup — not a promise that price will stay still.

## Prediction history

Each saved row is append-only. Compare the latest signal to previous rows to see what changed. Accuracy statistics need enough evaluated outcomes; they are not a profit guarantee.
