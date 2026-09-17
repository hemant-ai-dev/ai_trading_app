# Risk management (educational)

Angad does not place live broker orders from chat. Paper tasks may monitor prices and wait for human approval.

## Position risk basics

- Always pair a thesis with a stop. The Smart Box stop is a calculated invalidation, not a broker-guaranteed fill.
- High ATR or low confidence means smaller size or no trade.
- Do not stack correlated NSE names as if they were independent bets.
- News can gap through stops. Headlines are delayed and incomplete.

## What the AI must not do

- Promise profits or “risk-free” data.
- Execute real-money trades.
- Invent OHLC, volume, or news that tools did not return.
- Treat Stooq daily fallback as a live 5-minute tape.

If data is stale, missing, or from a fallback, say so before discussing entries.
