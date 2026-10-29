"""Theoretical Black-Scholes estimates. Not exchange-traded Greeks."""

from __future__ import annotations

import math
from typing import Any


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _sigma(iv: float | None) -> float | None:
    if iv is None:
        return None
    try:
        v = float(iv)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v > 2.0:  # percent quote from NSE
        v = v / 100.0
    return v


def theoretical_greeks(
    *,
    spot: float,
    strike: float,
    days_remaining: int,
    iv: float | None,
    right: str,
    rate: float = 0.06,
    ltp: float | None = None,
) -> dict[str, Any]:
    """Return labelled theoretical Greeks. Missing IV/time → unavailable fields."""
    out: dict[str, Any] = {
        "source": "black_scholes_theoretical",
        "note": "Estimates from a standard Black-Scholes formula — not live exchange Greeks and not a quote.",
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "theoretical_value": None,
        "intrinsic": None,
        "extrinsic": None,
        "unavailable": [],
    }
    call = str(right or "CE").upper() in ("CE", "CALL", "C")
    intrinsic = max(spot - strike, 0.0) if call else max(strike - spot, 0.0)
    out["intrinsic"] = round(intrinsic, 4)
    if ltp is not None:
        try:
            out["extrinsic"] = round(max(float(ltp) - intrinsic, 0.0), 4)
        except (TypeError, ValueError):
            out["unavailable"].append("extrinsic (LTP unusable)")
    sigma = _sigma(iv)
    t = max(int(days_remaining), 0) / 365.0
    if sigma is None:
        out["unavailable"].append("IV")
        return out
    if t <= 0:
        out["unavailable"].append("time_to_expiry")
        out["delta"] = 1.0 if call and spot > strike else (0.0 if call else (1.0 if strike > spot else 0.0))
        if not call and strike > spot:
            out["delta"] = -1.0
        out["theoretical_value"] = round(intrinsic, 4)
        return out
    if spot <= 0 or strike <= 0:
        out["unavailable"].append("spot/strike")
        return out
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    disc = math.exp(-rate * t)
    if call:
        value = spot * _cdf(d1) - strike * disc * _cdf(d2)
        delta = _cdf(d1)
    else:
        value = strike * disc * _cdf(-d2) - spot * _cdf(-d1)
        delta = _cdf(d1) - 1.0
    gamma = _pdf(d1) / (spot * sigma * math.sqrt(t))
    vega = spot * _pdf(d1) * math.sqrt(t) / 100.0  # per 1 vol point
    common = -spot * _pdf(d1) * sigma / (2 * math.sqrt(t))
    if call:
        theta_yr = common - rate * strike * disc * _cdf(d2)
    else:
        theta_yr = common + rate * strike * disc * _cdf(-d2)
    out["theoretical_value"] = round(value, 4)
    out["delta"] = round(delta, 4)
    out["gamma"] = round(gamma, 6)
    out["vega"] = round(vega, 4)
    out["theta"] = round(theta_yr / 365.0, 4)  # per calendar day
    return out
