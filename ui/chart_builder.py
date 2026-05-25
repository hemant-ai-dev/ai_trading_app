"""Chart: green live line, red solid prediction lines (saved runs for accuracy)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PRED_COLOR = "#e74c3c"
PRED_COLOR_PAST = "rgba(231, 76, 60, 0.35)"
LIVE_COLOR = "#2ecc71"


def _is_mobile() -> bool:
    return st.session_state.get("angad_mobile_mode", False)


def build_live_prediction_chart(
    *,
    df_ist: pd.DataFrame,
    live_line: pd.Series,
    current_pred: pd.Series | None,
    hist_predictions: pd.DataFrame,
    y0: float,
    y1: float,
    today,
) -> go.Figure:
    mobile = _is_mobile()
    h = 420 if mobile else 640
    fig = go.Figure()

    if len(df_ist) > 0:
        prior_mask = df_ist.index.map(lambda t: t.date()) < today
        prior = df_ist.loc[prior_mask]
        if len(prior) > 0:
            fig.add_trace(
                go.Scatter(
                    x=prior.index,
                    y=prior["Close"],
                    name="History",
                    line=dict(color="#566573", width=1),
                    opacity=0.35,
                )
            )

    if live_line is not None and len(live_line) > 0:
        fig.add_trace(
            go.Scatter(
                x=live_line.index,
                y=live_line.values,
                name="Live price",
                line=dict(color=LIVE_COLOR, width=3 if mobile else 4),
            )
        )

    # Past saved prediction lines (red solid, faint) — for accuracy comparison later
    if hist_predictions is not None and not hist_predictions.empty and "run_time" in hist_predictions.columns:
        hist = hist_predictions.copy()
        hist["target_time"] = pd.to_datetime(hist["target_time"])
        runs = hist["run_time"].unique()
        max_runs = 25 if mobile else 40
        if len(runs) > max_runs:
            runs = runs[-max_runs:]
        for rt in runs:
            sub = hist[hist["run_time"] == rt]
            fig.add_trace(
                go.Scatter(
                    x=sub["target_time"],
                    y=sub["predicted_price"],
                    name="Past prediction",
                    line=dict(color=PRED_COLOR_PAST, width=1.5),
                    showlegend=False,
                    hovertemplate="Saved pred: ₹%{y:.2f}<extra></extra>",
                )
            )

    # Current prediction (red solid bold) — saved to SQL this run
    if current_pred is not None and len(current_pred) > 0:
        fig.add_trace(
            go.Scatter(
                x=current_pred.index,
                y=current_pred.values,
                name="Prediction line (now)",
                line=dict(color=PRED_COLOR, width=4 if not mobile else 3),
            )
        )

    fig.update_layout(
        template="plotly_dark",
        height=h,
        font=dict(size=11 if mobile else 13),
        xaxis_title="Time (IST)",
        yaxis_title="Price (₹)",
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0.45)"),
        margin=dict(t=55, l=50, r=20, b=45),
        hovermode="x unified",
        dragmode="pan",
    )
    fig.update_xaxes(rangeslider_visible=not mobile)
    fig.update_yaxes(range=[y0, y1], tickformat=".2f", separatethousands=True)
    return fig
