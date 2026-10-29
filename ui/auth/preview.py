"""Sample charts on the login page — explain the desk, not live prices."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def _skin(fig: go.Figure, *, height: int, title: str) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,18,48,0.35)",
        height=height,
        margin=dict(l=10, r=10, t=38, b=10),
        title=dict(text=title, font=dict(size=12, color="#c9c6ff"), x=0.02, xanchor="left"),
        font=dict(color="#c8c6e8", size=10, family="Segoe UI, sans-serif"),
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(124,92,255,0.12)", zeroline=False, showticklabels=False)
    fig.update_yaxes(gridcolor="rgba(124,92,255,0.12)", zeroline=False)
    return fig


def sample_tape() -> go.Figure:
    o = [100, 101.2, 100.4, 99.6, 100.8, 102.1, 101.5, 103.0, 102.2, 101.4, 100.9, 101.8]
    c = [101.2, 100.4, 99.6, 100.8, 102.1, 101.5, 103.0, 102.2, 101.4, 100.9, 101.8, 101.1]
    h = [max(a, b) + 0.45 for a, b in zip(o, c)]
    l = [min(a, b) - 0.4 for a, b in zip(o, c)]
    x = list(range(len(o)))
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=x,
            open=o,
            high=h,
            low=l,
            close=c,
            increasing_line_color="#2ee6a6",
            decreasing_line_color="#ff5d7a",
            increasing_fillcolor="#2ee6a6",
            decreasing_fillcolor="#ff5d7a",
            name="Traded",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[11, 14],
            y=[c[-1], 99.2],
            mode="lines",
            line=dict(color="#f0c14b", width=2, dash="dash"),
            name="Guessed path",
        )
    )
    fig.update_layout(xaxis_rangeslider_visible=False)
    return _skin(fig, height=200, title="Tape — candles = traded, gold = guessed path")


def sample_conviction() -> go.Figure:
    fig = go.Figure(
        data=[
            go.Pie(
                values=[72, 28],
                labels=["SELL conviction", "Open risk"],
                hole=0.72,
                marker=dict(colors=["#ff5d7a", "rgba(255,255,255,0.08)"], line=dict(width=0)),
                textinfo="none",
            )
        ]
    )
    fig.update_layout(
        annotations=[
            dict(
                text="<b>72%</b><br><span style='font-size:11px;color:#9aa0c7'>SELL</span>",
                x=0.5,
                y=0.5,
                font=dict(size=18, color="#f4f2ff"),
                showarrow=False,
            )
        ]
    )
    return _skin(fig, height=200, title="Donut — how sure this run is")


def sample_levels() -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        y=["Stop", "Last close", "Target"],
        x=[103.4, 101.1, 98.6],
        orientation="h",
        marker_color=["#ff5d7a", "#7cf0ff", "#2ee6a6"],
        text=["₹ stop", "₹ last", "₹ target"],
        textposition="inside",
        insidetextanchor="middle",
        cliponaxis=False,
    )
    fig.update_xaxes(title_text="Sample levels (SELL example)", showticklabels=True)
    fig.update_yaxes(showticklabels=True)
    return _skin(fig, height=200, title="Levels — entry vs target vs stop")


def render_login_preview_charts() -> None:
    a, b, c = st.columns(3, gap="medium")
    cfg = {"displayModeBar": False, "staticPlot": False}
    with a:
        st.plotly_chart(sample_tape(), use_container_width=True, config=cfg)
    with b:
        st.plotly_chart(sample_conviction(), use_container_width=True, config=cfg)
    with c:
        st.plotly_chart(sample_levels(), use_container_width=True, config=cfg)
