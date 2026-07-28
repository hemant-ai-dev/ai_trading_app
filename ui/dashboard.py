"""Dashboard UI components for the trading terminal."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from charts.accuracy_dashboard import build_accuracy_dashboard
from charts.price_chart import DEFAULT_INDICATORS, build_trading_chart
from level_plan import chart_y_range
from prediction.accuracy import compute_accuracy_metrics
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult


SIGNAL_COLORS = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#f0b90b"}


def render_top_bar(ms: Any, latest: float, primary: PredictionResult, symbol: str) -> None:
    """Live market header strip."""
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    c1, c2, c3, c4, c5, c6 = st.columns([1.1, 1.1, 1.2, 1.0, 1.0, 1.2])
    c1.metric("Symbol", symbol)
    c2.metric("IST Time", ms.now_ist.strftime("%H:%M:%S"))
    c3.metric("Session", ms.phase.value.replace("_", " ").title())
    c4.metric("Live Price", f"₹{latest:,.2f}")
    c5.metric("Signal", primary.signal)
    c6.metric("Confidence", f"{primary.confidence:.0f}%")
    st.markdown(
        f'<div class="signal-strip" style="border-color:{color}"></div>',
        unsafe_allow_html=True,
    )


def render_confidence_meter(confidence: float, signal: str) -> None:
    """Visual confidence meter."""
    color = SIGNAL_COLORS.get(signal, "#95a5a6")
    st.markdown("##### Confidence Meter")
    st.progress(min(max(confidence / 100.0, 0.0), 1.0))
    st.caption(f"{confidence:.0f}% — {signal}")
    st.markdown(
        f'<div class="conf-bar"><div style="width:{confidence:.0f}%;background:{color}"></div></div>',
        unsafe_allow_html=True,
    )


def render_risk_meter(risk_level: str, atr: float, close: float) -> None:
    """Simple risk meter for beginners."""
    atr_pct = (atr / close * 100) if close else 0
    st.markdown("##### Risk Meter")
    level_map = {"Low": 0.25, "Medium": 0.55, "High": 0.85}
    st.progress(level_map.get(risk_level, 0.5))
    st.caption(f"{risk_level} risk · ATR {atr_pct:.2f}% of price")


def render_ai_explanation_panel(primary: PredictionResult, explanation: dict) -> None:
    """Side panel explaining the AI prediction in plain language."""
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    st.markdown(
        f"""
        <div class="ai-panel" style="border-left:4px solid {color}">
          <div class="ai-panel-title">AI Explanation</div>
          <div class="ai-pred" style="color:{color}">{primary.signal}</div>
          <div class="ai-conf">Confidence: <b>{primary.confidence:.0f}%</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**Reason**")
    reasons = explanation.get("reasons") or primary.reasons_simple or primary.reasons
    if reasons:
        for r in reasons:
            st.markdown(f"• {r}")
    else:
        st.caption("No detailed reasons available for this run.")

    st.markdown("**Suggested action**")
    st.info(explanation.get("suggested_action", "Watch the market and manage risk."))

    st.markdown("**Trend**")
    st.write(explanation.get("trend_summary", primary.trend.title()))

    if primary.source == "GENAI" and primary.raw.get("market_read"):
        with st.expander("Full AI market read", expanded=False):
            st.markdown(primary.raw["market_read"])


def render_compare_card(primary: PredictionResult, latest: float, history_row: dict | None) -> None:
    """Prediction vs reality comparison card."""
    st.markdown("##### Compare Prediction vs Reality")
    if history_row and history_row.get("actual_price") is not None:
        pred = float(history_row["predicted_price"])
        actual = float(history_row["actual_price"])
        diff = (actual - pred) / pred * 100 if pred else 0
        correct = bool(history_row.get("win"))
        status = "Correct" if correct else "Incorrect"
        icon = "Correct" if correct else "Incorrect"
        color = SIGNAL_COLORS["BUY"] if correct else SIGNAL_COLORS["SELL"]
        st.markdown(
            f"""
            <div class="compare-card" style="border-color:{color}">
              <div><b>Prediction:</b> {history_row.get('signal','—')} @ ₹{pred:,.2f}</div>
              <div><b>Actual Result:</b> Price moved to ₹{actual:,.2f}</div>
              <div><b>Difference:</b> {diff:+.2f}%</div>
              <div><b>Prediction Status:</b> <span style="color:{color}">{icon} — {status}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Live pending comparison against current prediction
        pred = primary.predicted_price
        diff = (latest - pred) / pred * 100 if pred else 0
        st.markdown(
            f"""
            <div class="compare-card">
              <div><b>Prediction:</b> {primary.signal} @ ₹{pred:,.2f}</div>
              <div><b>Actual Result:</b> Live price ₹{latest:,.2f} (still unfolding)</div>
              <div><b>Difference so far:</b> {diff:+.2f}%</div>
              <div><b>Prediction Status:</b> Pending evaluation</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_indicator_snapshot(ctx: dict) -> None:
    """Compact technical snapshot."""
    st.markdown("##### Technical Snapshot")
    rows = [
        ("RSI", f"{ctx.get('rsi', 0):.1f}"),
        ("MACD", f"{ctx.get('macd', 0):.4f}"),
        ("ADX", f"{ctx.get('adx', 0):.1f}"),
        ("ATR", f"{ctx.get('atr', 0):.2f}"),
        ("VWAP", f"₹{ctx.get('vwap', 0):,.2f}"),
        ("EMA 9/20", f"{ctx.get('ema9', 0):.2f} / {ctx.get('ema20', 0):.2f}"),
        ("Volume ratio", f"{ctx.get('vol_ratio', 1):.2f}x"),
        ("Trend", str(ctx.get("trend_dir", "neutral")).title()),
    ]
    st.dataframe(
        pd.DataFrame(rows, columns=["Indicator", "Value"]),
        use_container_width=True,
        hide_index=True,
    )


def render_fibonacci_panel(fib) -> None:
    """Fibonacci levels table."""
    if fib is None:
        st.caption("Fibonacci levels unavailable.")
        return
    st.markdown("##### Fibonacci Levels")
    st.caption(f"Swing {fib.trend} · High ₹{fib.swing_high:,.2f} · Low ₹{fib.swing_low:,.2f}")
    ret = pd.DataFrame([{"Level": k, "Price": f"₹{v:,.2f}"} for k, v in fib.retracements.items()])
    st.dataframe(ret, use_container_width=True, hide_index=True)
    if fib.extensions:
        with st.expander("Extensions", expanded=False):
            ext = pd.DataFrame(
                [{"Level": k, "Price": f"₹{v:,.2f}"} for k, v in fib.extensions.items()]
            )
            st.dataframe(ext, use_container_width=True, hide_index=True)


def render_volume_analysis(ctx: dict) -> None:
    """Volume analysis block."""
    st.markdown("##### Volume Analysis")
    ratio = float(ctx.get("vol_ratio") or 1.0)
    if ratio >= 1.5:
        msg = "Volume is well above average — strong participation behind the move."
    elif ratio >= 1.1:
        msg = "Volume is slightly above average — moderate conviction."
    elif ratio <= 0.7:
        msg = "Volume is below average — the move may lack conviction."
    else:
        msg = "Volume is near average — typical activity."
    st.write(msg)
    st.caption(f"Volume / 20-bar average: {ratio:.2f}x")


def collect_indicator_flags(sidebar: bool = True) -> dict[str, bool]:
    """Sidebar toggles for each indicator overlay."""
    container = st.sidebar if sidebar else st
    container.markdown("### Chart Indicators")
    flags = dict(DEFAULT_INDICATORS)
    labels = {
        "ema": "EMA 9 / 20 / 50",
        "sma": "SMA 20 / 50",
        "vwap": "VWAP",
        "bollinger": "Bollinger Bands",
        "rsi": "RSI pane",
        "macd": "MACD pane",
        "volume": "Volume",
        "atr": "ATR",
        "adx": "ADX",
        "support_resistance": "Support & Resistance",
        "fibonacci": "Fibonacci Retracement",
        "fib_extension": "Fibonacci Extension",
    }
    for key, label in labels.items():
        flags[key] = container.checkbox(label, value=flags[key], key=f"ind_{key}")
    return flags


def render_main_chart(
    *,
    df_ist: pd.DataFrame,
    live_line: pd.Series,
    projection,
    fib,
    sr,
    primary: PredictionResult,
    history: PredictionHistoryStore,
    symbol: str,
    today,
    mobile: bool,
    theme_name: str,
    indicators: dict[str, bool],
) -> None:
    """Render the professional candlestick chart."""
    hist = history.load_projection_history(symbol, 40)
    comparison = history.load_comparison_records(symbol, limit=12)
    fib_levels = list(fib.retracements.values()) if fib else []
    y0, y1 = chart_y_range(df_ist, projection, fib_levels)

    pred_start = projection.index[0] if projection is not None and len(projection) else None
    pred_end = projection.index[-1] if projection is not None and len(projection) else None

    # Historical signal markers from stored predictions
    buy_signals, sell_signals, hold_signals = [], [], []
    for rec in history.load_history(symbol, limit=25):
        pt = (rec.timestamp, rec.predicted_price)
        if rec.signal == "BUY":
            buy_signals.append(pt)
        elif rec.signal == "SELL":
            sell_signals.append(pt)
        else:
            hold_signals.append(pt)

    fig = build_trading_chart(
        df_ist=df_ist,
        live_line=live_line,
        current_pred=projection,
        hist_predictions=hist,
        fib=fib,
        support_resistance=sr,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        hold_signals=hold_signals,
        y0=y0,
        y1=y1,
        today=today,
        mobile=mobile,
        theme_name=theme_name,
        indicators=indicators,
        signal=primary.signal,
        confidence=primary.confidence,
        predicted_price=primary.predicted_price,
        price_low=primary.price_low,
        price_high=primary.price_high,
        prediction_start=pred_start,
        prediction_end=pred_end,
        comparison_records=comparison,
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
            "displaylogo": False,
        },
    )
    st.caption(
        "Candles = market OHLC · Yellow line = AI future prediction · "
        "Triangles = Buy/Sell · Diamond = Hold · Annotations = pred vs reality"
    )


def render_prediction_history(symbol: str, history: PredictionHistoryStore) -> None:
    """Full prediction history table with P/L simulation."""
    df = history.to_dataframe(symbol, limit=100)
    if df.empty:
        st.info("No predictions saved yet. They appear after each analysis refresh.")
        return
    display = df.copy()
    if "profit_loss_pct" not in display.columns:
        display["profit_loss_pct"] = display.apply(_row_pl, axis=1)
    cols = {
        "timestamp": "Timestamp",
        "market_price": "Market Price",
        "signal": "AI Prediction",
        "confidence": "Confidence",
        "predicted_price": "Predicted",
        "actual_price": "Actual Outcome",
        "error_pct": "Error %",
        "win": "Correct?",
        "profit_loss_pct": "P/L Sim %",
        "accuracy_label": "Accuracy",
    }
    keep = [c for c in cols if c in display.columns]
    out = display[keep].rename(columns=cols)
    st.dataframe(out, use_container_width=True, hide_index=True)


def _row_pl(row: pd.Series) -> float | None:
    if row.get("actual_price") is None or pd.isna(row.get("actual_price")):
        return None
    pred = float(row["predicted_price"])
    actual = float(row["actual_price"])
    if pred == 0:
        return None
    raw = (actual - pred) / pred * 100
    if row.get("signal") == "SELL":
        return round(-raw, 2)
    if row.get("signal") == "HOLD":
        return round(-abs(raw), 2)
    return round(raw, 2)


def render_accuracy_section(symbol: str, history: PredictionHistoryStore, theme_name: str = "dark") -> None:
    """Accuracy statistics + charts."""
    metrics = compute_accuracy_metrics(symbol, history)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Accuracy (±1%)", f"{metrics['accuracy_pct']}%")
    c2.metric("Win Rate", f"{metrics['win_rate_pct']}%")
    c3.metric("Avg Error", f"{metrics['avg_error_pct']}%")
    c4.metric("Avg Confidence", f"{metrics['avg_confidence']}%")
    c5.metric("P/L Simulation", f"{metrics['profit_loss_sim_pct']}%")
    if metrics["evaluated"] > 0:
        fig = build_accuracy_dashboard(symbol, history)
        if theme_name == "light":
            fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Accuracy charts appear after predictions are evaluated against live prices.")
