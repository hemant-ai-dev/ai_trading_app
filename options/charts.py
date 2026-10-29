"""Plotly helpers for option prediction bar and premium chart."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def prediction_bar(call_p: float, put_p: float) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        y=["Call", "Put"],
        x=[call_p, put_p],
        orientation="h",
        marker_color=["#2ee6a6", "#ff5d7a"],
        text=[f"{call_p:.0f}%", f"{put_p:.0f}%"],
        textposition="inside",
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,18,48,0.35)",
        height=140,
        margin=dict(l=48, r=12, t=28, b=24),
        title=dict(text="Option prediction bar (not a guarantee)", font=dict(size=12, color="#c9c6ff")),
        xaxis=dict(range=[0, 100], title="%"),
        showlegend=False,
        font=dict(color="#c8c6e8", size=11),
    )
    return fig


def premium_chart(
    predicted: pd.Series,
    actual: pd.Series,
    *,
    entry_low: float | None = None,
    entry_high: float | None = None,
    stop: float | None = None,
    target1: float | None = None,
    target2: float | None = None,
) -> go.Figure:
    fig = go.Figure()
    if actual is not None and len(actual):
        fig.add_scatter(
            x=list(actual.index),
            y=list(actual.astype(float)),
            name="Actual premium",
            mode="lines",
            line=dict(color="#2ee6a6", width=2.2),
        )
    if predicted is not None and len(predicted):
        fig.add_scatter(
            x=list(predicted.index),
            y=list(predicted.astype(float)),
            name="AI predicted premium",
            mode="lines+markers",
            line=dict(color="#f0b90b", width=2.4),
            marker=dict(size=5),
        )
    for y, name, color, dash in (
        (entry_low, "Entry low", "#7cf0ff", "dot"),
        (entry_high, "Entry high", "#7cf0ff", "dot"),
        (stop, "Stop", "#ff5d7a", "dash"),
        (target1, "Target 1", "#2ee6a6", "dash"),
        (target2, "Target 2", "#26a69a", "dash"),
    ):
        if y:
            fig.add_hline(y=float(y), line_dash=dash, line_color=color, annotation_text=name, annotation_font_size=10)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,18,48,0.35)",
        height=280,
        margin=dict(l=40, r=16, t=36, b=36),
        title=dict(text="Option premium — actual vs AI (educational)", font=dict(size=13, color="#c9c6ff")),
        legend=dict(orientation="h", y=1.12),
        font=dict(color="#c8c6e8", size=11),
    )
    return fig
