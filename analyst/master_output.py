"""Mandatory AI output schema from trading_prompt_master.md §3."""

from __future__ import annotations

import json
from typing import Any


SIGNAL_MAP = {"BUY": "LONG", "SELL": "SHORT", "HOLD": "FLAT"}
REVERSE_MAP = {"LONG": "BUY", "SHORT": "SELL", "FLAT": "HOLD"}


def to_master_prediction(signal: str) -> str:
    s = (signal or "HOLD").upper()
    if s in SIGNAL_MAP:
        return SIGNAL_MAP[s]
    if s in ("LONG", "SHORT", "FLAT"):
        return s
    return "FLAT"


def build_master_output(
    *,
    market_regime: str,
    signal: str,
    confidence: float,
    trigger_price: float,
    take_profit_target: float,
    stop_loss_level: float,
    technical_rationale: str,
    error: bool = False,
) -> dict[str, Any]:
    """
    Single JSON-ready dict matching trading_prompt_master.md.

    confidence_score is 0–1 (master schema), not 0–100.
    """
    conf01 = confidence if confidence <= 1.0 else confidence / 100.0
    conf01 = max(0.0, min(1.0, round(conf01, 4)))
    rationale = (technical_rationale or "").strip()
    # Max two sentences
    parts = [p.strip() for p in rationale.replace("!", ".").split(".") if p.strip()]
    rationale = ". ".join(parts[:2])
    if rationale and not rationale.endswith("."):
        rationale += "."

    return {
        "market_regime": market_regime
        or "Mean-Reverting Chop",
        "prediction": to_master_prediction(signal),
        "confidence_score": conf01,
        "execution_metrics": {
            "trigger_price": round(float(trigger_price or 0), 4),
            "take_profit_target": round(float(take_profit_target or 0), 4),
            "stop_loss_level": round(float(stop_loss_level or 0), 4),
        },
        "technical_rationale": rationale
        or (
            "Error: Insufficient or malformed data feed provided."
            if error
            else "Insufficient structural alignment for a directional call."
        ),
    }


def master_output_json_string(payload: dict[str, Any]) -> str:
    """Return raw JSON string without markdown fences (parser-friendly)."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def flat_error_output() -> dict[str, Any]:
    """§4 guardrail — corrupt/missing feed → FLAT."""
    return build_master_output(
        market_regime="Mean-Reverting Chop",
        signal="FLAT",
        confidence=0.0,
        trigger_price=0.0,
        take_profit_target=0.0,
        stop_loss_level=0.0,
        technical_rationale="Error: Insufficient or malformed data feed provided.",
        error=True,
    )
