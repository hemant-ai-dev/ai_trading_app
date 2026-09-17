# Application environment (how Angad is set up)

Use this when the user asks about the app environment, APIs, login files, or how data is fed to AI Chat.

## Runtime

- Streamlit desk on port 8501 (local default).
- Internal FastAPI on port 8765 with Swagger at /docs.
- Daily market mode: Yahoo Finance (yfinance) then Stooq CSV fallback. Not a live NSE tape.

## Where accounts live

- Usernames and bcrypt password hashes: data/users.xlsx
- Original passwords are never stored.
- Optional override: ANGAD_USERS_XLSX

## How AI Chat gets numbers

User question → symbol resolver (Nifty 50, nif50, TATAMOTORS, …) → internal tools get_quote, get_analysis, get_news, search_knowledge → grounded answer.

If someone types “Tell me about nif50”, the symbol is ^NSEI (Nifty 50), not TELL.NS.

## Config

- SQLite: data/storage/trading_tool.db
- Optional LLM polish: OPENAI_API_KEY (off by default). The LLM must not invent prices.
