"""ATM / ITM / OTM labels from spot vs strike."""

from __future__ import annotations

import pandas as pd


def moneyness_label(spot: float, strike: float, right: str, atm_pct: float = 0.004) -> str:
    if not spot or not strike:
        return "—"
    dist = abs(float(strike) - float(spot)) / float(spot)
    if dist <= atm_pct:
        return "ATM"
    is_call = str(right).upper() in ("CE", "C", "CALL")
    if is_call:
        return "ITM" if strike < spot else "OTM"
    return "ITM" if strike > spot else "OTM"


def annotate_chain(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["moneyness"] = [
        moneyness_label(spot, float(row.get("strike") or 0), str(row.get("right") or ""))
        for _, row in out.iterrows()
    ]
    out["distance_pct"] = ((out["strike"] - float(spot)) / float(spot) * 100).round(3)
    return out
