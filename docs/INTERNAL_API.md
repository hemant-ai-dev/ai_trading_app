# Angad internal API

Educational desk. Not financial advice. Daily free-source bars only — not a live NSE/BSE tape and not a profit guarantee.

## Data mode

Required trading information uses **daily OHLCV** from:

| Provider | Type | Free? | Role |
| --- | --- | --- | --- |
| Yahoo Finance via `yfinance` | External, unofficial | Yes (no paid Yahoo plan) | Primary daily bars |
| Stooq daily CSV | External public CSV | Yes | Fallback if Yahoo is empty |
| Yahoo Finance headlines | External | Yes | Equity news context |
| BBC / NYT **public RSS** | External | Yes | World headlines (not paid article APIs) |
| Local `ta` indicators | Internal compute | Yes | RSI, EMA, MACD, ATR, etc. |
| `/api/v1` FastAPI | Internal | Yes | App service layer |
| Markdown RAG | Internal | Yes | Trading knowledge search |

Indian quotes are typically `SYMBOL.NS`. Yahoo/Stooq are **not** official exchange feeds. If both fail, the API returns unavailable — it does not invent prices.

## Run

```text
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit may start FastAPI on `127.0.0.1:8765` in a background thread. Streamlit Cloud only exposes the Streamlit port; the in-process gateway still powers AI Chat.

Standalone:

```text
python -m api.serve
```

OpenAPI: `http://127.0.0.1:8765/docs` (Swagger UI). Alias: `/api/docs`. ReDoc: `/redoc`.

## Authentication

`POST /api/v1/auth/login` with `{ "username", "password" }` (Excel user store, hashed passwords).

Returns a bearer token (`angad_…`) valid 12 hours. Send `Authorization: Bearer <token>`.

Rate limit: 60 requests/minute/user. Login attempts are also rate limited by IP.

Third-party keys are never returned.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/health` | No auth. `data_mode=daily` |
| POST | `/api/v1/auth/login` | Issue token |
| GET | `/api/v1/market/quote/{symbol}` | Last daily close |
| GET | `/api/v1/market/history/{symbol}?period=3mo&interval=1d` | Daily bars only |
| GET | `/api/v1/market/indicators/{symbol}` | Local TA on daily series |
| GET | `/api/v1/market/analysis/{symbol}` | Python engine + explanation |
| GET | `/api/v1/predictions/{symbol}` | Same analysis payload |
| GET | `/api/v1/predictions/{symbol}/history` | Append-only SQLite rows |
| GET | `/api/v1/news/{symbol}` | Free headlines |
| GET | `/api/v1/knowledge/search?q=` | RAG over `knowledge/corpus` |
| POST | `/api/v1/ai/chat` | `{message, symbol?, conversation_id?}` tools then optional LLM polish |
| GET/POST | `/api/v1/tasks` | Paper worker tasks, not live orders |
| GET | `/api/v1/system/api-status` | Catalog + usage |
| POST | `/api/v1/system/providers/{code}/enabled` | Admin only |

## Example

```http
POST /api/v1/auth/login
{"username":"trader1","password":"secret-pass1"}
```

```http
GET /api/v1/market/quote/TATAMOTORS.NS
Authorization: Bearer angad_…
```

Quote `ok: false` with `code: unavailable` means free providers returned no bars. Retry later or use cached UI state — do not treat that as a live price of zero.

## AI Chat flow

User question → orchestrator selects tools (`get_quote`, `get_analysis`, `get_news`, `get_prediction_history`, `search_knowledge`, `create_paper_task`) → internal gateway → Yahoo/Stooq/RSS/local TA → grounded reply. Optional OpenAI (`OPENAI_API_KEY`) only rewrites wording; it must not invent numbers. Default `llm.provider` is `none`.

## Workers

`POST /api/v1/tasks` creates paper/monitor jobs for the Workers portal. There is no live execution API.

## Config

- Users: `data/users.xlsx` or `ANGAD_USERS_XLSX`
- SQLite: `data/storage/trading_tool.db` or `ANGAD_SQLITE_PATH`
- API bind: `ANGAD_API_HOST`, `ANGAD_API_PORT` (default 8765)
- Disable background API: `ANGAD_API_AUTOSTART=0`
- Optional LLM: `OPENAI_API_KEY` (not used for market data)
