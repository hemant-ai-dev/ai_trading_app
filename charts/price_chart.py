"""Professional interactive trading charts with indicators and predictions."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators.fibonacci import FibonacciLevels

LIVE_COLOR = "#2ecc71"
PRED_COLOR = "#e74c3c"
PRED_COLOR_PAST = "rgba(231, 76, 60, 0.35)"
BUY_COLOR = "#27ae60"
SELL_COLOR = "#e74c3c"
FIB_COLOR = "rgba(155, 89, 182, 0.6)"


def build_trading_chart(
    *,
    df_ist: pd.DataFrame,
    live_line: pd.Series,
    current_pred: pd.Series | None,
    hist_predictions: pd.DataFrame,
    fib: FibonacciLevels | None,
    support_resistance: dict[str, list[float]] | None,
    buy_signals: list | None = None,
    sell_signals: list | None = None,
    y0: float,
    y1: float,
    today,
    show_rsi: bool = True,
    mobile: bool = False,
) -> go.Figure:
    """Build multi-panel chart with price, predictions, Fibonacci, and RSI."""
    rows = 2 if show_rsi else 1
    row_heights = [0.75, 0.25] if show_rsi else [1.0]
    h = 480 if mobile else 720

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
    )

    if len(df_ist) > 0:
        prior_mask = df_ist.index.map(lambda t: t.date()) < today
        prior = df_ist.loc[prior_mask]
        if len(prior) > 0:
            fig.add_trace(
                go.Scatter(
                    x=prior.index, y=prior["Close"], name="History",
                    line=dict(color="#566573", width=1), opacity=0.35,
                ),
                row=1, col=1,
            )

    if live_line is not None and len(live_line) > 0:
        fig.add_trace(
            go.Scatter(
                x=live_line.index, y=live_line.values, name="Live price",
                line=dict(color=LIVE_COLOR, width=3 if mobile else 4),
            ),
            row=1, col=1,
        )

    if hist_predictions is not None and not hist_predictions.empty and "run_time" in hist_predictions.columns:
        runs = hist_predictions["run_time"].unique()[-(15 if mobile else 30):]
        for rt in runs:
            sub = hist_predictions[hist_predictions["run_time"] == rt]
            fig.add_trace(
                go.Scatter(
                    x=sub["target_time"], y=sub["predicted_price"],
                    line=dict(color=PRED_COLOR_PAST, width=1.2),
                    showlegend=False, hovertemplate="Past pred: ₹%{y:.2f}<extra></extra>",
                ),
                row=1, col=1,
            )

    if current_pred is not None and len(current_pred) > 0:
        fig.add_trace(
            go.Scatter(
                x=current_pred.index, y=current_pred.values, name="AI prediction",
                line=dict(color=PRED_COLOR, width=4 if not mobile else 3),
            ),
            row=1, col=1,
        )

    if fib is not None:
        for label, level in fib.retracements.items():
            if label in ("38.2%", "50.0%", "61.8%"):
                fig.add_hline(
                    y=level, line_dash="dot", line_color=FIB_COLOR,
                    annotation_text=f"Fib {label}", annotation_position="right",
                    row=1, col=1,
                )

    if support_resistance:
        for s in support_resistance.get("support", []):
            fig.add_hline(y=s, line_dash="dash", line_color="#3498db", opacity=0.5, row=1, col=1)
        for r in support_resistance.get("resistance", []):
            fig.add_hline(y=r, line_dash="dash", line_color="#e67e22", opacity=0.5, row=1, col=1)

    if buy_signals:
        fig.add_trace(
            go.Scatter(
                x=[b[0] for b in buy_signals], y=[b[1] for b in buy_signals],
                mode="markers", name="Buy", marker=dict(symbol="triangle-up", size=12, color=BUY_COLOR),
            ),
            row=1, col=1,
        )
    if sell_signals:
        fig.add_trace(
            go.Scatter(
                x=[s[0] for s in sell_signals], y=[s[1] for s in sell_signals],
                mode="markers", name="Sell", marker=dict(symbol="triangle-down", size=12, color=SELL_COLOR),
            ),
            row=1, col=1,
        )

    if show_rsi and "RSI" in df_ist.columns:
        fig.add_trace(
            go.Scatter(x=df_ist.index, y=df_ist["RSI"], name="RSI", line=dict(color="#9b59b6", width=1.5)),
            row=2, col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_color="#e74c3c", opacity=0.4, row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#27ae60", opacity=0.4, row=2, col=1)

    fig.update_layout(
        template="plotly_dark", height=h,
        font=dict(size=11 if mobile else 13),
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0.45)"),
        margin=dict(t=55, l=50, r=20, b=45),
        hovermode="x unified", dragmode="pan",
    )
    fig.update_yaxes(range=[y0, y1], tickformat=".2f", row=1, col=1)
    fig.update_xaxes(rangeslider_visible=not mobile, row=1, col=1)
    return fig
