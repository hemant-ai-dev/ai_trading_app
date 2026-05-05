# Angad Trading Engine - Project Documentation

## 1. Project Motive & Objective
The primary motive for creating the **Angad Trading Engine** is to provide an interactive, educational intraday trading dashboard for Indian financial markets (NSE). 

Trading decisions often require synthesizing vast amounts of data—ranging from technical indicators and price action to macroeconomic news and market sentiment. The goal of this project is to bridge the gap between pure mathematical analysis and qualitative AI reasoning. 

By combining a **deterministic, rule-based signal engine** (which relies on established metrics like VWAP, MACD, and RSI) with an **optional Generative AI reasoning layer**, the system aims to present traders with a comprehensive "playbook." It acts as an intelligent assistant that not only flags potential BUY/SELL/HOLD opportunities based on strict math, but also explains the *why* by analyzing relevant news headlines and market calendars. 

*Note: This tool is strictly for educational purposes and is not intended to provide financial advice.*

---

## 2. Code Working Process & Data Flow

The application follows a linear pipeline every time it refreshes or when a user inputs a new stock symbol:

### Step 1: Market Context & Calendar Check
The system uses `market_calendar.py` to determine the current state of the Indian National Stock Exchange (NSE). It checks if the market is open, closed, or in a pre-market phase, providing the necessary temporal context.

### Step 2: Data Fetching
In `data_fetch.py`, the system connects to market data providers (primarily Yahoo Finance via `yfinance`). It downloads historical and intraday OHLCV (Open, High, Low, Close, Volume) data based on the user's selected period (e.g., 5 days) and interval (e.g., 5 minutes).

### Step 3: Technical Indicator Calculation
The raw data is passed into `indicators.py`, which utilizes the `ta` (Technical Analysis) library to compute critical data points for each candlestick:
- **RSI (Relative Strength Index):** Measures momentum.
- **EMA (Exponential Moving Averages):** 9, 20, and 50-period EMAs to gauge short-to-medium trend direction.
- **MACD (Moving Average Convergence Divergence):** Highlights trend reversals.
- **VWAP (Volume Weighted Average Price):** Indicates the true average price based on volume.
- **ATR (Average True Range):** Measures market volatility.

### Step 4: Rule-Based Signal Generation
The enriched dataframe is fed into `signal_engine.py`. This deterministic engine looks at the very last data point and assigns a score based on a set of rules:
- EMA 9 > EMA 20 (+1)
- RSI > 55 (+1) or < 45 (-1)
- MACD > 0 (+1)
- Close > VWAP (+1)
If the cumulative score is >= 3, it triggers a **BUY** signal. If <= -2, a **SELL** signal. Otherwise, it defaults to **HOLD**. It also utilizes the ATR to dynamically set logical Stop-Loss and Target reference levels.

### Step 5: News & Intelligence Gathering (Optional AI Layer)
In parallel, `market_intel.py` gathers the latest financial news and RSS feeds related to the selected stock and broader global macroeconomic events. 

### Step 6: Generative AI Synthesis (Optional)
If an OpenAI API key is configured, `genai_reason.py` kicks in. It takes the mathematical signals, the technical snapshot, and the latest news headlines, and feeds them into an LLM (Large Language Model). The LLM processes this massive context and returns a structured JSON response containing a strategic playbook, risk assessment, and sentiment tilt, giving the user a plain-English explanation of the market state.

### Step 7: UI Rendering
Finally, `app.py` acts as the orchestrator and the user interface. Built with **Streamlit**, it renders:
- The top-level metrics (Last Close, Signal, Confidence, Target/Stop-Loss).
- The AI Playbook tabs.
- A highly interactive Plotly chart overlaying the actual price action, the rule-based target projections, and the AI sentiment tilt.

---

## 3. Core Files & Page Explanation

- **`app.py`**  
  *Role:* The main application entry point and Streamlit frontend.  
  *Explanation:* It configures the sidebar, handles the auto-refresh loop, orchestrates calls to the data fetchers and AI layers, and heavily focuses on rendering the complex UI elements (Plotly charts, metric grids, and AI explanation tabs).

- **`data_fetch.py`**  
  *Role:* Data pipeline.  
  *Explanation:* Responsible for making requests to `yfinance`. It handles edge cases, ensures the data is downloaded correctly, and prepares the pandas DataFrame for the indicator engine.

- **`indicators.py`**  
  *Role:* The Math layer.  
  *Explanation:* A pure processing script that takes a raw DataFrame and appends columns for RSI, MACD, EMA, VWAP, ATR, etc. It centralizes all mathematical transformations.

- **`signal_engine.py`**  
  *Role:* The Logic layer.  
  *Explanation:* Implements the deterministic trading rules. It calculates a "score" to decide the market posture and calculates dynamic invalidation (stop-loss) and objective (target) prices based on volatility (ATR).

- **`genai_reason.py`**  
  *Role:* AI synthesis.  
  *Explanation:* Formats the complex prompt sent to the LLM. It defines the JSON schema that the LLM must follow to ensure the output can be safely parsed and displayed in the Streamlit tabs.

- **`market_intel.py`**  
  *Role:* News aggregator.  
  *Explanation:* Fetches external RSS feeds (Yahoo Finance, etc.) to give the AI engine real-world context regarding the stock being analyzed.

- **`market_calendar.py` & `intraday_forecast.py`**  
  *Role:* Utilities.  
  *Explanation:* Deal with timezone conversions (IST - Indian Standard Time), market session timings (open/close schedules), and projecting future plot lines on the chart based on the target price and AI sentiment.

- **`level_plan.py`**  
  *Role:* Charting utilities.  
  *Explanation:* Generates the horizontal reference lines on the chart, formatting the tooltips and managing the Y-axis constraints so the user view remains clean.

---

## Conclusion
The Angad Trading Engine is a modular, well-separated application. The clear division between Data Fetching, Math (Indicators), Logic (Signal Engine), and UI (Streamlit) makes it highly scalable and easy to iterate upon, whether you want to tweak the math rules or completely overhaul the AI integration.
