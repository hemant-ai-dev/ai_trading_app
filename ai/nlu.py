"""Understand messy user questions: typos, slang, Hinglish, missing tickers."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from ai.symbols import ALIASES, compact_key, detect_symbol

# Informal spellings and Hinglish → something the tools can use.
_REPLACEMENTS = [
    (r"\bplz\b", "please"),
    (r"\bpls\b", "please"),
    (r"\bwht\b", "what"),
    (r"\bwat\b", "what"),
    (r"\bwht's\b", "what is"),
    (r"\bkya\s*hai\b", "what is"),
    (r"\bkya\b", "what"),
    (r"\bkitna\b", "price"),
    (r"\brate\b", "price"),
    (r"\bka\s*bhav\b", "price"),
    (r"\bbhav\b", "price"),
    (r"\bbatao\b", "tell me about"),
    (r"\bbtao\b", "tell me about"),
    (r"\bbta\s*do\b", "tell me about"),
    (r"\btel\s+me\b", "tell me"),
    (r"\btellme\b", "tell me"),
    (r"\babt\b", "about"),
    (r"\babut\b", "about"),
    (r"\banalise\b", "analyze"),
    (r"\banalize\b", "analyze"),
    (r"\banalys\b", "analyze"),
    (r"\boutlok\b", "outlook"),
    (r"\bout look\b", "outlook"),
    (r"\bpredction\b", "prediction"),
    (r"\bpredicition\b", "prediction"),
    (r"\benviroment\b", "environment"),
    (r"\benvironmental\b", "environment"),
    (r"\bclimte\b", "climate"),
    (r"\bnoifty\s*50\b", "nifty50"),
    (r"\bnfifty\s*50\b", "nifty50"),
    (r"\bnifty\s*50\b", "nifty50"),
    (r"\blast\s+\d+\s+days?\b", "history last days movement"),
    (r"\bnifti\b", "nifty"),
    (r"\bnifti50\b", "nifty50"),
    (r"\bniffty\b", "nifty"),
    (r"\bnif ty\b", "nifty"),
    (r"\bnifty5\b", "nifty50"),
    (r"\bnse\s*index\b", "nifty50"),
    (r"\bindian\s+market\b", "nifty50"),
    (r"\bshare\s+bazar\b", "nifty50"),
    (r"\bsharebazar\b", "nifty50"),
    (r"\bbank\s*nifty\b", "banknifty"),
    (r"\bbnifty\b", "banknifty"),
    (r"\bsensx\b", "sensex"),
    (r"\bsens ex\b", "sensex"),
    (r"\bbhel\b", "bhel"),
    (r"\btata\s*motor[s]?\b", "tatamotors"),
    (r"\bttmt\b", "tatamotors"),
    (r"\brelaince\b", "reliance"),
    (r"\brelience\b", "reliance"),
    (r"\bril\b", "reliance"),
    (r"\binfosys\b", "infy"),
    (r"\binfosis\b", "infy"),
    (r"\bhdfc\s*bank\b", "hdfcbank"),
    (r"\bshould\s+i\s+buy\b", "analyze buy"),
    (r"\bbuy\s+or\s+sell\b", "analyze"),
    (r"\bkaisa\s*hai\b", "outlook"),
    (r"\bkaisa\b", "outlook"),
    (r"\bnext\s*day\b", "outlook"),
    (r"\bnxt\s*day\b", "outlook"),
    (r"\btomorrow\b", "outlook"),
    (r"\benvrmnt\b", "environment"),
    (r"\besg\s*risk\b", "environment esg"),
]

_PHRASES: list[tuple[str, str]] = [
    ("TATAMOTORS", "TATAMOTORS.NS"),
    ("BANKNIFTY", "^NSEBANK"),
    ("NIFTY50", "^NSEI"),
    ("NIF50", "^NSEI"),
    ("NIFTY", "^NSEI"),
    ("SENSEX", "^BSESN"),
    ("RELIANCE", "RELIANCE.NS"),
    ("INFOSYS", "INFY.NS"),
    ("HDFCBANK", "HDFCBANK.NS"),
    ("ICICIBANK", "ICICIBANK.NS"),
]

_INTENT_WORDS: dict[str, tuple[str, ...]] = {
    "quote": ("price", "quote", "ltp", "close", "rate", "bhav", "kitna", "value", "trading"),
    "analysis": ("analyze", "analyse", "analysis", "outlook", "view", "kaisa", "signal", "hold", "buy", "sell", "target", "stop", "about", "tell"),
    "news": ("news", "headline", "sentiment"),
    "history": ("history", "previous", "changed", "accuracy", "prediction", "movement", "days", "week"),
    "risk": ("risk", "stoploss", "stop", "danger"),
    "environment": ("environment", "climate", "esg", "carbon", "pollution", "green", "sustainab", "weather"),
    "app": ("swagger", "excel", "password", "login", "api", "streamlit", "stored", "username"),
    "task": ("monitor", "notify", "prepare", "worker"),
}

_FOLLOW_UP = re.compile(
    r"\b(and\s+this|same|uska|iska|uska\s+kya|what\s+about\s+(it|this)|price\s*\??$|aur\s*\??$|now\??$)\b",
    re.I,
)


@dataclass
class Understood:
    original: str
    cleaned: str
    symbol: str
    intents: list[str] = field(default_factory=list)
    restated: str = ""
    used_previous_symbol: bool = False


def _clean(text: str) -> str:
    q = (text or "").strip().lower()
    q = q.replace("&", " and ")
    for pat, repl in _REPLACEMENTS:
        q = re.sub(pat, repl, q, flags=re.I)
    q = re.sub(r"[?!.,;:]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def _fuzzy_symbol(cleaned: str, compact: str) -> str | None:
    keys = {compact_key(k): ALIASES[k] for k in ALIASES}
    tokens = re.findall(r"[a-z0-9^]{3,}", cleaned.lower())
    compact_tokens = [compact_key(t) for t in tokens] + ([compact] if compact else [])
    alias_keys = list(keys)
    best: tuple[float, str] | None = None
    for token in compact_tokens:
        if len(token) < 3:
            continue
        for key in alias_keys:
            if len(key) < 3:
                continue
            ratio = difflib.SequenceMatcher(None, token, key).ratio()
            if token in key or key in token:
                ratio = max(ratio, 0.9)
            if ratio >= 0.78 and (best is None or ratio > best[0]):
                best = (ratio, keys[key])
    if best:
        return best[1]
    for phrase, ticker in _PHRASES:
        if phrase in compact:
            return ticker
    return None


def _intents(cleaned: str) -> list[str]:
    found: list[str] = []
    words = set(re.findall(r"[a-z0-9]+", cleaned))
    for intent, needles in _INTENT_WORDS.items():
        for n in needles:
            parts = n.split()
            if all(p in cleaned for p in parts) or n in words:
                found.append(intent)
                break
            close = difflib.get_close_matches(n, list(words), n=1, cutoff=0.82)
            if close:
                found.append(intent)
                break
    if not found:
        found = ["analysis", "quote"]
    # de-dupe
    out: list[str] = []
    for item in found:
        if item not in out:
            out.append(item)
    return out


def understand(
    text: str,
    *,
    default_symbol: str | None = None,
    previous_symbol: str | None = None,
) -> Understood:
    original = (text or "").strip()
    cleaned = _clean(original)
    compact = compact_key(cleaned)
    symbol = detect_symbol(cleaned)
    used_prev = False
    if not symbol:
        symbol = _fuzzy_symbol(cleaned, compact)
    if not symbol and previous_symbol and (_FOLLOW_UP.search(original) or len(cleaned.split()) <= 4):
        symbol = previous_symbol
        used_prev = True
    if not symbol:
        symbol = (default_symbol or "^NSEI").strip().upper() or "^NSEI"
    intents = _intents(cleaned)
    pretty = {
        "^NSEI": "Nifty 50",
        "^NSEBANK": "Bank Nifty",
        "^BSESN": "Sensex",
    }.get(symbol, symbol)
    restated = f"You asked about {pretty}"
    if "environment" in intents:
        restated += " and environment/ESG context"
    if "quote" in intents:
        restated += " (daily price)"
    if "analysis" in intents:
        restated += " with analysis"
    restated += "."
    return Understood(
        original=original,
        cleaned=cleaned,
        symbol=symbol,
        intents=intents,
        restated=restated,
        used_previous_symbol=used_prev,
    )


def last_chat_symbol(messages: list[dict[str, Any]]) -> str | None:
    for msg in reversed(messages or []):
        sym = (msg.get("Symbol") or "").strip()
        if sym:
            return sym.upper()
    return None
