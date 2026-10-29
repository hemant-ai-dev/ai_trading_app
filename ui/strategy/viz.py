"""Shared Plotly charts for the neon desk — dark glass, educational only."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult

SIGNAL_COLORS = {"BUY": "#2ee6a6", "SELL": "#ff5d7a", "HOLD": "#c084fc"}


def _base(fig: go.Figure, *, height: int = 240, title: str = "") -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16,18,48,0.35)",
        height=height,
        margin=dict(l=12, r=12, t=42 if title else 16, b=12),
        title=dict(text=title, font=dict(size=13, color="#c9c6ff"), x=0.02, xanchor="left"),
        font=dict(color="#c8c6e8", size=11, family="Segoe UI, sans-serif"),
        showlegend=False,
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(124,92,255,0.12)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(124,92,255,0.12)", zeroline=False)
    return fig


def prediction_confidence_donut(primary: PredictionResult) -> go.Figure:
    conf = max(0.0, min(100.0, float(primary.confidence or 0)))
    color = SIGNAL_COLORS.get(primary.signal, "#8b7cff")
    fig = go.Figure(
        data=[
            go.Pie(
                values=[conf, max(0.0, 100.0 - conf)],
                labels=[f"{primary.signal}", "Open risk"],
                hole=0.74,
                marker=dict(colors=[color, "rgba(255,255,255,0.08)"], line=dict(width=0)),
                textinfo="none",
                hovertemplate="%{label}: %{value:.0f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        annotations=[
            dict(
                text=f"<b>{conf:.0f}%</b><br><span style='font-size:11px;color:#9aa0c7'>{primary.signal}</span>",
                x=0.5,
                y=0.5,
                font=dict(size=22, color="#f4f2ff"),
                showarrow=False,
            )
        ]
    )
    return _base(fig, height=200, title="Conviction")


def signal_mix_donut(history: PredictionHistoryStore, symbol: str) -> go.Figure:
    df = history.to_dataframe(symbol, limit=40)
    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    if not df.empty and "signal" in df.columns:
        for sig, n in df["signal"].value_counts().items():
            key = str(sig).upper()
            if key in counts:
                counts[key] = int(n)
    if sum(counts.values()) == 0:
        counts["HOLD"] = 1
    fig = go.Figure(
        data=[
            go.Pie(
                values=list(counts.values()),
                labels=list(counts.keys()),
                hole=0.62,
                marker=dict(colors=["#2ee6a6", "#ff5d7a", "#c084fc"], line=dict(width=0)),
                textinfo="label+percent",
                textfont=dict(size=11),
            )
        ]
    )
    return _base(fig, height=260, title="Signal mix (this symbol)")


def volume_profile(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df is None or df.empty or "Volume" not in df.columns:
        fig.add_annotation(text="No volume", x=0.5, y=0.5, showarrow=False)
        return _base(fig, height=220, title="Volume")
    tail = df.tail(40)
    closes = tail["Close"]
    up = closes >= closes.shift(1)
    colors = ["#2ee6a6" if bool(u) else "#ff5d7a" for u in up.fillna(True)]
    fig.add_bar(x=list(tail.index.astype(str)), y=tail["Volume"], marker_color=colors, name="Volume")
    fig.update_xaxes(showticklabels=False)
    return _base(fig, height=220, title="Volume (last 40 daily bars)")


def close_spark(df: pd.DataFrame, title: str = "Close path") -> go.Figure:
    fig = go.Figure()
    if df is None or df.empty:
        return _base(fig, height=220, title=title)
    tail = df.tail(60)
    fig.add_scatter(
        x=list(tail.index),
        y=tail["Close"],
        mode="lines",
        line=dict(color="#7cf0ff", width=2.4),
        name="Close",
    )
    return _base(fig, height=220, title=title)


def ma_ribbon(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df is None or df.empty:
        fig.add_annotation(text="No close series", x=0.5, y=0.5, showarrow=False)
        return _base(fig, height=220, title="Moving averages")
    tail = df.tail(80).copy()
    close = tail["Close"].astype(float)
    fig.add_scatter(x=list(tail.index), y=close, mode="lines", line=dict(color="#f4f2ff", width=1.6), name="Close")
    if len(close) >= 10:
        fig.add_scatter(
            x=list(tail.index),
            y=close.rolling(10, min_periods=5).mean(),
            mode="lines",
            line=dict(color="#7cf0ff", width=1.8),
            name="MA10",
        )
    if len(close) >= 20:
        fig.add_scatter(
            x=list(tail.index),
            y=close.rolling(20, min_periods=8).mean(),
            mode="lines",
            line=dict(color="#c084fc", width=1.8),
            name="MA20",
        )
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, font=dict(size=10)))
    return _base(fig, height=220, title="Close vs MA10 / MA20")


def news_sentiment_donut(news_agg: dict | None) -> go.Figure:
    agg = news_agg or {}
    bull = max(0.0, float(agg.get("bull_score") or 0))
    bear = max(0.0, float(agg.get("bear_score") or 0))
    rest = max(0.4, 3.0 - bull - bear)
    fig = go.Figure(
        data=[
            go.Pie(
                values=[bull or 0.15, bear or 0.15, rest],
                labels=["Bull headlines", "Bear headlines", "Neutral / unscored"],
                hole=0.62,
                marker=dict(colors=["#2ee6a6", "#ff5d7a", "rgba(255,255,255,0.12)"], line=dict(width=0)),
                textinfo="percent",
            )
        ]
    )
    tilt = str(agg.get("tilt") or "neutral").title()
    fig.update_layout(
        annotations=[
            dict(
                text=f"<b>{tilt}</b><br><span style='font-size:11px;color:#9aa0c7'>news tilt</span>",
                x=0.5,
                y=0.5,
                font=dict(size=16, color="#f4f2ff"),
                showarrow=False,
            )
        ]
    )
    return _base(fig, height=260, title="Headline mix today")


def price_levels_map(latest: float, primary: PredictionResult) -> go.Figure:
    rows = [
        ("Stop", float(primary.stop_loss or 0), "#ff5d7a"),
        ("Last", float(latest), "#7cf0ff"),
        ("Predicted", float(primary.predicted_price or 0), "#c084fc"),
        ("Target", float(primary.target_price or 0), "#2ee6a6"),
    ]
    fig = go.Figure()
    fig.add_bar(
        y=[r[0] for r in rows],
        x=[r[1] for r in rows],
        orientation="h",
        marker_color=[r[2] for r in rows],
        text=[f"₹{r[1]:,.2f}" for r in rows],
        textposition="outside",
        cliponaxis=False,
    )
    fig.update_xaxes(title_text="₹")
    return _base(fig, height=220, title="Today’s price map")


def pnl_bars(history: PredictionHistoryStore, symbol: str) -> go.Figure:
    df = history.to_dataframe(symbol, limit=24)
    fig = go.Figure()
    if df.empty or "profit_loss_sim_pct" not in df.columns:
        fig.add_annotation(text="No evaluated P/L yet", x=0.5, y=0.5, showarrow=False)
        return _base(fig, height=220, title="Simulated P/L")
    sub = df.dropna(subset=["profit_loss_sim_pct"]).tail(12)
    if sub.empty:
        fig.add_annotation(text="No evaluated P/L yet", x=0.5, y=0.5, showarrow=False)
        return _base(fig, height=220, title="Simulated P/L")
    colors = ["#2ee6a6" if float(v) >= 0 else "#ff5d7a" for v in sub["profit_loss_sim_pct"]]
    fig.add_bar(
        x=list(range(len(sub))),
        y=sub["profit_loss_sim_pct"],
        marker_color=colors,
        name="P/L %",
    )
    fig.update_xaxes(title_text="Recent evaluated calls", showticklabels=False)
    fig.update_yaxes(title_text="%")
    return _base(fig, height=220, title="Simulated P/L (educational)")


def rsi_gauge(rsi: float | None) -> go.Figure:
    val = 50.0 if rsi is None else float(rsi)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=val,
            number={"font": {"size": 28, "color": "#f4f2ff"}, "suffix": ""},
            title={"text": "RSI", "font": {"size": 13, "color": "#c9c6ff"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#6b6790"},
                "bar": {"color": "#8b7cff"},
                "bgcolor": "rgba(255,255,255,0.04)",
                "steps": [
                    {"range": [0, 30], "color": "rgba(46,230,166,0.35)"},
                    {"range": [30, 70], "color": "rgba(124,92,255,0.2)"},
                    {"range": [70, 100], "color": "rgba(255,93,122,0.35)"},
                ],
                "threshold": {"line": {"color": "#ff5d7a", "width": 2}, "value": 70},
            },
        )
    )
    return _base(fig, height=240, title="")
