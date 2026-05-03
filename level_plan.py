"""Deterministic reference levels from last bar + signal (education only — not advice)."""

from __future__ import annotations

from typing import Any


def snapshot_levels(df: Any, result: dict[str, Any]) -> dict[str, float]:
    last = df.iloc[-1]
    return {
        "last_close": float(last["Close"]),
        "vwap": float(last["VWAP"]),
        "atr": float(last["ATR"]),
        "rule_stop": float(result["stop_loss"]),
        "rule_target": float(result["target"]),
    }


def rule_based_playbook_text(lv: dict[str, float], signal: str) -> str:
    """Plain-language zones anchored to rule stop/target/VWAP."""
    lc = lv["last_close"]
    stp = lv["rule_stop"]
    tgt = lv["rule_target"]
    vw = lv["vwap"]
    atr = lv["atr"]

    lines = [
        f"- **Last close (series):** ₹{lc:.2f}",
        f"- **Rule VWAP (session reference):** ₹{vw:.2f}",
        f"- **ATR (recent volatility proxy):** ₹{atr:.2f}",
        f"- **Rule reference stop / invalidation band:** ₹{stp:.2f}",
        f"- **Rule reference objective:** ₹{tgt:.2f}",
        "",
        "**How this ties to the rule signal:**",
    ]

    if signal == "BUY":
        lines += [
            f"- Bullish bias assumes sustained acceptance **above ~₹{max(lc, vw):.2f}** (price/VWAP context).",
            f"- If price **never holds above** that neighbourhood and slips toward **₹{stp:.2f}**, treat as **wait / reassess** — rule invalidation sits near that zone.",
            f"- If momentum confirms up, **objective band is anchored toward ₹{tgt:.2f}** (not guaranteed).",
            "- For index/options-style thinking *education only*: long-volatility analogues often tie **confirmation above** a strike-like pivot and **risk cut** toward the invalidation zone.",
        ]
    elif signal == "SELL":
        lines += [
            f"- Bearish bias assumes repeated rejection **below ~₹{min(lc, vw):.2f}**.",
            f"- If price **never breaks / holds below** that context and squeezes toward **₹{stp:.2f}**, treat as **wait / reassess**.",
            f"- If downside expands, **reference stretch sits toward ₹{tgt:.2f}**.",
            "- Educational analogues on the short side mirror this with inverted triggers.",
        ]
    else:
        lines += [
            f"- Neutral/wait posture between **₹{min(stp, tgt):.2f}** and **₹{max(stp, tgt):.2f}** rule anchors.",
            "- Confirmation requires a clean hold beyond VWAP **or** a breakdown through it — avoid forcing direction mid-range.",
        ]

    lines.append("")
    lines.append("*Everything above restates indicator-derived references — not a personalized recommendation.*")
    return "\n".join(lines)


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
