# अंगद (Angad) — एजेंटिक AI ट्रेडिंग असिस्टंट  
## संपूर्ण मराठी मार्गदर्शिका (प्रकल्प तपशीलवार दस्तऐवज)

> **महत्त्वाची सूचना:** हे टूल **शैक्षणिक / संशोधन** उद्देशाने आहे. हे आर्थिक सल्ला नाही. वास्तविक पैशाने ट्रेड करण्यापूर्वी स्वतःची जोखीम समजून घ्या.

---

# अनुक्रमणिका

| अध्याय | विषय |
|--------|------|
| १ | प्रकल्प ओळख — हे AI टूल काय आहे? |
| २ | कोडची रचना — फोल्डर्स, फाईल्स, वाचनक्रम |
| ३ | अॅप कसे चालते? (सुरुवात ते निकाल) |
| ४ | AI कसे काम करते? (मल्टी-एजंट डेस्क) |
| ५ | प्रत्येक एजंटचा तपशील |
| ६ | गणित व नियम — स्कोअर, कॉन्फिडन्स, रिस्क |
| ७ | चार्ट कसा वाचायचा — रंग, रेषा, चिन्हे |
| ८ | स्क्रीनवर प्रत्येक पॅनेल / बटण / टॉगल |
| ९ | भविष्यवाणी (Prediction) पूर्ण समजून घेणे |
| १० | इतिहास / अचूकता / लर्निंग |
| ११ | Gen AI मोड |
| १२ | सेटिंग्ज, API की, चालवणे |
| १३ | कोड वाचण्याचा व्यावहारिक क्रम (नवशिक्यांसाठी) |
| १४ | सामान्य प्रश्न व चेतावण्या |

---

# अध्याय १ — प्रकल्प ओळख: हे AI टूल काय आहे?

## १.१ नाव व उद्देश

**Angad — Agentic AI Trading Assistant** हे एक Streamlit आधारित ट्रेडिंग टर्मिनल आहे.

हे साधे “एक फॉर्म्युला = BUY/SELL” बॉट नाही.  
उलट, हे **अनुभवी ट्रेडरच्या टीमसारखे** वागते:

1. मार्केट डेटा गोळा करते  
2. बातम्या तपासते  
3. कोणते इंडिकेटर्स आता महत्त्वाचे आहेत ते ठरवते  
4. पॅटर्न्स शोधते  
5. सर्व पुरावे वजन देऊन निर्णय घेते  
6. जोखीम (stop / target / position size) काढते  
7. सोप्या भाषेत **का?** हे समजावून सांगते  
8. जुने अंदाज लक्षात ठेवून शिकण्याचा प्रयत्न करते  

## १.२ हे काय देते?

| आउटपुट | अर्थ |
|--------|------|
| **Signal** | `BUY` / `SELL` / `HOLD` |
| **Confidence** | ०–१००% जवळचा विश्वास |
| **Predicted Price** | अपेक्षित किंमत (waypoint) |
| **Target** | नफा लक्ष्य |
| **Stop Loss** | चुकीला झाल्यास बाहेर पडण्याची पातळी |
| **Range** | अपेक्षित खालची–वरची पट्टी |
| **Risk level** | Low / Medium / High |
| **Scenarios** | Bullish / Base / Bearish शक्यता |
| **Report** | पूर्ण स्पष्टीकरण |

## १.३ “Agentic” म्हणजे काय?

**Agentic** = अनेक छोट्या AI/नियम मॉड्यूल्स (एजंट्स) स्वतंत्र काम करतात आणि एक **Orchestrator** त्यांचे निकाल एकत्र करतो.

उदाहरण: बातम्या खूप जोरदार असतील तर News वजन वाढते; मार्केट ट्रेंडमध्ये असेल तर EMA/MACD वजन वाढते; साइडवेजमध्ये RSI/Bollinger वजन वाढते.

---

# अध्याय २ — कोडची रचना: फोल्डर्स, फाईल्स, वाचनक्रम

## २.१ प्रोजेक्ट रूट (महत्त्वाचे फोल्डर्स)

प्रोजेक्ट पथ: `d:\Projects\ai_trading_app`

| फोल्डर / फाईल | उद्देश (एक ओळीत) |
|---------------|-------------------|
| `app.py` | Streamlit सुरू होते इथून — UI + कंट्रोल्स |
| `agents/` | नामित एजंट क्लासेस + Orchestrator |
| `analyst/` | मुख्य AI लॉजिक — regime, weights, decision, risk, report |
| `ai/` | LLM (OpenAI) कनेक्शन + सोपे explanation |
| `charts/` | Plotly कॅंडलस्टिक चार्ट, थीम, अचूकता ग्राफ |
| `config/` | defaults.json / local.json — सेटिंग्ज व API की |
| `data/` | मार्केट डेटा प्रोव्हायडर, कॅश, prediction JSON स्टोरेज |
| `indicators/` | RSI, MACD, EMA, ATR, ADX, Fib, Support/Resistance |
| `prediction/` | इंजिन, GenAI, नियम इंजिन, इतिहास, अचूकता |
| `providers/` | yfinance / news / LLM अडॅप्टर्स |
| `services/` | AnalysisService, MarketService, NewsService |
| `ui/` | डॅशबोर्ड पॅनेल्स, स्टाइल्स |
| `utils/` | लॉगिंग, IST वेळ |
| `tests/` | युनिट टेस्ट्स |
| `docs/` | ही मार्गदर्शिका |
| `Prompt.txt` | मूळ उत्पादन डिझाइन डॉक्युमेंट |
| `requirements.txt` | Python पॅकेजेस |
| `venv/` | स्थानिक Python वर्च्युअल एन्व्हायरनमेंट |

## २.२ सर्वात महत्त्वाच्या फाईल्स (कोड वाचताना)

### UI व एंट्री

| फाईल | काय करते |
|------|----------|
| `app.py` | साइडबार बटणे, टॅब्स, analyze() कॉल |
| `ui/dashboard.py` | प्रत्येक पॅनेल: explanation, news, risk, chart render |
| `ui/styles.py` | CSS / थीम |
| `charts/price_chart.py` | कॅंडल्स, रेषा, रंग, markers |
| `charts/themes.py` | dark/light रंगकोड |

### सेवा व पाइपलाइन

| फाईल | काय करते |
|------|----------|
| `services/analysis_service.py` | पूर्ण विश्लेषण ऑर्केस्ट्रेशन |
| `services/market_service.py` | OHLCV डेटा आणणे |
| `services/news_service.py` | बातम्या आणणे |
| `prediction/engine.py` | Analyst + optional GenAI |
| `analyst/pipeline.py` | **मुख्य मल्टी-एजंट पाइपलाइन** |

### Analyst एजंट लॉजिक

| फाईल | काय करते |
|------|----------|
| `analyst/context_gatherer.py` | मार्केट रिसर्च (Nifty, VIX, USDINR…) |
| `analyst/news_impact.py` | बातम्या bullish/bearish स्कोअर |
| `analyst/regime.py` | ट्रेंड/साइडवेज/व्होलॅटाइल ओळख |
| `analyst/weight_engine.py` | डायनॅमिक वजन |
| `analyst/decision_engine.py` | पुरावे → BUY/SELL/HOLD |
| `analyst/candles.py` | कॅंडलस्टिक पॅटर्न्स |
| `analyst/chart_patterns.py` | Double Top, H&S, Cup & Handle… |
| `analyst/risk.py` | Stop, Target, R:R, Position size |
| `analyst/scenarios.py` | ३ भविष्य मार्ग |
| `analyst/report.py` | पूर्ण रिपोर्ट |
| `analyst/memory.py` | जुनी अचूकता → वजन nudge |
| `analyst/models.py` | Data classes (EvidenceFactor, Report…) |

### Agents पॅकेज

| फाईल | काय करते |
|------|----------|
| `agents/__init__.py` | MarketDataAgent, NewsAgent, DecisionAgent… |
| `agents/orchestrator.py` | OrchestratorAgent (pipeline ला कॉल) |

## २.३ कोड वाचण्याचा सुलभ क्रम (नवशिक्यांसाठी)

जर तुम्ही पहिल्यांदा कोड उघडत असाल, **हा क्रम** अनुसरा:

```
१) app.py                          ← UI व कंट्रोल्स
२) services/analysis_service.py    ← analyze() काय कॉल करते
३) prediction/engine.py            ← Analyst + GenAI
४) analyst/pipeline.py             ← एजंट्सची क्रमवारी (सर्वात महत्त्वाचे)
५) analyst/decision_engine.py      ← निर्णय कसा होतो
६) analyst/risk.py                 ← Stop/Target कसे
७) charts/price_chart.py           ← चार्टवर काय दिसते
८) ui/dashboard.py                 ← स्क्रीनवर मजकूर कसा येतो
```

### कोडमधील “ओळख चिन्हे”

- फंक्शन नावे: `run_...`, `build_...`, `detect_...`, `render_...`
- `render_*` = UI दाखवणे  
- `build_*` = डेटा/रिपोर्ट तयार करणे  
- `detect_*` = पॅटर्न/regime शोधणे  
- `run_*` = पूर्ण पाइपलाइन चालवणे  

## २.४ डेटा कसा फिरतो? (एक चित्रात्मक प्रवाह)

```
[वापरकर्ता: Symbol/Period/Interval]
        │
        ▼
   app.py → AnalysisService.analyze()
        │
        ├─► MarketService → OHLCV (yfinance)
        ├─► apply_all_indicators() → RSI/MACD/EMA…
        ├─► NewsService → equity + world headlines
        └─► run_prediction_pipeline()
                │
                ├─► run_analyst_pipeline()  ← मुख्य AI निर्णय
                │       Market → News → Regime → Patterns
                │       → Learning → Decision → Risk → Report
                │
                └─► (optional) GenAI narrative merge
        │
        ▼
   PredictionResult + scenarios + explanation
        │
        ▼
   ui/dashboard + charts/price_chart  → स्क्रीन
        │
        ▼
   PredictionHistoryStore → data/storage/predictions.json
```

---

# अध्याय ३ — अॅप कसे चालते? (सुरुवात ते निकाल)

## ३.१ स्टार्टअप

1. `load_settings()` → `config/defaults.json` + `config/local.json`  
2. `AnalysisService(SETTINGS)` तयार  
3. `PredictionHistoryStore()` तयार  
4. Streamlit पेज: **Angad AI Trading Terminal**  
5. साइडबार कंट्रोल्स लोड  
6. `@st.fragment` — Auto-refresh चालू असेल तर ~६० सेकंदांनी पुन्हा विश्लेषण  

## ३.२ एका रिफ्रेशमध्ये काय होते?

1. NSE सत्र स्थिती (`get_market_status`) — खुले/बंद/सुट्टी  
2. निवडलेल्या सिम्बॉलचे OHLCV आणणे  
3. सर्व इंडिकेटर्स गणना  
4. बातम्या गोळा  
5. Analyst पाइपलाइन → Signal + Confidence + Risk  
6. (जर Gen AI ऑन) LLM कडून कथा/समायोजन  
7. इतिहास अपडेट — जुने अंदाज vs आताची किंमत  
8. नवीन अंदाज JSON मध्ये सेव्ह  
9. UI वर चार्ट + पॅनेल्स दाखवणे  

## ३.३ मुख्य Python कमांड

```bash
cd d:\Projects\ai_trading_app
.\venv\Scripts\python.exe -m streamlit run app.py
```

ब्राउझर: **http://localhost:8501**

---

# अध्याय ४ — AI कसे काम करते? (मल्टी-एजंट डेस्क)

## ४.१ मूलभूत तत्त्वे (Prompt.txt नुसार)

1. **एकच स्ट्रॅटेजी अंधत्वाने फॉलो करू नये**  
2. सध्याच्या मार्केट स्थितीनुसार पद्धती बदलाव्यात  
3. प्रत्येक निर्णयाचे स्पष्टीकरण हवे  
4. मॉड्युलर असावे — नवीन एजंट सहज जोडता येईल  

## ४.२ “AI” इथे दोन स्तरांवर आहे

| स्तर | प्रकार | काय करते |
|------|--------|----------|
| **A. Deterministic Analyst** | नियम + वजन + स्कोअर | नेहमी चालतो; मुख्य Signal येथून |
| **B. Gen AI (Optional)** | OpenAI LLM | कथा, अतिरिक्त दृष्टिकोन; कधीकधी निर्णय blend |

**डीफॉल्ट:** Gen AI बंद → फक्त Analyst.

## ४.३ Analyst निर्णय कसा “विचार” करतो?

1. सर्व पुरावे `EvidenceFactor` बनतात (EMA, RSI, News…)  
2. प्रत्येकाला `direction` (bullish/bearish/neutral), `strength`, `weight`  
3. `contribution = signed_strength × weight` (फक्त accepted)  
4. सर्व contribution ची बेरीज = **score**  
5. score ≥ +१.८ → BUY; ≤ −१.८ → SELL; अन्यथा HOLD  
6. confidence = score ची ताकद + एजंट्स किती एकमत आहेत  

म्हणजे हे “जादू” नाही — **मोजता येणारे वजन असलेले पुरावे** आहेत.

---

# अध्याय ५ — प्रत्येक एजंटचा तपशील

पाइपलाइन क्रम (`analyst/pipeline.py`):

## ५.१ Market Research Agent

**फाईल:** `analyst/context_gatherer.py`

**काय गोळा करते:**
- Live OHLC, Volume  
- ATR, ADX, RSI, VWAP, trend  
- मॅक्रो: Nifty 50, Bank Nifty, India VIX, US VIX, USDINR, Crude, Gold, US 10Y  
- Nifty विरुद्ध Relative Strength  

**अजून कनेक्ट नसलेले** (placeholder संदेश):
- Order book, Open Interest, Options chain, FII/DII, Economic calendar…

## ५.२ News Intelligence Agent

**फाईल:** `analyst/news_impact.py`

- प्रत्येक हेडलाइन → **bullish / bearish / neutral**  
- Keyword matching + amplifiers (earnings, RBI, Fed, war…)  
- Strength ०–१  
- एकत्रित `tilt` व `net_score`  
- `major_event` जर strength ≥ ०.७  

**उदाहरण:** “Infosys beats earnings” → bullish + amplifier.

## ५.३ Technical Analysis Agent (Regime)

**फाईल:** `analyst/regime.py`

| Regime | कधी ओळखते | कोणते टूल्स प्राधान्य |
|--------|-----------|----------------------|
| **breakout** | Volume ≥ १.६×, ADX ≥ २२, EMA अंतर | volume, VWAP, EMA, S/R, MACD, ATR |
| **volatile** | ATR% ≥ १.८ किंवा India VIX ≥ १८ | ATR, VWAP, volume, S/R, Bollinger |
| **trending_up/down** | ADX ≥ २५ + trend | EMA, SMA, ADX, MACD, Fib |
| **sideways** | ADX < १८ किंवा RSI मध्ये + EMA जवळ | RSI, Bollinger, S/R, candles |
| soft trend | मिश्र | मिश्र साधने |

**Auto-select indicators** या regime वरून चार्ट चेकबॉक्स सुचवते.

## ५.४ Pattern Recognition Agent

**फाईल्स:** `analyst/chart_patterns.py`, `analyst/candles.py`

**चार्ट पॅटर्न्स (heuristic):**
- Double Top / Double Bottom  
- Head & Shoulders / Inverse  
- Triangle / Compression  
- Flag / Pennant  
- Channel, Rectangle, Wedge  
- Cup & Handle  
- Harmonic AB=CD hint  

**कॅंडल्स:**
- Doji, Hammer, Shooting Star  
- Bullish/Bearish Engulfing, Harami  
- Morning/Evening Star  
- Three White Soldiers / Three Black Crows  

## ५.५ Learning Agent

**फाईल:** `analyst/memory.py`

- गेल्या अंदाजांची win rate / error पाहते  
- वजन थोडे nudge करते (उदा. win कमी → volume/S&R वाढव)  
- पुरेसा इतिहास नसेल तर nudge नाही  

## ५.६ Decision Agent

**फाईल्स:** `analyst/weight_engine.py` + `analyst/decision_engine.py`

- Dynamic weights (regime + news + memory)  
- Evidence factors  
- Conflict resolution: ट्रेंडमध्ये reverse RSI/BB **reject** होऊ शकते  
- Final BUY/SELL/HOLD  

## ५.७ Risk Management Agent

**फाईल:** `analyst/risk.py`

- Risk level  
- Stop Loss, Target, Predicted  
- Risk/Reward ratio  
- Position size (% of capital) — डीफॉल्ट भांडवल ₹१,००,०००, जास्तीत जास्त जोखीम ~१%  

## ५.८ Explainable AI Agent

**फाईल:** `analyst/report.py` + `ai/explainer.py`

- Market summary, technical, news, patterns, risk, probabilities  
- Why / Rejected / Invalidation / Targets  
- Beginner-friendly Marathi/English मिश्र UI मजकूर (UI इंग्रजीत आहे; हा दस्तऐवज मराठीत)  

## ५.९ Sentiment Agent (क्लास)

`agents/__init__.py` मध्ये आहे — सध्या news aggregate वरून tilt काढतो. सोशल सेंटिमेंट नंतर जोडता येईल.

## ५.१० Orchestrator Agent

`agents/orchestrator.py` → प्रत्यक्षात `run_analyst_pipeline()` चालवतो.  
UI मध्ये **Multi-agent desk (orchestrator trace)** मध्ये प्रत्येक एजंटचा सारांश दिसतो.

---

# अध्याय ६ — गणित व नियम (सर्व महत्त्वाचे थ्रेशहोल्ड)

## ६.१ Decision Score

```
score = Σ (signed_strength × weight)   # फक्त accepted factors
```

| Score | Signal |
|-------|--------|
| ≥ **+१.८** | BUY |
| ≤ **−१.८** | SELL |
| मध्ये | HOLD |

## ६.२ Confidence

- `magnitude = min(|score| / 5, 1)`  
- `agreement` = किती accepted factors एका दिशेने आहेत  

**BUY/SELL:**  
`confidence ≈ 55 + magnitude×28 + agreement×12` → क्लॅम्प **४८ ते ९४**

**HOLD:**  
`confidence ≈ 42 + (1−magnitude)×22 + agreement×8`

## ६.३ मुख्य Evidence नियम (Decision Engine)

| घटक | Bullish संकेत | Bearish संकेत |
|------|---------------|----------------|
| EMA stack | 9 > 20 > 50 (+०.९) | 9 < 20 < 50 (−०.९) |
| RSI | ≤३० oversold (+०.८५); ≥५५ mild (+०.३५) | ≥७० (−०.८५); ≤४५ mild (−०.३५) |
| MACD | MACD > signal आणि >० (+०.८) | MACD < signal आणि <० (−०.८) |
| VWAP | किंमत VWAP वर ATR×०.३ पेक्षा जास्त | खाली तितकेच |
| Bollinger | Lower band ला bounce | Upper band ला reject |
| Volume | ratio ≥ १.५ + किंमत EMA वर/खाली | volume ≤ ०.७ → reject (कमजोर) |
| ADX | ADX ≥ **२५** → ट्रेंड कन्फर्म | ADX कमी → reject |
| Support/Resistance | Support जवळ ०.४% | Resistance जवळ ०.४% |
| News | net_score मजबूत | net_score नकारात्मक |
| India VIX | ≤१२ शांत (+०.१५) | ≥१८ जोखीम (−०.२५) |

**Reject उदाहरणे:**
- RSI ४५–५५ मधला → “neutral, not actionable”  
- मजबूत uptrend मध्ये weak bearish RSI → de-emphasized  
- Sideways मध्ये weak trend signal → reject  

## ६.४ Dynamic Weights (उदाहरणे)

**Base (साधारण):**
- trend १.०, momentum ०.९, macd ०.९, news ०.८५, fib ०.८, vwap ०.७…

**Trending:**
- trend ×१.३५, macd ×१.२५, adx ×१.३  
- momentum ×०.७५, bollinger ×०.७  

**Sideways:**
- momentum/bollinger ×१.३५, S/R ×१.३  
- trend ×०.६५  

**Breakout:**
- volume ×१.४५, vwap ×१.२५  

**Major news:**
- news ×१.६  

शेवटी वजन mean-normalize ≈ १.०.

## ६.५ Risk Plan (ATR multiples)

`atr = max(atr, close×0.002, 0.01)`  
`atr_pct = atr/close × 100`

### Risk Level

| अट | Level |
|----|-------|
| atr_pct > २.५ किंवा conf < ५५ किंवा volatile | **High** |
| atr_pct > १.२ किंवा conf < ७० किंवा breakout | **Medium** |
| अन्यथा | **Low** |

### Target / Stop multiples

| Regime | Target × ATR | Stop × ATR |
|--------|--------------|------------|
| Trending + conf≥७० | ३.० | १.२ |
| Breakout | २.५ | १.३ |
| Volatile | २.० | १.६ |
| Sideways | १.५ | १.० |
| Default | २.२ | १.२ |

**BUY उदाहरण:**
- `target = close + atr × target_mult`  
- `stop = close − atr × stop_mult`  
- `predicted = close + atr × (target_mult × ०.४५)`  

**SELL:** वरचे आरसे (mirror).  
**HOLD:** ±०.६ ATR stop/target, predicted = close.

### Risk/Reward व Position

```
R:R = reward_distance / risk_distance
risk_pct = 1% × (Low=1.0 / Medium=0.7 / High=0.4)   # HOLD मध्ये ×0.5
shares ≈ (capital × risk_pct/100) / risk_per_share
```

डीफॉल्ट capital = ₹१,००,०००.

## ६.६ Scenarios संभाव्यता

- BUY: bullish शक्यता वाढते confidence नुसार  
- SELL: bearish वाढते  
- HOLD: जवळपास २८% / ४४% / २८% (bull/base/bear)  
- नंतर normalize करून बेरीज १००%  

## ६.७ News scoring

```
strength ≈ min(1.0, 0.35 + 0.15×keyword_hits + 0.12×amplifiers)
net = bull_score − bear_score
tilt = bullish if net > 0.45 else bearish if net < −0.45 else neutral
```

## ६.८ इंडिकेटर पीरियड्स (ta लायब्ररी)

| इंडिकेटर | डीफॉल्ट |
|----------|---------|
| EMA | ९ / २० / ५० |
| SMA | २० / ५० |
| RSI | १४ |
| MACD | १२ / २६ / ९ |
| ATR | १४ |
| ADX | १४ |
| Bollinger | २०, ± २ |
| Volume MA | २० |

`trend_dir`: साधारणतः EMA९ vs EMA२०.

---

# अध्याय ७ — चार्ट कसा वाचायचा (रंग, रेषा, चिन्हे)

## ७.१ Dark थीम (डीफॉल्ट) — रंगकोष्टक

| घटक | रंग (Hex) | अर्थ |
|------|-----------|------|
| हिरवी कॅंडल | `#26a69a` | Close ≥ Open (खरेदी दबाव) |
| लाल कॅंडल | `#ef5350` | Close < Open (विक्री दबाव) |
| **AI भविष्य रेषा (मुख्य)** | `#f0b90b` पिवळी/सोनेरी, जाडी ३ | Base scenario / predicted path |
| Confidence band | पिवळा अर्धपारदर्शक | अपेक्षित उच्च-निम्न पट्टी |
| जुने prediction overlays | फिकट पिवळे dotted | भूतकाळातील AI मार्ग |
| Buy marker | हिरवा ▲ triangle-up | BUY संकेत |
| Sell marker | लाल ▼ triangle-down | SELL संकेत |
| Hold marker | पिवळा ◆ diamond | HOLD |
| Bullish scenario | हिरवा dotted | वरची शक्यता |
| Bearish scenario | लाल dotted | खालची शक्यता |
| News marker | उघडा diamond | बातम्या प्रभाव |
| EMA ९ | `#2962ff` निळा | जलद सरासरी |
| EMA २० | `#ff6d00` नारिंगी | मध्यम |
| EMA ५० | `#e040fb` गुलाबी/जांभळा | मंद |
| SMA २० | `#00bcd4` | साधी सरासरी |
| SMA ५० | `#8d6e63` तपकिरी | |
| VWAP | `#ab47bc` जांभळा | व्हॉल्यूम वजन सरासरी |
| Bollinger | निळसर dotted + fill | volatility बँड्स |
| Fibonacci | जांभळ्या आडव्या रेषा | ३८.२% / ५०% / ६१.८% |
| Support | `#2196f3` निळ्या dashed | आधार |
| Resistance | `#ff9800` नारिंगी dashed | प्रतिरोध |
| RSI रेषा | `#7e57c2` | ३०/५०/७० आडव्या |
| MACD | हिरवी; Signal लाल; Hist बार | मोमेंटम |
| ATR | राखाडी | अस्थिरता |
| ADX | निळा | ट्रेंड सामर्थ्य |
| Correct annotation | हिरवा | अंदाज बरोबर जवळ |
| Incorrect | लाल | अंदाज चुकला |

**पार्श्वभूमी:** `#0b0e11` (काळा टर्मिनल लुक).

## ७.२ Light थीम फरक

- Up candle `#089981`, Down `#f23645`  
- Prediction `#f57c00` नारिंगी  
- बाकी लॉजिक समान  

## ७.३ चार्ट पॅनेल्स (वरून खाली)

1. **Price** — कॅंडल्स + overlays + AI path  
2. **Volume** (जर ऑन) — बार + २०-बार सरासरी  
3. **RSI** (जर ऑन)  
4. **MACD** (जर ऑन)  
5. **ATR/ADX** (जर ऑन)  

## ७.४ AI Prediction Line कशी काढली जाते?

1. Decision नंतर Risk Plan → target/stop/predicted  
2. `build_scenarios()` → bullish/base/bearish series (IST सत्र ५m ग्रिड)  
3. **Base series** = मुख्य पिवळी रेषा  
4. रेषा **शेवटच्या कॅंडलच्या Close पासून** भविष्यकाळात जाते  
5. Confidence कमी → band रुंद (`width_pct = max(0.004, (100−conf)/100 × 0.04)`)  

## ७.५ Markers कसे वाचावे

| चिन्ह | अर्थ |
|-------|------|
| ▲ हिरवा | इतिहास/सध्याचा BUY |
| ▼ लाल | SELL |
| ◆ पिवळा | HOLD |
| ◇ (उघडा) | News — hover वर हेडलाइन |
| Annotation Correct/Incorrect | जुना अंदाज vs प्रत्यक्ष किंमत |

## ७.६ चार्ट खालील कॅप्शन (इंग्रजी UI)

> Candles = market OHLC · Yellow line = AI future prediction · Triangles = Buy/Sell · Diamond = Hold · Annotations = pred vs reality

---

# अध्याय ८ — प्रत्येक बटण, टॉगल, पॅनेल कसे मदत करते

## ८.१ साइडबार — Controls

| कंट्रोल | डीफॉल्ट | काय करते / कसे मदत |
|---------|---------|---------------------|
| **Reload settings** | — | `local.json` पुन्हा लोड; API की बदलली तर उपयोगी |
| **Symbol** | Infosys इ. | प्रीसेट इंडेक्स/स्टॉक |
| **Ticker** | Custom वर | उदा. `SBIN.NS`, `TATASTEEL.NS` |
| **Period** | `5d` | किती इतिहास: १ दिवस / ५ दिवस / १ महिना |
| **Interval** | `5m` | कॅंडल साइज: १m/५m/१५m/१h — छोटा = जास्त आवाज |
| **Auto-refresh ~60s** | ON | दर मिनिटाला नवीन डेटा+AI |
| **Use Gen AI** | OFF | OpenAI कथा/blend; की हवी |
| **World news** | ON | जागतिक बातम्याही स्कोअर |
| **Chart theme** | dark | डार्क/लाइट रंग |
| **Compact chart** | OFF | मोबाइल/छोटा चार्ट |
| **Chart Indicators** चेकबॉक्स | मिश्र | कोणते overlays दिसायचे |
| **Auto-select indicators (regime)** | ON | Regime नुसार उपयुक्त इंडिकेटर्स आपोआप ON |

### Symbol प्रीसेट्स

| UI नाव | Yahoo टिकर |
|--------|------------|
| Nifty 50 | `^NSEI` |
| Bank Nifty | `^NSEBANK` |
| Sensex | `^BSESN` |
| Reliance | `RELIANCE.NS` |
| TCS | `TCS.NS` |
| Infosys | `INFY.NS` |
| Custom | तुम्ही लिहा |

## ८.२ वरची पट्टी (Top Bar)

| मेट्रिक | अर्थ |
|---------|------|
| Symbol | निवडलेला टिकर |
| IST Time | भारतीय वेळ |
| Session | मार्केट फेज (Pre-open / Open / Post-close…) |
| Live Price | शेवटची Close |
| Signal | BUY/SELL/HOLD |
| Confidence | टक्के विश्वास |

रंग पट्टी Signal नुसार: हिरवा / लाल / पिवळा.

## ८.३ टॅब्स

### A) Trading Desk

**डावीकडे:**
- Candlestick Chart  
- Predicted / Target / Stop / Range  
- Compare Prediction vs Reality  
- Alternative Scenarios टेबल  
- Multi-agent desk expander  

**उजवीकडे:**
- AI Explanation (+ Supporting / Conflicting)  
- Confidence Meter  
- Risk Meter  
- Risk Management (R:R, Position %, Risk/trade %)  
- Market Trend + Regime  
- News Intelligence  
- Technical Snapshot  
- Volume Analysis  
- Fibonacci  
- Pattern Recognition  

### B) Prediction History

प्रत्येक अंदाजाची ओळ: वेळ, मार्केट किंमत, Signal, Confidence, Predicted, Actual, Error%, Correct?, P/L Sim%, Accuracy.

### C) Accuracy Statistics

- Accuracy (±१%)  
- Win Rate  
- Avg Error  
- Avg Confidence  
- P/L Simulation  
- ग्राफ (जेव्हा पुरेसे evaluated असतील)

## ८.४ AI Explanation पॅनेल — कसे वाचावे

1. मोठा Signal + Confidence  
2. **Supporting evidence** — स्वीकारलेले कारणे (७–८)  
3. **Conflicting / de-emphasized** — का दुर्लक्षित  
4. **Suggested action** — नवशिक्यांसाठी सूचना  
5. **Trend + Regime**  
6. **Techniques emphasized** — कोणते टूल्स प्राधान्य  
7. **Full analyst report** — संपूर्ण markdown अहवाल  
8. **Full AI market read** — GenAI चालू असल्यास  

## ८.५ Risk Management पॅनेल

| मेट्रिक | अर्थ |
|---------|------|
| R:R | उदा. १:२.५ — जोखमीच्या तुलनेत बक्षिस |
| Position | शिफारस भांडवलाची टक्केवारी |
| Risk/trade | एका ट्रेडमध्ये जोखीम % |

खाली नोट्स: shares अंदाज, High risk चेतावणी, कमकुवत R:R इशारा.

## ८.६ News Intelligence

प्रत्येक ओळ:
`BULLISH (६५%) — headline…`

रंग: हिरवा / लाल / पिवळा.

## ८.७ Compare Prediction vs Reality

- Prediction vs Actual किंमत  
- Difference %  
- Status: Correct / Incorrect / Pending  

Pending = अजून मार्केट उलगडत आहे.

## ८.८ Alternative Scenarios

| स्तंभ | अर्थ |
|-------|------|
| Scenario | Bullish / Base / Bearish |
| Target | त्या मार्गाची किंमत |
| Probability | शक्यता % |
| Summary | एक वाक्य |

---

# अध्याय ९ — AI Predicted चार्ट: प्रत्येक तपशील

## ९.१ पायऱ्यांनी वाचन

1. **शेवटची कॅंडल** = आताची स्थिती  
2. **पिवळी जाड रेषा** = AI चा मुख्य (base) भविष्य मार्ग  
3. **हिरवी/लाल dotted** = पर्यायी bull/bear मार्ग  
4. **पिवळी अर्धपारदर्शक पट्टी** = अनिश्चितता (confidence band)  
5. **▲/▼/◆** = संकेत चिन्हे  
6. **EMA/VWAP** = ट्रेंड संदर्भ  
7. **Support/Resistance dashed** = महत्त्वाच्या पातळ्या  
8. **Fib रेषा** = pullback झोन  
9. **खालचे पॅनेल** RSI/MACD = मोमेंटम पुष्टी  

## ९.२ Predicted Price vs Target vs Stop — फरक

| फील्ड | साधारण अर्थ |
|-------|-------------|
| **Predicted Price** | मधला “waypoint” — जिथे AI लवकर पोहोचेल असे मानते |
| **Target** | पूर्ण नफा लक्ष्य (जास्त ATR multiples) |
| **Stop Loss** | चुकल्यास बाहेर |
| **Range low–high** | अपेक्षित पट्टी / band |

## ९.३ Signal = HOLD असताना चार्ट

- रेषा जवळपास सपाट/अल्प हालचाल  
- Target/Stop जवळ (±०.६ ATR)  
- Position size कमी  

## ९.४ Regime = volatile असताना

- Stop दूर (१.६×ATR)  
- Risk High शक्य  
- VWAP/ATR जास्त महत्त्व  

## ९.५ चार्टवर “योग्य” वाचन चेकलिस्ट

- [ ] Signal व पिवळ्या रेषेची दिशा जुळते का?  
- [ ] Volume surge सोबत ब्रेकआउट आहे का?  
- [ ] News tilt Signal ला विरोध करतो का? (Conflict expander पाहा)  
- [ ] R:R ≥ ~१.२ आहे का?  
- [ ] Risk High असेल तर साइज कमी ठेवा  

---

# अध्याय १० — इतिहास, अचूकता, शिकणे

## १०.१ स्टोरेज

फाइल: `data/storage/predictions.json`  
कमाल सुमारे **२०००** नोंदी.

प्रत्येक नोंदीत: timestamp (IST), signal, confidence, predicted/target/stop, projection points, accuracy_label…

## १०.२ मूल्यांकन नियम (सुमारे ५ मिनिटांनंतर)

| Signal | “Win” कधी? |
|--------|------------|
| BUY | actual ≥ predicted × ०.९९ |
| SELL | actual ≤ predicted × १.०१ |
| HOLD | error_pct ≤ १.० |

**Accuracy labels:**
- Accurate (±१%) — error ≤ १%  
- Direction correct — दिशा बरोबर पण error जास्त  
- Incorrect — चुकीचे  

## १०.३ Accuracy Statistics मेट्रिक्स

| मेट्रिक | अर्थ |
|---------|------|
| Accuracy (±१%) | किंमत जवळपास बरोबर |
| Win Rate | दिशा/नियमानुसार यश % |
| Avg Error | सरासरी % चूक |
| Avg Confidence | सरासरी विश्वास |
| P/L Simulation | साधे +१/−१ सिम्युलेशन |

## १०.४ Learning Agent कसे वापरते

- Win rate ≥ ६०% → थोडे trend विश्वास  
- Win rate ≤ ४०% → volume/S&R/news वाढव, trend कमी  
- Avg error जास्त → macro सावधगिरी  
- खूप BUY skew → momentum confirmation वाढ  

---

# अध्याय ११ — Gen AI मोड

## ११.१ कधी चालते?

साइडबार: **Use Gen AI (requires API key)** = ON  
आणि `OPENAI_API_KEY` किंवा `config/local.json` मध्ये की.

## ११.२ काय होते?

1. Analyst आधी निर्णय देतो  
2. LLM ला brief + indicators + headlines पाठवले  
3. JSON उत्तर: signal, confidence, prices, market_read, reasoning…  

## ११.३ Merge नियम

- जर `|GenAI.confidence − Analyst.confidence| < २५`  
  → GenAI शी blend (signal/prices/reasons)  
  → source = `ANALYST+GENAI`  
- अन्यथा Analyst ठेव; GenAI `genai_alternative` मध्ये  
- UI मध्ये **Full AI market read** दिसू शकते  

## ११.४ मॉडेल सेटिंग्ज (साधारण)

- Default model: `gpt-4o-mini`  
- Temperature ~ ०.४५  
- Max tokens ~ २८००  

**की नसेल:** साइडबार warning; GenAI कॉल होणार नाही.

---

# अध्याय १२ — सेटिंग्ज, API, चालवणे

## १२.१ Config क्रम

1. `config/defaults.json`  
2. `config/local.json` (merge)  
3. Env: `OPENAI_API_KEY`, `TRADING_LLM_PROVIDER`, …  

उदाहरण: `config/local.example.json` कॉपी करून `local.json` बनवा.

## १२.२ Dependencies

`requirements.txt`:
- streamlit, pandas, numpy, plotly  
- yfinance, ta  
- openai  
- pandas-market-calendars  

## १२.३ रन (Windows)

```powershell
cd d:\Projects\ai_trading_app
.\venv\Scripts\python.exe -m streamlit run app.py
```

Local: http://localhost:8501  
Network: तुमच्या LAN IP वर (मोबाइल त्याच Wi‑Fi वर असल्यास).

## १२.४ GitHub Desktop / मोबाइल

कोड commit झाल्यानंतर GitHub Desktop मधून **Push** करा.  
मोबाइलवर GitHub अॅप/ब्राउझरने कोड/docs पाहा.  
Streamlit मोबाइलवर चालवायचे असेल तर PC चालू ठेवा किंवा क्लाउड होस्ट करा.

---

# अध्याय १३ — कोड वाचण्याचा व्यावहारिक डेमो

## १३.१ “Signal कुठून आला?” शोधण्यासाठी

1. `analyst/pipeline.py` → `decide_from_factors`  
2. `analyst/decision_engine.py` → `build_evidence_factors`  
3. UI मध्ये Supporting evidence = `primary.reasons`  
4. Rejected = `primary.raw["rejected_signals"]`  
5. Weights = `primary.raw["weights"]`  
6. Trace = `primary.raw["agent_trace"]`  

## १३.२ “Stop Loss कुठून?” 

`analyst/risk.py` → `build_risk_plan`  
ATR multiples + regime + signal.

## १३.३ “पिवळी रेषा कुठून?”

`analyst/scenarios.py` → base series  
→ `prediction/engine.py` projection  
→ `charts/price_chart.py` `pred_future` रंगाने draw.

## १३.४ नवीन एजंट जोडायचा असेल तर

1. `agents/__init__.py` मध्ये क्लास  
2. `analyst/` मध्ये लॉजिक फाईल  
3. `pipeline.py` मध्ये क्रमाने कॉल + `agent_trace`  
4. गरज असल्यास UI पॅनेल `ui/dashboard.py`  

---

# अध्याय १४ — सामान्य प्रश्न व चेतावण्या

## १४.१ FAQ

**प्रश्न: AI नेहमी बरोबर असते का?**  
उत्तर: नाही. Win rate / Accuracy टॅब पाहा. शैक्षणिक साधन आहे.

**प्रश्न: १m कॅंडल का आवाजदार?**  
उत्तर: छोटा interval = जास्त नॉइझ. इंट्राडेसाठी ५m/१५m बर्याचदा स्थिर.

**प्रश्न: Options/OI का दिसत नाही?**  
उत्तर: प्रोव्हायडर अजून प्लग इन नाही — Market Research मध्ये “unavailable” नोंद आहे.

**प्रश्न: HOLD म्हणजे काय करायचे?**  
उत्तर: जोरदार सेटअप नाही — वाट पहा / साइज कमी.

**प्रश्न: Auto-select indicators का?**  
उत्तर: Regime नुसार उपयुक्त overlays आपोआप दाखवते; मॅन्युअल चेकबॉक्स कायम ठेवता येतात.

## १४.२ जोखीम चेतावण्या

- पेस्ट परफॉर्मन्स ≠ भविष्य  
- बातम्या keyword-based — संदर्भ चुकीचा होऊ शकतो  
- पॅटर्न्स heuristic — १००% अचूक नाहीत  
- GenAI भ्रम (hallucination) करू शकते — Analyst सोबत तुलना करा  
- **हे आर्थिक सल्ला नाही**  

## १४.३ जलद संदर्भ कार्ड (प्रिंट करा)

| पहा | अर्थ |
|-----|------|
| पिवळी जाड रेषा | AI base prediction |
| हिरवा/लाल dotted | Alt scenarios |
| ▲ / ▼ / ◆ | BUY / SELL / HOLD |
| Score ≥ १.८ | BUY कट |
| Score ≤ −१.८ | SELL कट |
| ADX ≥ २५ | मजबूत ट्रेंड |
| VIX ≥ १८ | उच्च अस्थिरता |
| R:R | Target vs Stop गुणोत्तर |
| Agent trace | कोणत्या एजंटने काय म्हटले |

---

# परिशिष्ट अ — फाईल → जबाबदारी (त्वरित इंडेक्स)

| तुम्हाला हवे आहे | उघडा |
|------------------|------|
| UI बटणे | `app.py` |
| पॅनेल्स | `ui/dashboard.py` |
| चार्ट रंग | `charts/themes.py`, `charts/price_chart.py` |
| पूर्ण AI क्रम | `analyst/pipeline.py` |
| निर्णय गणित | `analyst/decision_engine.py` |
| वजन | `analyst/weight_engine.py` |
| जोखीम | `analyst/risk.py` |
| बातम्या | `analyst/news_impact.py` |
| Regime | `analyst/regime.py` |
| रिपोर्ट | `analyst/report.py` |
| इतिहास | `prediction/history_store.py` |
| अचूकता | `prediction/accuracy.py` |
| GenAI | `prediction/genai_engine.py`, `prediction/engine.py` |
| डिझाइन स्पेक | `Prompt.txt` |

---

# परिशिष्ट ब — शब्दकोश (मराठी ↔ इंग्रजी)

| मराठी | इंग्रजी |
|-------|---------|
| भविष्यवाणी | Prediction |
| विश्वास | Confidence |
| जोखीम | Risk |
| थांबा / तोटा मर्यादा | Stop Loss |
| नफा लक्ष्य | Target |
| आधार / प्रतिरोध | Support / Resistance |
| अस्थिरता | Volatility |
| बाजार स्थिती | Market Regime |
| वजन | Weight |
| पुरावा | Evidence / Factor |
| समन्वयक | Orchestrator |
| स्पष्टीकरणक्षम AI | Explainable AI |

---

**दस्तऐवज आवृत्ती:** Angad Agentic Assistant पूर्ण मार्गदर्शिका  
**स्थान:** `docs/Angad_Sambhurna_Marathi_Margadarshika.md`  
**प्रकल्प:** `ai_trading_app`

*— शेवट —*
