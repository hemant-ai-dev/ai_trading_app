"""NSE India option-chain client (unofficial public website JSON)."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.cookiejar import CookieJar
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_INDEX = {
    "^NSEI": "NIFTY",
    "NIFTY": "NIFTY",
    "^NSEBANK": "BANKNIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "MIDCPNIFTY": "MIDCPNIFTY",
    "NIFTYNXT50": "NIFTYNXT50",
}

_jar = CookieJar()
_opener: urllib.request.OpenerDirector | None = None
_warmed_at = 0.0


def nse_pair(symbol: str) -> tuple[str, str] | None:
    """Return (NSE symbol, type Indices|Equity) or None if we should not hit NSE."""
    raw = (symbol or "").strip().upper()
    if not raw or raw in ("^BSESN", "SENSEX"):
        return None
    if raw in _INDEX:
        return _INDEX[raw], "Indices"
    name = raw[:-3] if raw.endswith(".NS") else raw
    name = name.replace("^", "")
    if name in _INDEX.values():
        return name, "Indices"
    if not name or any(ch.isdigit() for ch in name[:1]):
        return None
    return name, "Equity"


def nse_expiry_label(iso: str) -> str:
    dt = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def iso_from_nse_expiry(label: str) -> str:
    text = str(label or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def _opener_obj() -> urllib.request.OpenerDirector:
    global _opener
    if _opener is None:
        ctx = ssl.create_default_context()
        _opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(_jar),
            urllib.request.HTTPSHandler(context=ctx),
        )
    return _opener


def _headers(accept: str = "application/json, text/plain, */*") -> dict[str, str]:
    return {
        "User-Agent": _UA,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain",
        "Connection": "keep-alive",
    }


def _warm() -> None:
    global _warmed_at
    now = time.time()
    if now - _warmed_at < 480:
        return
    req = urllib.request.Request(
        "https://www.nseindia.com/option-chain",
        headers=_headers("text/html,application/xhtml+xml"),
    )
    _opener_obj().open(req, timeout=18).read(64)
    _warmed_at = now


def _get_json(url: str) -> dict[str, Any]:
    _warm()
    req = urllib.request.Request(url, headers=_headers())
    with _opener_obj().open(req, timeout=22) as resp:
        raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8", "replace"))


def fetch_contract_info(nse_symbol: str) -> dict[str, Any]:
    q = urllib.parse.quote(nse_symbol)
    return _get_json(f"https://www.nseindia.com/api/option-chain-contract-info?symbol={q}")


def fetch_chain_payload(nse_symbol: str, kind: str, expiry_label: str) -> dict[str, Any]:
    global _warmed_at
    q = urllib.parse.quote(nse_symbol)
    exp = urllib.parse.quote(expiry_label)
    kind = "Indices" if kind == "Indices" else "Equity"
    url = f"https://www.nseindia.com/api/option-chain-v3?type={kind}&symbol={q}&expiry={exp}"
    try:
        return _get_json(url)
    except urllib.error.HTTPError:
        _warmed_at = 0.0
        return _get_json(url)


def parse_sides(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float | None]:
    records = (payload or {}).get("records") or {}
    spot = records.get("underlyingValue")
    try:
        spot_f = float(spot) if spot not in (None, "", 0) else None
    except (TypeError, ValueError):
        spot_f = None
    calls: list[dict[str, Any]] = []
    puts: list[dict[str, Any]] = []
    for row in records.get("data") or []:
        strike = row.get("strikePrice")
        if row.get("CE"):
            calls.append(_leg(row["CE"], "CE", strike))
        if row.get("PE"):
            puts.append(_leg(row["PE"], "PE", strike))
    return calls, puts, spot_f


def _leg(leg: dict[str, Any], right: str, strike: Any) -> dict[str, Any]:
    bid = _num(leg.get("buyPrice1"))
    ask = _num(leg.get("sellPrice1"))
    spread = None
    if bid is not None and ask is not None:
        spread = round(ask - bid, 4)
    return {
        "contract": leg.get("identifier"),
        "right": right,
        "strike": _num(strike if strike is not None else leg.get("strikePrice")),
        "ltp": _num(leg.get("lastPrice")),
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "volume": _num(leg.get("totalTradedVolume")),
        "open_interest": _num(leg.get("openInterest")),
        "oi_change": _num(leg.get("changeinOpenInterest")),
        "iv": _num(leg.get("impliedVolatility")),
        "last_traded": None,
        "change": _num(leg.get("change")),
        "pct_change": _num(leg.get("pChange") if leg.get("pChange") is not None else leg.get("PChange")),
        "in_the_money": None,
    }


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
