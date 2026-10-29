"""Option chain fetch: NSE India first, Yahoo Finance fallback."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from data.cache import APP_CACHE
from options import nse
from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)

_INDEX_CANDIDATES = {
    "^NSEI": ("^NSEI", "NIFTY"),
    "^NSEBANK": ("^NSEBANK", "BANKNIFTY"),
    "^BSESN": ("^BSESN",),
}


def yahoo_option_tickers(symbol: str) -> list[str]:
    sym = (symbol or "").strip()
    if sym in _INDEX_CANDIDATES:
        return list(_INDEX_CANDIDATES[sym])
    out = [sym]
    if sym.endswith(".NS"):
        out.append(sym[:-3])
    elif "." not in sym:
        out.append(f"{sym}.NS")
    return list(dict.fromkeys(out))


def list_expiries(symbol: str) -> tuple[str, list[str]]:
    """Return (resolved_id, expiry ISO dates)."""
    cache_key = f"opt-exp|{symbol}"

    def _fetch() -> tuple[str, list[str]]:
        pair = nse.nse_pair(symbol)
        if pair:
            nse_sym, _kind = pair
            try:
                info = nse.fetch_contract_info(nse_sym)
                labels = [str(x) for x in (info.get("expiryDates") or []) if x]
                isos = [nse.iso_from_nse_expiry(x) for x in labels]
                isos = [x for x in isos if len(x) == 10]
                if isos:
                    return f"NSE:{nse_sym}", isos
            except Exception as exc:
                logger.warning("NSE expiries failed for %s: %s", nse_sym, exc)
        return _yahoo_expiries(symbol)

    return APP_CACHE.get_or_set(cache_key, 120, _fetch)


def _yahoo_expiries(symbol: str) -> tuple[str, list[str]]:
    import yfinance as yf

    last_err = ""
    for ticker in yahoo_option_tickers(symbol):
        try:
            tk = yf.Ticker(ticker)
            exps = list(tk.options or [])
            if exps:
                return ticker, [str(x) for x in exps]
        except Exception as exc:
            last_err = str(exc)
            logger.warning("Yahoo option expiries failed for %s: %s", ticker, exc)
    if last_err:
        logger.warning("No option expiries: %s", last_err[:180])
    return "", []


def fetch_chain(symbol: str, expiry: str) -> dict[str, Any]:
    cache_key = f"opt-chain|{symbol}|{expiry}"

    def _fetch() -> dict[str, Any]:
        payload = {
            "ticker": "",
            "expiry": expiry,
            "expiries": [],
            "calls": pd.DataFrame(),
            "puts": pd.DataFrame(),
            "spot": None,
            "source": "",
            "note": "",
        }
        pair = nse.nse_pair(symbol)
        if pair and expiry:
            nse_sym, kind = pair
            try:
                label = nse.nse_expiry_label(expiry) if len(str(expiry)) >= 10 and expiry[4] == "-" else str(expiry)
                raw = nse.fetch_chain_payload(nse_sym, kind, label)
                calls_rows, puts_rows, spot = nse.parse_sides(raw)
                payload["ticker"] = f"NSE:{nse_sym}"
                payload["source"] = "nseindia"
                payload["spot"] = spot
                payload["calls"] = pd.DataFrame(calls_rows)
                payload["puts"] = pd.DataFrame(puts_rows)
                rec = (raw or {}).get("records") or {}
                labels = rec.get("expiryDates") or []
                payload["expiries"] = [nse.iso_from_nse_expiry(str(x)) for x in labels]
                if payload["calls"].empty and payload["puts"].empty:
                    payload["note"] = "NSE returned no contracts for this expiry."
                else:
                    return payload
            except Exception as exc:
                logger.warning("NSE option chain failed for %s %s: %s", nse_sym, expiry, exc)
                payload["note"] = f"NSE chain error: {exc}"
        yahoo = _yahoo_chain(symbol, expiry)
        if yahoo["calls"].empty and yahoo["puts"].empty:
            prior = payload.get("note") if pair else ""
            yahoo["note"] = yahoo.get("note") or (
                "Option-chain data is currently unavailable. Please try again."
            )
            if prior:
                yahoo["note"] = f"{prior} {yahoo['note']}"
        elif payload.get("note") and not yahoo.get("note"):
            yahoo["note"] = str(payload["note"])
        return yahoo

    return APP_CACHE.get_or_set(cache_key, 45, _fetch)


def _yahoo_chain(symbol: str, expiry: str) -> dict[str, Any]:
    import yfinance as yf

    resolved, exps = _yahoo_expiries(symbol)
    payload = {
        "ticker": resolved,
        "expiry": expiry,
        "expiries": exps,
        "calls": pd.DataFrame(),
        "puts": pd.DataFrame(),
        "spot": None,
        "source": "yahoo",
        "note": "",
    }
    if not resolved or expiry not in exps:
        payload["note"] = "Option-chain data is currently unavailable. Please try again."
        return payload
    try:
        chain = yf.Ticker(resolved).option_chain(expiry)
        payload["calls"] = _normalize_yahoo(getattr(chain, "calls", None), "CE")
        payload["puts"] = _normalize_yahoo(getattr(chain, "puts", None), "PE")
        if payload["calls"].empty and payload["puts"].empty:
            payload["note"] = "Option-chain data is currently unavailable. Please try again."
    except Exception as exc:
        payload["note"] = "Option-chain data is currently unavailable. Please try again."
        logger.warning("Yahoo option chain failed: %s", exc)
    return payload


def _normalize_yahoo(df: pd.DataFrame | None, right: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    rename = {
        "lastPrice": "ltp",
        "openInterest": "open_interest",
        "impliedVolatility": "iv",
        "lastTradeDate": "last_traded",
        "percentChange": "pct_change",
        "contractSymbol": "contract",
        "inTheMoney": "in_the_money",
    }
    for src, dst in rename.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    out["right"] = right
    if "oi_change" not in out.columns:
        out["oi_change"] = pd.NA
    if "spread" not in out.columns:
        bid = pd.to_numeric(out.get("bid"), errors="coerce")
        ask = pd.to_numeric(out.get("ask"), errors="coerce")
        out["spread"] = ask - bid
    if "iv" in out.columns:
        iv = pd.to_numeric(out["iv"], errors="coerce")
        out["iv"] = iv.where(iv > 2, iv * 100)
    keep = [
        "contract",
        "right",
        "strike",
        "ltp",
        "bid",
        "ask",
        "spread",
        "volume",
        "open_interest",
        "oi_change",
        "iv",
        "last_traded",
        "change",
        "pct_change",
        "in_the_money",
    ]
    cols = [c for c in keep if c in out.columns]
    return out[cols].sort_values("strike") if cols else out


def expiry_meta(expiry_iso: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(IST)
    try:
        exp = date.fromisoformat(str(expiry_iso)[:10])
    except ValueError:
        return {"expiry": expiry_iso, "valid": False}
    today = now.date()
    remaining = (exp - today).days
    weekday = exp.strftime("%A")
    if remaining < 0:
        status = "EXPIRED"
    elif remaining == 0:
        status = "EXPIRY DAY"
    else:
        status = "ACTIVE"
    return {
        "expiry": exp.isoformat(),
        "expiry_day": weekday,
        "days_remaining": remaining,
        "status": status,
        "is_expiry_day": remaining == 0,
        "expired": remaining < 0,
        "as_of": today.isoformat(),
        "valid": True,
    }
