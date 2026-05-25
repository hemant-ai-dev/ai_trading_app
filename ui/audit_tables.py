"""Readable SQL audit tables — no raw JSON on screen."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ui.bilingual import SIGNAL_EN_MR, parse_reason_tags


def _safe_json_list(raw) -> list:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else []
    except json.JSONDecodeError:
        return []


def render_audit_summary(audit: pd.DataFrame) -> None:
    if audit.empty:
        st.caption("No predictions saved yet.")
        return

    summary = audit[
        [
            "run_id",
            "run_time_ist",
            "source_type",
            "signal",
            "confidence_pct",
            "target_price",
            "stop_loss",
        ]
    ].copy()
    summary["Signal (MR)"] = summary["signal"].map(
        lambda s: SIGNAL_EN_MR.get(str(s).upper(), ("", ""))[1]
    )
    summary.columns = [
        "Run #",
        "Time (IST)",
        "Source",
        "Signal",
        "Confidence %",
        "Target ₹",
        "Stop ₹",
        "Signal (Marathi)",
    ]
    st.dataframe(summary, use_container_width=True, hide_index=True)


def render_audit_detail_tables(row: pd.Series) -> None:
    st.markdown(f"**Run #{int(row['run_id'])}** · {row['source_type']} · {row['signal']}")

    if pd.notna(row.get("market_read")):
        st.markdown("Market read (English)")
        st.write(str(row["market_read"])[:3000])

    steps = _safe_json_list(row.get("reasoning_steps_json"))
    steps_mr = []
    raw = row.get("genai_output_json")
    if pd.notna(raw):
        try:
            obj = json.loads(raw) if isinstance(raw, str) else {}
            steps_mr = obj.get("reasoning_steps_mr") or []
        except json.JSONDecodeError:
            pass
    if steps:
        rows = []
        for i, s in enumerate(steps):
            mr = steps_mr[i] if i < len(steps_mr) else "—"
            rows.append({"Step": i + 1, "Logic (English)": s, "Logic (Marathi)": mr})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    news = _safe_json_list(row.get("news_cited_json"))
    if news:
        rows = []
        for n in news:
            if isinstance(n, dict):
                rows.append(
                    {
                        "Headline ID": n.get("headline_id", "—"),
                        "Why it matters": n.get("why_it_matters", n.get("note", "—")),
                    }
                )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    ind = _safe_json_list(row.get("indicators_json"))
    if isinstance(row.get("indicators_json"), str):
        try:
            ind = json.loads(row["indicators_json"])
        except json.JSONDecodeError:
            ind = {}
    if isinstance(ind, dict) and ind:
        flat = []
        for k, v in ind.items():
            flat.append({"Field": k, "Value": v})
        st.dataframe(pd.DataFrame(flat), use_container_width=True, hide_index=True)

    reason = row.get("reason_tags") or ""
    if reason:
        tags = parse_reason_tags(str(reason))
        st.dataframe(
            pd.DataFrame([{"Factor": t} for t in tags]),
            use_container_width=True,
            hide_index=True,
        )
