"""Accuracy dashboard charts."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from prediction.accuracy import compute_accuracy_metrics, confidence_distribution_df
from prediction.history_store import PredictionHistoryStore


def build_accuracy_dashboard(symbol: str | None = None, store: PredictionHistoryStore | None = None) -> go.Figure:
    """Build accuracy analytics dashboard with multiple panels."""
    store = store or PredictionHistoryStore()
    metrics = compute_accuracy_metrics(symbol, store)
    history = store.to_dataframe(symbol, limit=100)
    conf_df = confidence_distribution_df(symbol, store)

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Prediction Error Over Time",
            "Win / Loss",
            "Confidence Distribution",
            "Predicted vs Actual",
        ),
        specs=[[{"type": "scatter"}, {"type": "bar"}], [{"type": "bar"}, {"type": "scatter"}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    if not history.empty:
        evaluated = history[history["actual_price"].notna()].copy()
        if not evaluated.empty:
            evaluated["timestamp"] = pd.to_datetime(evaluated["timestamp"])
            fig.add_trace(
                go.Scatter(
                    x=evaluated["timestamp"], y=evaluated["error_pct"],
                    mode="lines+markers", name="Error %",
                    line=dict(color="#e74c3c"),
                ),
                row=1, col=1,
            )
            wins = int(evaluated["win"].fillna(False).sum())
            losses = len(evaluated) - wins
            fig.add_trace(
                go.Bar(x=["Wins", "Losses"], y=[wins, losses], marker_color=["#27ae60", "#e74c3c"], name="W/L"),
                row=1, col=2,
            )
            fig.add_trace(
                go.Scatter(
                    x=evaluated["predicted_price"], y=evaluated["actual_price"],
                    mode="markers", name="Pred vs Actual",
                    marker=dict(color=evaluated["confidence"], colorscale="Viridis", size=8),
                ),
                row=2, col=2,
            )

    if not conf_df.empty:
        fig.add_trace(
            go.Bar(x=conf_df["bucket"].astype(str), y=conf_df["count"], marker_color="#3498db", name="Confidence"),
            row=2, col=1,
        )

    fig.update_layout(
        template="plotly_dark", height=600,
        title_text=(
            f"Accuracy: {metrics['accuracy_pct']}% · Win rate: {metrics['win_rate_pct']}% · "
            f"Avg error: {metrics['avg_error_pct']}% · P/L sim: {metrics['profit_loss_sim_pct']}%"
        ),
        showlegend=False,
    )
    return fig
