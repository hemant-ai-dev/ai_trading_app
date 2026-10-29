"""Educational option recommendation from chain + underlying snapshot. Not a broker."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from options.classify import annotate_chain, moneyness_label
from utils.time_utils import IST

MODEL_VERSION = "angad-option-intel-v1"
MIN_RR = 1.5


def _num(v, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def put_call_ratio(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    c = _num(calls["open_interest"].sum()) if calls is not None and not calls.empty and "open_interest" in calls.columns else 0
    p = _num(puts["open_interest"].sum()) if puts is not None and not puts.empty and "open_interest" in puts.columns else 0
    if c <= 0:
        return None
    return round(p / c, 3)


def _delta_proxy(moneyness: str) -> float:
    return {"ITM": 0.7, "ATM": 0.5, "OTM": 0.28}.get(moneyness, 0.4)


def _liquidity_score(row: pd.Series) -> float:
    vol = _num(row.get("volume"))
    oi = _num(row.get("open_interest"))
    ltp = max(_num(row.get("ltp")), 0.01)
    spread = max(_num(row.get("spread")), 0)
    spread_pct = spread / ltp
    score = min(vol / 500.0, 3) + min(oi / 2000.0, 3) - min(spread_pct * 8, 3)
    return score


def _premium_levels(row: pd.Series, *, pred_move: float, spot: float) -> dict[str, Any]:
    ltp = max(_num(row.get("ltp")), 0.05)
    bid = _num(row.get("bid"), ltp * 0.98)
    ask = _num(row.get("ask"), ltp * 1.02)
    if bid <= 0:
        bid = ltp * 0.98
    if ask <= 0:
        ask = ltp * 1.02
    iv = _num(row.get("iv"), 0.25)
    vol_unit = max(ltp * max(iv, 0.12) * 0.35, ltp * 0.08)
    entry_low = round(min(bid, ltp) * 0.995, 2)
    entry_high = round(max(ltp, min(ask, ltp * 1.03)), 2)
    entry_mid = round((entry_low + entry_high) / 2, 2)
    stop = round(max(0.05, entry_mid - vol_unit), 2)
    t1 = round(entry_mid + vol_unit * 1.3, 2)
    t2 = round(entry_mid + vol_unit * 2.1, 2)
    risk = round(entry_mid - stop, 2)
    reward = round(t1 - entry_mid, 2)
    rr = round(reward / risk, 2) if risk > 0 else 0
    right = str(row.get("right") or "")
    money = str(row.get("moneyness") or moneyness_label(spot, float(row.get("strike") or 0), right or "CE"))
    delta = _delta_proxy(money)
    prem_move = delta * pred_move
    predicted_premium = round(max(0.05, ltp + prem_move * 0.15), 2)
    return {
        "ltp": round(ltp, 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "iv": round(iv, 4),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": stop,
        "target1": t1,
        "target2": t2,
        "target3": round(entry_mid + vol_unit * 2.8, 2),
        "risk": risk,
        "reward": reward,
        "rr": rr,
        "moneyness": money,
        "predicted_premium": predicted_premium,
        "spread_pct": (ask - bid) / ltp if ltp else 1,
        "liq": _liquidity_score(row),
    }


def rank_candidates(
    chain: pd.DataFrame,
    *,
    spot: float,
    pred_move: float,
    days_remaining: int,
    prefer_right: str | None,
) -> list[dict[str, Any]]:
    """Score contracts on liquidity, spread, OI, IV, distance — never cheap premium alone."""
    if chain is None or chain.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in chain.iterrows():
        right = str(row.get("right") or "")
        lv = _premium_levels(row, pred_move=pred_move, spot=spot)
        qualify: list[str] = []
        fail: list[str] = []
        dist = abs(_num(row.get("strike")) - spot) / spot if spot else 1
        if lv["liq"] >= 1.0:
            qualify.append(f"Liquidity score {lv['liq']:.1f} (volume + OI vs spread).")
        else:
            fail.append(f"Thin tape — liquidity score {lv['liq']:.1f}.")
        if lv["spread_pct"] <= 0.06:
            qualify.append("Bid/ask spread is usable.")
        else:
            fail.append("Bid/ask spread is wide relative to last premium.")
        if _num(row.get("open_interest")) >= 500:
            qualify.append(f"Open interest {_num(row.get('open_interest')):.0f}.")
        else:
            fail.append("Open interest is light.")
        if dist <= 0.025:
            qualify.append("Strike is near spot (ATM/near-ATM).")
        elif dist > 0.06:
            fail.append("Strike is far from spot versus the expected move.")
        if days_remaining <= 1:
            fail.append("Expiry-related theta and gap risk is elevated.")
        if lv["ltp"] < 8 and lv["liq"] < 1.5:
            fail.append("Low premium is not a reason to select this contract.")
        if lv["rr"] < MIN_RR:
            fail.append(f"Premium R:R {lv['rr']}:1 is below {MIN_RR}:1.")
        else:
            qualify.append(f"Premium R:R 1:{lv['rr']}.")
        side_ok = prefer_right is None or right == prefer_right
        if prefer_right and right != prefer_right:
            fail.append(f"Right {right} does not match the underlying bias ({prefer_right}).")
        ok = side_ok and not fail
        rows.append(
            {
                "right": right,
                "strike": float(row.get("strike") or 0),
                "contract": str(row.get("contract") or ""),
                "premium": lv["ltp"],
                "moneyness": lv["moneyness"],
                "volume": _num(row.get("volume")),
                "open_interest": _num(row.get("open_interest")),
                "oi_change": _num(row.get("oi_change")),
                "iv": lv["iv"],
                "rr": lv["rr"],
                "liq": round(lv["liq"], 2),
                "qualifies": ok,
                "why": qualify,
                "why_not": fail,
                "levels": lv,
            }
        )
    rows.sort(key=lambda r: (1 if r["qualifies"] else 0, r["liq"]), reverse=True)
    return rows[:8]


def recommend(
    *,
    underlying: str,
    spot: float,
    predicted_underlying: float,
    signal: str,
    trend: str,
    confidence: float,
    rsi: float | None,
    macd: float | None,
    atr: float | None,
    vwap: float | None,
    expiry: str,
    days_remaining: int,
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    previous_action: str | None = None,
) -> dict[str, Any]:
    """Return prediction + separate trade recommendation. Educational only."""
    sig = (signal or "HOLD").upper()
    trend_l = (trend or "").lower()
    pred_move = float(predicted_underlying) - float(spot)
    pred_pct = (pred_move / spot * 100) if spot else 0.0
    if pred_move > 0 and sig == "BUY":
        bias = "Bullish"
        want = "CE"
    elif pred_move < 0 and sig == "SELL":
        bias = "Bearish"
        want = "PE"
    elif sig == "BUY" or "up" in trend_l:
        bias = "Bullish"
        want = "CE"
    elif sig == "SELL" or "down" in trend_l:
        bias = "Bearish"
        want = "PE"
    else:
        bias = "Unclear"
        want = None

    pcr = put_call_ratio(calls, puts)
    call_prob = 50.0 + max(-35.0, min(35.0, pred_pct * 8 + ((confidence - 50) * 0.25)))
    if pcr is not None:
        call_prob += max(-8, min(8, (1.0 - pcr) * 10))
    if rsi is not None:
        call_prob += max(-6, min(6, (float(rsi) - 50) * 0.2))
    call_prob = max(8.0, min(92.0, call_prob))
    put_prob = 100.0 - call_prob
    strength = "STRONG" if abs(call_prob - 50) >= 18 and confidence >= 62 else (
        "MODERATE" if abs(call_prob - 50) >= 8 else "WEAK"
    )

    prediction = {
        "bias": bias,
        "call_probability": round(call_prob, 1),
        "put_probability": round(put_prob, 1),
        "confidence": round(float(confidence or 0), 1),
        "signal_strength": strength,
        "expected_underlying_low": round(min(spot, predicted_underlying), 2),
        "expected_underlying_high": round(max(spot, predicted_underlying), 2),
        "pcr": pcr,
        "separate_from_trade": True,
    }

    reasons: list[str] = []
    action = "NO TRADE"
    if days_remaining < 0:
        reasons.append("Selected expiry has already passed.")
    elif want is None or bias == "Unclear" or sig == "HOLD":
        action = "WAIT" if confidence >= 40 else "NO TRADE"
        reasons.append("Underlying direction is not a high-conviction BUY or SELL.")
    elif days_remaining == 0:
        action = "NO TRADE"
        reasons.append("Expiry day — theta and gap risk are elevated.")
    elif confidence < 42:
        action = "WAIT"
        reasons.append("Model confidence is too low to justify an option premium risk.")
    elif atr and spot and (atr / spot) > 0.035 and days_remaining <= 2:
        action = "WAIT"
        reasons.append("ATR is high this close to expiry.")

    chain = pd.concat(
        [annotate_chain(calls, spot), annotate_chain(puts, spot)],
        ignore_index=True,
    ) if (calls is not None or puts is not None) else pd.DataFrame()

    pick = None
    if want and not chain.empty:
        side = chain[chain["right"] == want].copy() if "right" in chain.columns else chain
        if not side.empty:
            side["liq"] = side.apply(_liquidity_score, axis=1)
            atm = side[side["moneyness"] == "ATM"]
            otm = side[side["moneyness"] == "OTM"]
            pool = pd.concat([atm, otm.head(8)], ignore_index=True) if not otm.empty else side
            pool = pool.sort_values("liq", ascending=False)
            pick = pool.iloc[0] if not pool.empty else None

    rec: dict[str, Any] = {
        "action": action,
        "contract_right": want,
        "strike": None,
        "premium": None,
        "entry_low": None,
        "entry_high": None,
        "stop": None,
        "target1": None,
        "target2": None,
        "target3": None,
        "risk": None,
        "reward": None,
        "rr": None,
        "reasons": reasons,
        "entry_why": [],
        "exit_condition": None,
        "trail_condition": None,
        "risk_level": "High",
        "contract": None,
        "expected_premium_low": None,
        "expected_premium_high": None,
        "predicted_premium": None,
    }

    if pick is not None and action != "NO TRADE":
        ltp = max(_num(pick.get("ltp")), 0.05)
        bid = _num(pick.get("bid"), ltp * 0.98)
        ask = _num(pick.get("ask"), ltp * 1.02)
        if bid <= 0:
            bid = ltp * 0.98
        if ask <= 0:
            ask = ltp * 1.02
        raw_iv = pick.get("iv")
        has_iv = raw_iv is not None and not (isinstance(raw_iv, float) and pd.isna(raw_iv))
        iv = _num(raw_iv, 0.25)
        vol_unit = max(ltp * max(iv, 0.12) * 0.35, ltp * 0.08)
        entry_low = round(min(bid, ltp) * 0.995, 2)
        entry_high = round(max(ltp, min(ask, ltp * 1.03)), 2)
        entry_mid = round((entry_low + entry_high) / 2, 2)
        stop = round(max(0.05, entry_mid - vol_unit), 2)
        t1 = round(entry_mid + vol_unit * 1.3, 2)
        t2 = round(entry_mid + vol_unit * 2.1, 2)
        t3 = round(entry_mid + vol_unit * 2.8, 2)
        risk = round(entry_mid - stop, 2)
        reward = round(t1 - entry_mid, 2)
        rr = round(reward / risk, 2) if risk > 0 else 0
        spread_pct = (ask - bid) / ltp if ltp else 1
        liq = _liquidity_score(pick)
        rec.update(
            {
                "contract_right": str(pick.get("right") or want),
                "strike": float(pick.get("strike") or 0),
                "premium": round(ltp, 2),
                "entry_low": entry_low,
                "entry_high": entry_high,
                "stop": stop,
                "target1": t1,
                "target2": t2,
                "target3": t3,
                "risk": risk,
                "reward": reward,
                "rr": rr,
                "contract": str(pick.get("contract") or ""),
                "iv": round(iv, 4),
                "volume": _num(pick.get("volume")),
                "open_interest": _num(pick.get("open_interest")),
                "spread": round(_num(pick.get("spread")), 2),
                "moneyness": str(pick.get("moneyness") or moneyness_label(spot, float(pick.get("strike") or 0), want or "CE")),
            }
        )
        rec["entry_why"] = [
            f"Premium last ₹{ltp:.2f}; entry band uses bid/ask around the last print.",
            f"Liquidity score {liq:.1f} (volume {_num(pick.get('volume')):.0f}, OI {_num(pick.get('open_interest')):.0f}).",
            f"Stop/targets sized from IV {iv:.0%} and premium volatility, not a fixed percent.",
        ]
        from options.greeks import theoretical_greeks

        rec["greeks"] = theoretical_greeks(
            spot=float(spot),
            strike=float(rec["strike"] or 0),
            days_remaining=int(days_remaining),
            iv=_num(raw_iv) if has_iv else None,
            right=str(rec.get("contract_right") or want or "CE"),
            ltp=ltp,
        )
        rec["entry_why"].append(rec["greeks"].get("note") or "Theoretical Greeks only.")
        if rec["greeks"].get("unavailable"):
            rec["entry_why"].append("Unavailable: " + ", ".join(rec["greeks"]["unavailable"]))
        delta = rec["greeks"].get("delta")
        if delta is None:
            delta = _delta_proxy(rec["moneyness"])
            rec["entry_why"].append("Delta is a moneyness proxy because Black-Scholes inputs were incomplete.")
        prem_move = float(delta) * pred_move
        rec["predicted_premium"] = round(max(0.05, ltp + prem_move * 0.15), 2)
        rec["expected_premium_low"] = round(min(ltp, rec["predicted_premium"]), 2)
        rec["expected_premium_high"] = round(max(t1, rec["predicted_premium"]), 2)

        if spread_pct > 0.08 or liq < 0.4:
            rec["action"] = "WAIT" if action != "NO TRADE" else "NO TRADE"
            rec["reasons"].append("Spread is wide or liquidity is thin — wait rather than chase.")
        elif rr < MIN_RR:
            rec["action"] = "NO TRADE"
            rec["reasons"].append(f"Risk/reward {rr}:1 is below the {MIN_RR}:1 screen.")
        elif action in ("NO TRADE", "WAIT") and (sig == "HOLD" or bias == "Unclear" or days_remaining <= 0):
            rec["action"] = action
            rec["reasons"].append("Underlying prediction exists, but a premium trade is not cleared.")
        else:
            rec["action"] = f"BUY {rec['contract_right']}"
            rec["reasons"].append(
                f"{bias} underlying bias with {rec['moneyness']} {rec['contract_right']} near ₹{rec['strike']:.0f}."
            )
            rec["exit_condition"] = f"Exit if premium trades below stop ₹{stop:.2f} or underlying thesis flips."
            rec["trail_condition"] = f"After target 1 (₹{t1:.2f}), trail stop toward entry."
            rec["risk_level"] = "High" if days_remaining <= 5 or iv > 0.45 else "Medium"

        if previous_action:
            prev = previous_action.upper()
            now_act = rec["action"]
            if prev.startswith("BUY") and now_act in ("NO TRADE", "WAIT"):
                rec["action"] = "EXIT"
                rec["reasons"].append("Setup no longer clears liquidity or R:R screens.")
            elif prev.startswith("BUY") and now_act.startswith("BUY"):
                rec["action"] = "HOLD"
                rec["reasons"].append("Same side still qualifies — hold rather than re-enter.")

    if rec["action"] in ("NO TRADE", "WAIT") and not rec["reasons"]:
        rec["reasons"].append("Wait for confirmation in trend, liquidity, and risk/reward together.")

    wait_level = round(spot + (atr or spot * 0.004) * (0.4 if bias == "Bullish" else -0.4), 2)
    if rec["action"] in ("WAIT", "NO TRADE"):
        rec["wait_text"] = (
            f"NO ENTRY NOW. Wait for confirmation {'above' if bias != 'Bearish' else 'below'} ₹{wait_level:,.2f}."
        )

    rec["prediction"] = prediction
    rec["underlying"] = underlying
    rec["expiry"] = expiry
    rec["spot"] = round(float(spot), 2)
    rec["predicted_underlying"] = round(float(predicted_underlying), 2)
    rec["model_version"] = MODEL_VERSION
    rec["as_of"] = datetime.now(IST).isoformat()
    rec["days_remaining"] = days_remaining
    return rec


def display_chain(df: pd.DataFrame, spot: float, limit: int = 21) -> pd.DataFrame:
    tagged = annotate_chain(df, spot)
    if tagged.empty:
        return tagged
    tagged = tagged.copy()
    tagged["atm_rank"] = (tagged["strike"] - float(spot)).abs()
    mid = tagged.sort_values("atm_rank").head(limit).sort_values("strike")
    cols = [
        "moneyness",
        "strike",
        "ltp",
        "bid",
        "ask",
        "volume",
        "open_interest",
        "oi_change",
        "iv",
        "last_traded",
        "change",
        "pct_change",
        "spread",
    ]
    use = [c for c in cols if c in mid.columns]
    return mid[use]
