# Market data limits (Angad)

Angad never claims official NSE/BSE live feeds. Prices come from free, unofficial sources.

## Yahoo Finance (yfinance)

- Purpose: OHLCV candles and last traded-style prices for charts and indicators.
- Cost: No paid Yahoo plan is used. The yfinance library reads public Yahoo chart endpoints.
- Indian symbols: NSE tickers typically use the `.NS` suffix (example: TATAMOTORS.NS). BSE often uses `.BO`. Index examples: ^NSEI, ^NSEBANK, ^BSESN.
- Delay: Yahoo data is not a guaranteed real-time exchange feed. Treat prints as delayed or unofficial.
- Limits: Yahoo does not publish a supported retail quota for this unofficial client. Rate limits and empty bars happen. Do not invent candles when Yahoo returns nothing.

## Stooq daily CSV

- Purpose: Free fallback daily OHLCV when Yahoo returns no bars.
- Cost: Public CSV download, no API key.
- Limitation: Daily bars only. Intraday (1m/5m) charts are not available from this fallback.
- NSE coverage: Mapping such as RELIANCE.NS → reliance.in is best-effort and may be incomplete.

## News

- Yahoo Finance ticker headlines (free page/RSS-style access via existing news helpers).
- BBC World RSS and NYT World RSS are public feeds. They are not paid article-search APIs.
- Headlines are context, not a trading signal guarantee.

## Internal APIs

Frontend, AI Chat, and workers should call Angad internal services. Those services call Yahoo/Stooq/RSS. Third-party keys are never sent to the browser.

If both Yahoo and Stooq fail, the correct response is that market data is unavailable — never a fabricated price.
