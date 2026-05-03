"""Deterministic reference levels from last bar + signal (education only — not advice)."""

from __future__ import annotations

from typing import Any

# Maps each tag emitted by signal_engine to a plain-language explanation.
FACTOR_HELP: dict[str, str] = {
    "EMA Bullish": (
        "The **9-period EMA** sits **above** the **20-period EMA**. "
        "This rule treats that as *short-term trend above medium-term* — a simple uptrend filter (not a guarantee of future direction)."
    ),
    "EMA Bearish": (
        "The **9-period EMA** sits **below** the **20-period EMA**. "
        "Short-term average below medium-term → the scorecard leans toward weakness until structure improves."
    ),
    "RSI Strong": (
        "**RSI** is **above 55** on the loaded window. "
        "The engine reads that as stronger momentum in the lookback; very high RSI can also mean stretched conditions."
    ),
    "RSI Weak": (
        "**RSI** is **below 45** → softer momentum in the lookback; often paired with caution or mean-reversion context depending on price structure."
    ),
    "MACD Positive": (
        "The **MACD line** is **above zero** on this interval → typical reading is momentum favoring the upside versus the signal/zero line (still interval-sensitive)."
    ),
    "MACD Negative": (
        "The **MACD line** is **at or below zero** → momentum oscillator not supporting the bullish side in this bar’s snapshot."
    ),
    "Above VWAP": (
        "Last close is **above session VWAP** (volume-weighted average price for the window Yahoo/ta built). "
        "Often used intraday as a bull/bear “fair value” reference — above can mean relative strength vs that session average."
    ),
    "Below VWAP": (
        "Last close is **at or below VWAP** → price not demonstrating acceptance above the volume-weighted average in this snapshot."
    ),
}


def snapshot_levels(df: Any, result: dict[str, Any]) -> dict[str, float]:
    last = df.iloc[-1]
    return {
        "last_close": float(last["Close"]),
        "vwap": float(last["VWAP"]),
        "atr": float(last["ATR"]),
        "rule_stop": float(result["stop_loss"]),
        "rule_target": float(result["target"]),
    }


def format_rule_factor_breakdown(reason_csv: str) -> str:
    """Expand comma-separated tags into readable sections."""
    tags = [t.strip() for t in reason_csv.split(",") if t.strip()]
    blocks = []
    for i, tag in enumerate(tags, start=1):
        body = FACTOR_HELP.get(tag, f"*No built-in blurb for “{tag}” — it still counted in the score.*")
        blocks.append(f"#### {i}. {tag}\n\n{body}\n")
    return "\n---\n".join(blocks) if blocks else "_No factor tags._"


def scorecard_how_it_works() -> str:
    return """
### How the BUY / SELL / HOLD label is produced

The engine runs **five checks** on the **latest completed bar** in your downloaded data:

| Check | Bullish / +1 side | Bearish / −1 side |
|-------|--------------------|-------------------|
| EMA trend | EMA9 > EMA20 | EMA9 < EMA20 |
| RSI band | RSI > 55 | RSI < 45 |
| MACD | MACD > 0 | MACD ≤ 0 |
| vs VWAP | Close > VWAP | Close ≤ VWAP |

**Note:** RSI only moves one step: either “Strong”, “Weak”, or neither (neutral band 45–55 scores 0 on RSI).

**Final label**

- **Score ≥ 3 → BUY**
- **Score ≤ −2 → SELL**
- **Else → HOLD**

**Stops & targets** use **ATR** from the same bar: BUY uses stop ≈ close − ATR, target ≈ close + 2×ATR (direction flips for SELL; HOLD uses a symmetric band for display).

*This is a teaching summary of the code path — not investment advice.*
""".strip()


def rule_based_playbook_text(lv: dict[str, float], signal: str) -> str:
    """Plain-language zones anchored to rule stop/target/VWAP."""
    lc = lv["last_close"]
    stp = lv["rule_stop"]
    tgt = lv["rule_target"]
    vw = lv["vwap"]
    atr = lv["atr"]

    lines = [
        "### Reference numbers (from your latest bar + rules)",
        "",
        f"| Role | ₹ Price |",
        f"|------|---------|",
        f"| Last close (series) | **{lc:.2f}** |",
        f"| VWAP (session reference) | **{vw:.2f}** |",
        f"| ATR (volatility proxy) | **{atr:.2f}** |",
        f"| Rule invalidation / stop **reference** | **{stp:.2f}** |",
        f"| Rule objective / target **reference** | **{tgt:.2f}** |",
        "",
        "### How this ties to the rule signal",
    ]

    if signal == "BUY":
        lines += [
            f"- **Bullish posture** in this model assumes acceptance **above ~₹{max(lc, vw):.2f}** (last vs VWAP context).",
            f"- If price **cannot hold above** that zone and **slides toward ₹{stp:.2f}**, treat as **wait / reassess** — that stop reference is where the rule logic would **invalidate** the bull story.",
            f"- If follow-through holds, the **objective reference** is anchored toward **₹{tgt:.2f}** (math overlay — not a promise of reaching it).",
            "- **Options-style analogy (education only):** long views often pair **confirmation above** a pivot-like level with **risk** referenced toward the invalidation zone.",
        ]
    elif signal == "SELL":
        lines += [
            f"- **Bearish posture** assumes repeated trade **below ~₹{min(lc, vw):.2f}**.",
            f"- If price **never breaks / holds below** that idea and **reclaims toward ₹{stp:.2f}**, treat as **wait / reassess**.",
            f"- If downside extends, **stretch reference** sits toward **₹{tgt:.2f}**.",
            "- Short-side analogues invert the same logic.",
        ]
    else:
        lines += [
            f"- **HOLD / wait** when the score sits between bullish and bearish thresholds — price is often **chopping between ₹{min(stp, tgt):.2f}** and **₹{max(stp, tgt):.2f}** on these references.",
            "- Wait for a **clean hold beyond VWAP** *or* a **clean failure through VWAP** before forcing a directional story.",
        ]

    lines += [
        "",
        "---",
        "*Everything above restates indicator-derived references — not a personalized recommendation.*",
    ]
    return "\n".join(lines)


def format_full_deterministic_desk(reason_csv: str, lv: dict[str, float], signal: str) -> str:
    """Large markdown block for the main UI when Angad LLM layer is off or as baseline."""
    parts = [
        "## What each flashing factor means",
        "",
        format_rule_factor_breakdown(reason_csv),
        "",
        "---",
        "",
        scorecard_how_it_works(),
        "",
        "---",
        "",
        rule_based_playbook_text(lv, signal),
    ]
    return "\n".join(parts)


def default_chart_levels(lv: dict[str, float], signal: str) -> list[dict[str, Any]]:
    """Fallback horizontal lines for Plotly."""
    rows = [
        {"price": lv["last_close"], "label": "Last close", "kind": "spot"},
        {"price": lv["vwap"], "label": "VWAP ref", "kind": "context"},
        {"price": lv["rule_stop"], "label": "Rule stop / invalidation ref", "kind": "risk"},
        {"price": lv["rule_target"], "label": "Rule objective ref", "kind": "target"},
    ]
    if signal == "BUY":
        rows.insert(2, {"price": max(lv["last_close"], lv["vwap"]), "label": "Bull confirmation pivot (price vs VWAP)", "kind": "trigger"})
    elif signal == "SELL":
        rows.insert(2, {"price": min(lv["last_close"], lv["vwap"]), "label": "Bear confirmation pivot (price vs VWAP)", "kind": "trigger"})
    return rows


def merge_chart_levels(intel_levels: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer model-supplied numeric lines when sane."""
    out: list[dict[str, Any]] = []
    seen = set()
    if isinstance(intel_levels, list):
        for row in intel_levels:
            if not isinstance(row, dict):
                continue
            try:
                p = float(row.get("price"))
            except (TypeError, ValueError):
                continue
            label = str(row.get("label") or "Level")
            kind = str(row.get("kind") or "ref")
            key = round(p, 4)
            if key in seen:
                continue
            seen.add(key)
            out.append({"price": p, "label": label, "kind": kind})
    for row in fallback:
        key = round(float(row["price"]), 4)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return sorted(out, key=lambda r: r["price"])


def chart_y_range(
    df_ist: Any,
    proj_cmp: Any,
    proj_qual: Any | None,
    chart_levels: list[dict[str, Any]],
) -> tuple[float, float]:
    """Pad Y-axis so price + projections + lines stay readable."""
    ys: list[float] = []
    close = df_ist["Close"].astype(float)
    ys.extend([float(close.min()), float(close.max())])
    if proj_cmp is not None and len(proj_cmp) > 0:
        ys.extend([float(proj_cmp.min()), float(proj_cmp.max())])
    if proj_qual is not None and len(proj_qual) > 0:
        ys.extend([float(proj_qual.min()), float(proj_qual.max())])
    for row in chart_levels:
        ys.append(float(row["price"]))
    if not ys:
        return 0.0, 1.0
    lo, hi = min(ys), max(ys)
    span = hi - lo
    pad = max(span * 0.06, hi * 0.0015, 1e-6)
    return lo - pad, hi + pad
