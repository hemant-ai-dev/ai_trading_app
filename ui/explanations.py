"""Detailed English + Marathi narratives when Gen AI is off (rule-based)."""

from __future__ import annotations

from ui.bilingual import REGIME_MR, SIGNAL_GUIDE


def build_rule_narrative_en(signal: str, rule: dict, logic_snap: dict) -> str:
    ind = logic_snap.get("indicators") or {}
    ohlcv = logic_snap.get("ohlcv_last") or {}
    close = ohlcv.get("close", 0)
    rsi = ind.get("rsi", 50)
    ema9 = ind.get("ema9", close)
    ema20 = ind.get("ema20", close)
    vwap = ind.get("vwap", close)
    atr = ind.get("atr", 0)
    regime = rule.get("market_regime", "mixed")
    score = rule.get("score", 0)
    conf = rule.get("confidence", 0)
    target = rule.get("target", close)
    stop = rule.get("stop_loss", close)

    base = SIGNAL_GUIDE.get(signal.upper(), SIGNAL_GUIDE["HOLD"])["en"]
    return f"""{base}

**Detailed read on this bar**
- Last close **₹{close:,.2f}** vs VWAP **₹{vwap:,.2f}** — {"above fair value" if close > vwap else "at or below fair value"} for this window.
- **EMA9 {ema9:,.2f}** vs **EMA20 {ema20:,.2f}** — {"short-term above medium-term (bullish structure)" if ema9 > ema20 else "short-term below medium-term (bearish structure)"}.
- **RSI {rsi:.1f}** — {"strong momentum zone" if rsi >= 60 else "weak momentum zone" if rsi <= 40 else "neutral/mixed momentum"}.
- **ATR {atr:,.2f}** sets the risk band; target **₹{target:,.2f}** and stop **₹{stop:,.2f}** are ATR-scaled references, not guaranteed fills.
- **Weighted score {score}** → label **{signal}** with **{conf}%** confidence. Regime tag: **{regime}** ({REGIME_MR.get(regime, regime)}).
- **Factors:** {rule.get("reason", "—")}

**What you should do as monitor (not advice):** Wait for price to confirm direction vs VWAP and EMA stack before treating this as actionable. Compare the red prediction line to live price over time — SQL stores each run for accuracy."""



def build_rule_narrative_mr(signal: str, rule: dict, logic_snap: dict) -> str:
    ind = logic_snap.get("indicators") or {}
    ohlcv = logic_snap.get("ohlcv_last") or {}
    close = ohlcv.get("close", 0)
    rsi = ind.get("rsi", 50)
    ema9 = ind.get("ema9", close)
    ema20 = ind.get("ema20", close)
    vwap = ind.get("vwap", close)
    atr = ind.get("atr", 0)
    regime = rule.get("market_regime", "mixed")
    score = rule.get("score", 0)
    conf = rule.get("confidence", 0)
    target = rule.get("target", close)
    stop = rule.get("stop_loss", close)

    base = SIGNAL_GUIDE.get(signal.upper(), SIGNAL_GUIDE["HOLD"])["mr"]
    return f"""{base}

**या बारवर सविस्तर वाचन**
- शेवटची किंमत **₹{close:,.2f}** वि VWAP **₹{vwap:,.2f}** — या विंडोसाठी {"वरच्या बाजूने" if close > vwap else "खाली/समान"}.
- **EMA9 {ema9:,.2f}** वि **EMA20 {ema20:,.2f}** — {"लघुकालीन वर (बुलिश)" if ema9 > ema20 else "लघुकालीन खाली (बेअरिश)"}.
- **RSI {rsi:.1f}** — {"मजबूत" if rsi >= 60 else "कमकुवत" if rsi <= 40 else "मिश्र/तटस्थ"}.
- **ATR {atr:,.2f}** — जोखीम बँड; लक्ष्य **₹{target:,.2f}**, स्टॉप **₹{stop:,.2f}** (हमी नाही).
- **स्कोअर {score}** → **{signal}**, विश्वास **{conf}%**. रेजीम: **{REGIME_MR.get(regime, regime)}**.
- **घटक:** {rule.get("reason", "—")}

**निरीक्षक म्हणून:** VWAP आणि EMA पुष्टी होईपर्यंत प्रतीक्षा करा. लाल अंदाज रेषा व लाइव्ह किंमत SQL मध्ये तुलना करा."""
