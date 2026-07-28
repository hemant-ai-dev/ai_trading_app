"""
Professional Kite-style candlestick trading chart.

Features:
  - OHLC candlesticks with volume
  - Zoom / pan / rangeslider
  - Crosshair (unified x-hover) with price & time
  - Price scale on the right, time scale at bottom
  - Dark / light themes
  - Indicator overlays (EMA, SMA, VWAP, BB, Fib, S/R)
  - Optional RSI / MACD / ATR / ADX panes
  - AI future prediction curve + confidence bands
  - Past prediction overlays with Correct / Incorrect markers
  - Buy / Sell / Hold signal markers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from charts.themes import ThemeDict, get_theme
from indicators.fibonacci import FibonacciLevels

IndicatorFlags = dict[str, bool]

DEFAULT_INDICATORS: IndicatorFlags = {
    "ema": True,
    "sma": False,
    "vwap": True,
    "bollinger": False,
    "rsi": True,
    "macd": False,
    "volume": True,
    "atr": False,
    "adx": False,
    "support_resistance": True,
    "fibonacci": True,
    "fib_extension": False,
}


def _candle_colors(df: pd.DataFrame, theme: ThemeDict) -> list[str]:
    """Per-bar volume colors matching candle direction."""
    colors: list[str] = []
    for _, row in df.iterrows():
        up = float(row["Close"]) >= float(row["Open"])
        colors.append(theme["volume_up"] if up else theme["volume_down"])
    return colors


def _future_projection_from_last(
    df_ist: pd.DataFrame,
    projection: pd.Series | None,
) -> pd.Series | None:
    """
    Ensure future prediction starts exactly at the last candle close
    and only extends into future timestamps (no historical overlap).
    """
    if projection is None or len(projection) == 0 or df_ist.empty:
        return projection
    last_ts = df_ist.index[-1]
    last_px = float(df_ist["Close"].iloc[-1])
    future = projection[projection.index > last_ts].copy()
    if future.empty:
        # Keep path but force anchor at last candle
        idx = projection.index
        vals = projection.astype(float).values.copy()
        if len(vals):
            vals[0] = last_px
        return pd.Series(vals, index=idx, name="projection")
    # Prepend anchor at last candle
    anchor = pd.Series([last_px], index=[last_ts], name="projection")
    return pd.concat([anchor, future.astype(float)])


def _confidence_bands(
    proj: pd.Series,
    low: float | None,
    high: float | None,
    confidence: float,
) -> tuple[pd.Series, pd.Series] | None:
    """Build upper/lower confidence bands around a projection path."""
    if proj is None or len(proj) < 2:
        return None
    start = float(proj.iloc[0])
    end = float(proj.iloc[-1])
    if low is None or high is None or low >= high:
        # Derive band width from confidence (lower conf = wider band)
        width_pct = max(0.004, (100 - confidence) / 100 * 0.04)
        low = min(start, end) * (1 - width_pct)
        high = max(start, end) * (1 + width_pct)
    n = len(proj)
    # Expand band gradually toward the end
    t = np.linspace(0, 1, n)
    upper = start + (high - start) * t
    lower = start + (low - start) * t
    # Keep bands outside the center path
    center = proj.astype(float).values
    upper = np.maximum(upper, center)
    lower = np.minimum(lower, center)
    return (
        pd.Series(upper, index=proj.index),
        pd.Series(lower, index=proj.index),
    )


def _subplot_layout(flags: IndicatorFlags) -> tuple[int, list[float], list[str]]:
    """Decide subplot rows: price (+volume) (+rsi) (+macd) (+atr/adx)."""
    rows = 1
    titles = ["Price"]
    heights = [0.62]
    if flags.get("volume", True):
        rows += 1
        titles.append("Volume")
        heights.append(0.12)
    if flags.get("rsi", False):
        rows += 1
        titles.append("RSI")
        heights.append(0.13)
    if flags.get("macd", False):
        rows += 1
        titles.append("MACD")
        heights.append(0.13)
    if flags.get("atr", False) or flags.get("adx", False):
        rows += 1
        label = "ATR / ADX" if flags.get("atr") and flags.get("adx") else ("ATR" if flags.get("atr") else "ADX")
        titles.append(label)
        heights.append(0.12)
    # Normalize heights
    total = sum(heights)
    heights = [h / total for h in heights]
    # Price gets remaining weight preference
    if rows == 1:
        heights = [1.0]
    return rows, heights, titles


def build_trading_chart(
    *,
    df_ist: pd.DataFrame,
    live_line: pd.Series | None = None,
    current_pred: pd.Series | None = None,
    hist_predictions: pd.DataFrame | None = None,
    fib: FibonacciLevels | None = None,
    support_resistance: dict[str, list[float]] | None = None,
    buy_signals: Sequence[tuple[Any, float]] | None = None,
    sell_signals: Sequence[tuple[Any, float]] | None = None,
    hold_signals: Sequence[tuple[Any, float]] | None = None,
    y0: float | None = None,
    y1: float | None = None,
    today=None,
    mobile: bool = False,
    theme_name: str = "dark",
    indicators: IndicatorFlags | None = None,
    signal: str | None = None,
    confidence: float = 0.0,
    predicted_price: float | None = None,
    price_low: float | None = None,
    price_high: float | None = None,
    prediction_start: datetime | None = None,
    prediction_end: datetime | None = None,
    comparison_records: list[dict[str, Any]] | None = None,
    show_rsi: bool | None = None,
) -> go.Figure:
    """
    Build a professional multi-pane candlestick trading chart.

    ``indicators`` toggles control overlays and secondary panes.
    ``comparison_records`` annotate past predictions vs reality on the chart.
    """
    theme = get_theme(theme_name)
    flags = dict(DEFAULT_INDICATORS)
    if indicators:
        flags.update(indicators)
    # Backward-compat for older callers
    if show_rsi is not None:
        flags["rsi"] = bool(show_rsi)

    rows, heights, titles = _subplot_layout(flags)
    h = 520 if mobile else 780

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=heights,
        subplot_titles=titles if not mobile else None,
    )

    price_row = 1
    next_row = 2
    vol_row = macd_row = rsi_row = atr_row = None
    if flags.get("volume", True):
        vol_row = next_row
        next_row += 1
    if flags.get("rsi", False):
        rsi_row = next_row
        next_row += 1
    if flags.get("macd", False):
        macd_row = next_row
        next_row += 1
    if flags.get("atr", False) or flags.get("adx", False):
        atr_row = next_row

    # --- Candlesticks ---
    if len(df_ist) > 0:
        fig.add_trace(
            go.Candlestick(
                x=df_ist.index,
                open=df_ist["Open"],
                high=df_ist["High"],
                low=df_ist["Low"],
                close=df_ist["Close"],
                name="OHLC",
                increasing_line_color=theme["candle_up"],
                decreasing_line_color=theme["candle_down"],
                increasing_fillcolor=theme["candle_up"],
                decreasing_fillcolor=theme["candle_down"],
                whiskerwidth=0.4,
                hovertext=[
                    f"O ₹{o:,.2f}<br>H ₹{h_:,.2f}<br>L ₹{l_:,.2f}<br>C ₹{c:,.2f}"
                    for o, h_, l_, c in zip(
                        df_ist["Open"], df_ist["High"], df_ist["Low"], df_ist["Close"]
                    )
                ],
                hoverinfo="text+x",
            ),
            row=price_row,
            col=1,
        )

    # --- Moving averages / VWAP / Bollinger ---
    overlay_specs = []
    if flags.get("ema"):
        for col, color, label in (
            ("EMA9", theme["ema9"], "EMA 9"),
            ("EMA20", theme["ema20"], "EMA 20"),
            ("EMA50", theme["ema50"], "EMA 50"),
        ):
            if col in df_ist.columns:
                overlay_specs.append((col, color, label, 1.2))
    if flags.get("sma"):
        for col, color, label in (
            ("SMA20", theme["sma20"], "SMA 20"),
            ("SMA50", theme["sma50"], "SMA 50"),
        ):
            if col in df_ist.columns:
                overlay_specs.append((col, color, label, 1.0))
    if flags.get("vwap") and "VWAP" in df_ist.columns:
        overlay_specs.append(("VWAP", theme["vwap"], "VWAP", 1.4))

    for col, color, label, width in overlay_specs:
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist[col],
                name=label,
                line=dict(color=color, width=width),
                hovertemplate=f"{label}: ₹%{{y:.2f}}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )

    if flags.get("bollinger") and {"BB_UPPER", "BB_MIDDLE", "BB_LOWER"}.issubset(df_ist.columns):
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["BB_UPPER"],
                name="BB Upper",
                line=dict(color=theme["bb"], width=1, dash="dot"),
                hovertemplate="BB Upper: ₹%{y:.2f}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["BB_LOWER"],
                name="BB Lower",
                line=dict(color=theme["bb"], width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(33,150,243,0.08)",
                hovertemplate="BB Lower: ₹%{y:.2f}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["BB_MIDDLE"],
                name="BB Mid",
                line=dict(color=theme["bb"], width=1),
                showlegend=False,
            ),
            row=price_row,
            col=1,
        )

    # --- Fibonacci ---
    if flags.get("fibonacci") and fib is not None:
        key_levels = ("38.2%", "50.0%", "61.8%")
        for label, level in fib.retracements.items():
            if label in key_levels:
                fig.add_hline(
                    y=level,
                    line_dash="dot",
                    line_color=theme["fib"],
                    line_width=1,
                    annotation_text=f"Fib {label}",
                    annotation_position="right",
                    annotation_font_color=theme["fib"],
                    annotation_font_size=10,
                    row=price_row,
                    col=1,
                )
        if flags.get("fib_extension"):
            for label, level in fib.extensions.items():
                fig.add_hline(
                    y=level,
                    line_dash="dashdot",
                    line_color=theme["fib"],
                    line_width=1,
                    opacity=0.55,
                    annotation_text=f"Ext {label}",
                    annotation_position="right",
                    annotation_font_size=9,
                    row=price_row,
                    col=1,
                )

    # --- Support / Resistance ---
    if flags.get("support_resistance") and support_resistance:
        for s in support_resistance.get("support", [])[:3]:
            fig.add_hline(
                y=s,
                line_dash="dash",
                line_color=theme["support"],
                opacity=0.55,
                line_width=1,
                row=price_row,
                col=1,
            )
        for r in support_resistance.get("resistance", [])[:3]:
            fig.add_hline(
                y=r,
                line_dash="dash",
                line_color=theme["resistance"],
                opacity=0.55,
                line_width=1,
                row=price_row,
                col=1,
            )

    # --- Past predictions (faint) ---
    if hist_predictions is not None and not hist_predictions.empty:
        hp = hist_predictions.copy()
        if "run_time" in hp.columns and "target_time" in hp.columns:
            runs = hp["run_time"].unique()[-(8 if mobile else 16):]
            for i, rt in enumerate(runs):
                sub = hp[hp["run_time"] == rt]
                fig.add_trace(
                    go.Scatter(
                        x=pd.to_datetime(sub["target_time"]),
                        y=sub["predicted_price"],
                        mode="lines",
                        line=dict(color=theme["pred_past"], width=1, dash="dot"),
                        name="Past AI pred" if i == 0 else None,
                        showlegend=(i == 0),
                        hovertemplate="Past AI: ₹%{y:.2f}<extra></extra>",
                        legendgroup="past_pred",
                    ),
                    row=price_row,
                    col=1,
                )

    # --- Future prediction + confidence bands ---
    proj = _future_projection_from_last(df_ist, current_pred)
    if proj is not None and len(proj) > 0:
        bands = _confidence_bands(proj, price_low, price_high, confidence)
        if bands is not None:
            upper, lower = bands
            fig.add_trace(
                go.Scatter(
                    x=upper.index,
                    y=upper.values,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=price_row,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=lower.index,
                    y=lower.values,
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor=theme["pred_band"],
                    name="Confidence band",
                    hoverinfo="skip",
                ),
                row=price_row,
                col=1,
            )
        fig.add_trace(
            go.Scatter(
                x=proj.index,
                y=proj.values,
                name="AI future prediction",
                mode="lines",
                line=dict(color=theme["pred_future"], width=3, dash="solid"),
                hovertemplate="AI pred: ₹%{y:.2f}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )
        # Prediction start / end markers
        start_ts = prediction_start or proj.index[0]
        end_ts = prediction_end or proj.index[-1]
        start_px = float(proj.iloc[0])
        end_px = float(predicted_price) if predicted_price else float(proj.iloc[-1])
        fig.add_trace(
            go.Scatter(
                x=[start_ts, end_ts],
                y=[start_px, end_px],
                mode="markers+text",
                marker=dict(
                    symbol=["circle", "diamond"],
                    size=[9, 11],
                    color=[theme["live"], theme["pred_future"]],
                    line=dict(width=1, color=theme["text"]),
                ),
                text=["Start", f"End ₹{end_px:,.2f}"],
                textposition=["top center", "top right"],
                textfont=dict(size=10, color=theme["text"]),
                name="Pred window",
                hovertemplate="%{text}<br>%{x}<br>₹%{y:.2f}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )

    # --- Signal markers ---
    def _add_markers(points, name, symbol, color):
        if not points:
            return
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                mode="markers",
                name=name,
                marker=dict(
                    symbol=symbol,
                    size=14 if not mobile else 11,
                    color=color,
                    line=dict(width=1, color=theme["text"]),
                ),
                hovertemplate=f"{name}: ₹%{{y:.2f}}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )

    # Current signal at last candle if no explicit lists
    if not buy_signals and not sell_signals and not hold_signals and signal and len(df_ist):
        pt = (df_ist.index[-1], float(df_ist["Close"].iloc[-1]))
        if signal == "BUY":
            buy_signals = [pt]
        elif signal == "SELL":
            sell_signals = [pt]
        else:
            hold_signals = [pt]

    _add_markers(buy_signals, "Buy", "triangle-up", theme["buy"])
    _add_markers(sell_signals, "Sell", "triangle-down", theme["sell"])
    _add_markers(hold_signals, "Hold", "diamond", theme["hold"])

    # --- Compare prediction vs reality annotations ---
    if comparison_records:
        for rec in comparison_records[-12:]:
            ts = pd.to_datetime(rec.get("timestamp"))
            pred_px = rec.get("predicted_price")
            actual = rec.get("actual_price")
            sig = rec.get("signal", "HOLD")
            if pred_px is None or actual is None or pd.isna(actual):
                continue
            diff_pct = (float(actual) - float(pred_px)) / float(pred_px) * 100 if pred_px else 0
            correct = bool(rec.get("win"))
            status = "Correct" if correct else "Incorrect"
            color = theme["correct"] if correct else theme["incorrect"]
            icon = "OK" if correct else "X"
            fig.add_annotation(
                x=ts,
                y=float(actual),
                text=(
                    f"{icon} {sig} @ ₹{float(pred_px):,.1f}<br>"
                    f"Actual ₹{float(actual):,.1f} ({diff_pct:+.1f}%)<br>"
                    f"{status}"
                ),
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowcolor=color,
                ax=0,
                ay=-40 if correct else 40,
                bgcolor="rgba(11,14,17,0.85)" if theme["name"] == "dark" else "rgba(255,255,255,0.9)",
                bordercolor=color,
                borderwidth=1,
                font=dict(size=9, color=theme["text"]),
                row=price_row,
                col=1,
            )

    # --- Volume ---
    if vol_row is not None and "Volume" in df_ist.columns and len(df_ist):
        fig.add_trace(
            go.Bar(
                x=df_ist.index,
                y=df_ist["Volume"],
                name="Volume",
                marker_color=_candle_colors(df_ist, theme),
                hovertemplate="Vol: %{y:,.0f}<extra></extra>",
            ),
            row=vol_row,
            col=1,
        )
        if "VOL_MA20" in df_ist.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_ist.index,
                    y=df_ist["VOL_MA20"],
                    name="Vol MA20",
                    line=dict(color=theme["muted"], width=1),
                    hovertemplate="Vol MA: %{y:,.0f}<extra></extra>",
                ),
                row=vol_row,
                col=1,
            )

    # --- RSI ---
    if rsi_row is not None and "RSI" in df_ist.columns:
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["RSI"],
                name="RSI",
                line=dict(color=theme["rsi"], width=1.5),
                hovertemplate="RSI: %{y:.1f}<extra></extra>",
            ),
            row=rsi_row,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dot", line_color=theme["sell"], opacity=0.5, row=rsi_row, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color=theme["buy"], opacity=0.5, row=rsi_row, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color=theme["muted"], opacity=0.3, row=rsi_row, col=1)
        fig.update_yaxes(range=[0, 100], row=rsi_row, col=1)

    # --- MACD ---
    if macd_row is not None and {"MACD", "MACD_SIGNAL", "MACD_HIST"}.issubset(df_ist.columns):
        hist_colors = [
            theme["macd_hist_pos"] if v >= 0 else theme["macd_hist_neg"]
            for v in df_ist["MACD_HIST"].fillna(0)
        ]
        fig.add_trace(
            go.Bar(
                x=df_ist.index,
                y=df_ist["MACD_HIST"],
                name="MACD Hist",
                marker_color=hist_colors,
                hovertemplate="Hist: %{y:.4f}<extra></extra>",
            ),
            row=macd_row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["MACD"],
                name="MACD",
                line=dict(color=theme["macd"], width=1.4),
            ),
            row=macd_row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df_ist.index,
                y=df_ist["MACD_SIGNAL"],
                name="Signal",
                line=dict(color=theme["macd_signal"], width=1.2),
            ),
            row=macd_row,
            col=1,
        )

    # --- ATR / ADX ---
    if atr_row is not None:
        if flags.get("atr") and "ATR" in df_ist.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_ist.index,
                    y=df_ist["ATR"],
                    name="ATR",
                    line=dict(color=theme["atr"], width=1.4),
                    hovertemplate="ATR: %{y:.2f}<extra></extra>",
                ),
                row=atr_row,
                col=1,
            )
        if flags.get("adx") and "ADX" in df_ist.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_ist.index,
                    y=df_ist["ADX"],
                    name="ADX",
                    line=dict(color=theme["adx"], width=1.4),
                    hovertemplate="ADX: %{y:.1f}<extra></extra>",
                ),
                row=atr_row,
                col=1,
            )

    # --- Layout: Kite-style terminal ---
    fig.update_layout(
        template=theme["template"],
        paper_bgcolor=theme["paper_bg"],
        plot_bgcolor=theme["plot_bg"],
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=11 if mobile else 12, color=theme["text"]),
        height=h,
        margin=dict(t=40 if mobile else 48, l=8, r=64, b=40),
        legend=dict(
            orientation="h",
            y=1.02,
            x=0,
            bgcolor="rgba(0,0,0,0)" if theme["name"] == "dark" else "rgba(255,255,255,0)",
            font=dict(size=10),
        ),
        hovermode="x unified",
        dragmode="pan",
        uirevision="angad-chart",  # preserve zoom across refreshes
        transition={"duration": 280, "easing": "cubic-in-out"},
        xaxis_rangeslider_visible=False,
        spikedistance=-1,
    )

    # Crosshair spikes on all x-axes; price scale on the right for price pane
    for r in range(1, rows + 1):
        fig.update_xaxes(
            showgrid=True,
            gridcolor=theme["grid"],
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikecolor=theme["crosshair"],
            spikethickness=1,
            spikedash="solid",
            showline=True,
            linecolor=theme["border"],
            row=r,
            col=1,
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor=theme["grid"],
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikecolor=theme["crosshair"],
            spikethickness=1,
            showline=True,
            linecolor=theme["border"],
            side="right",
            tickformat=".2f" if r == price_row else None,
            fixedrange=False,
            row=r,
            col=1,
        )

    # Bottom time scale + rangeslider on last x-axis only for non-mobile
    fig.update_xaxes(
        title_text="Time (IST)",
        rangeslider_visible=not mobile,
        rangeslider_thickness=0.05,
        row=rows,
        col=1,
    )
    fig.update_yaxes(title_text="Price (₹)", row=price_row, col=1)

    if y0 is not None and y1 is not None:
        fig.update_yaxes(range=[y0, y1], row=price_row, col=1)
    elif len(df_ist) > 0:
        lo = float(df_ist[["Low", "Close"]].min().min())
        hi = float(df_ist[["High", "Close"]].max().max())
        if proj is not None and len(proj):
            lo = min(lo, float(proj.min()))
            hi = max(hi, float(proj.max()))
        pad = max((hi - lo) * 0.05, hi * 0.001)
        fig.update_yaxes(range=[lo - pad, hi + pad], row=price_row, col=1)

    # Confidence badge annotation
    if signal and confidence:
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.98,
            text=f"{signal} · {confidence:.0f}% conf",
            showarrow=False,
            font=dict(
                size=13,
                color=theme["buy"] if signal == "BUY" else (theme["sell"] if signal == "SELL" else theme["hold"]),
            ),
            bgcolor="rgba(0,0,0,0.45)" if theme["name"] == "dark" else "rgba(255,255,255,0.85)",
            borderpad=6,
        )

    return fig
