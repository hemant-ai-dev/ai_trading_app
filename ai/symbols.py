"""Resolve Indian index/stock names from chat text. Avoid English words as tickers."""

from __future__ import annotations

import difflib
import re

ALIASES = {
    "NIF50": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTYFIFTY": "^NSEI",
    "NIFTY": "^NSEI",
    "NSEI": "^NSEI",
    "^NSEI": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "NIFTYBANK": "^NSEBANK",
    "^NSEBANK": "^NSEBANK",
    "SENSEX": "^BSESN",
    "^BSESN": "^BSESN",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATAMOTOR": "TATAMOTORS.NS",
    "RELIANCE": "RELIANCE.NS",
    "INFY": "INFY.NS",
    "INFOSYS": "INFY.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "WIPRO": "WIPRO.NS",
    "ITC": "ITC.NS",
    "SBIN": "SBIN.NS",
    "MARUTI": "MARUTI.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "BHEL": "BHEL.NS",
    "ONGC": "ONGC.NS",
    "NTPC": "NTPC.NS",
    "POWERGRID": "POWERGRID.NS",
    "COALINDIA": "COALINDIA.NS",
    "LT": "LT.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
}

STOPWORDS = {
    "BUY", "SELL", "HOLD", "RSI", "MACD", "ATR", "EMA", "VWAP", "API", "AI",
    "TELL", "ABOUT", "THE", "STOCK", "INDEX", "MARKET", "PRICE", "QUOTE",
    "WHAT", "WHEN", "WHERE", "WHICH", "THIS", "THAT", "FROM", "WITH", "HAVE",
    "PLEASE", "GIVE", "SHOW", "ANALYZE", "ANALYSIS", "OUTLOOK", "TODAY",
    "DAILY", "HISTORY", "RISK", "NEWS", "WHY", "HOW", "CAN", "YOU", "FOR",
    "AND", "ARE", "IS", "ME", "MY", "OUR", "ANY", "ALL", "NOT", "NOW",
    "ENVIRONMENT", "CLIMATE", "ESG", "SHARE", "SHARES", "DETAILS", "DETAIL",
    "COMPANY", "INFO", "INFORMATION", "HELLO", "HI", "COULD", "WOULD",
    "SHOULD", "LAST", "DAYS", "DAY", "WEEK", "MONTH", "YEAR", "MOVEMENT",
    "MOVE", "CHART", "TREND", "JUST", "LIKE", "SOME", "MORE", "THAN",
    "THEN", "BEEN", "WERE", "WAS", "WILL", "YOUR", "THERE", "HERE",
    "DOES", "DID", "DONT", "DONT", "INTO", "OVER", "UNDER", "AFTER",
    "BEFORE", "BETWEEN", "ALSO", "ONLY", "VERY", "MUCH", "MANY",
}

_TICKER = re.compile(r"\b(\^[A-Z0-9]{2,12}|[A-Z]{2,15}(?:\.[A-Z]{1,4})?)\b")
_COMPACT = re.compile(r"[^A-Z0-9^]+")
_TYPED_CAPS = re.compile(r"\b[A-Z]{2,12}(?:\.[A-Z]{1,4})?\b")


def compact_key(text: str) -> str:
    return _COMPACT.sub("", (text or "").upper())


def _fuzzy_alias_token(token: str) -> str | None:
    token = compact_key(token)
    if len(token) < 4:
        return None
    best: tuple[float, str] | None = None
    for name, ticker in ALIASES.items():
        key = compact_key(name)
        if len(key) < 4:
            continue
        ratio = difflib.SequenceMatcher(None, token, key).ratio()
        if token in key or key in token:
            ratio = max(ratio, 0.88)
        if ratio >= 0.74 and (best is None or ratio > best[0]):
            best = (ratio, ticker)
    return best[1] if best else None


def detect_symbol(text: str) -> str | None:
    raw = text or ""
    compact = compact_key(raw)

    for blob in re.findall(r"[A-Z]*N[A-Z]{0,4}F[A-Z]{0,4}T[A-Z]{0,4}Y?[A-Z]*50", compact):
        if difflib.SequenceMatcher(None, blob, "NIFTY50").ratio() >= 0.72:
            return "^NSEI"
        if "NIF" in blob or "FTY" in blob or "IFTY" in blob:
            return "^NSEI"

    for name in sorted(ALIASES, key=len, reverse=True):
        key = compact_key(name)
        if len(key) < 4:
            continue
        if key and key in compact:
            return ALIASES[name]

    for token in re.findall(r"[A-Za-z]{3,15}50|[A-Za-z]{4,15}", raw):
        hit = _fuzzy_alias_token(token)
        if hit:
            return hit

    for token in _TICKER.findall(raw.upper()):
        if token in STOPWORDS:
            continue
        if token in ALIASES:
            return ALIASES[token]
        if token.startswith("^") or "." in token:
            return token
        fuzzy = _fuzzy_alias_token(token)
        if fuzzy:
            return fuzzy
        if token in STOPWORDS:
            continue
        # Only treat ALL-CAPS typed codes (BHEL) as tickers, never "could"/"last".
        if token.isalpha() and 3 <= len(token) <= 12 and token in _TYPED_CAPS.findall(raw):
            return f"{token}.NS"
    return None


def infer_symbol(text: str, default: str | None = None) -> str:
    found = detect_symbol(text)
    if found:
        return found
    fallback = (default or "").strip().upper()
    return fallback or "^NSEI"
