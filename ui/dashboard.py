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
from ui.smart_box import build_smart_box


SIGNAL_COLORS = {"BUY": "#26a69a", "SELL": "#ef5350", "HOLD": "#f0b90b"}


def render_desk_header(username: str, role: str) -> None:
    """Trading-floor banner with a moving ticker strip."""
    st.markdown(
        f"""
<div class="desk-hero">
  <div class="desk-hero-copy">
    <div class="terminal-title">Angad — Trading Floor</div>
    <div class="terminal-sub">Signed in as <b>{username}</b> · {role} · Smart Box for a quick read, charts when you want depth</div>
  </div>
  <div class="desk-live-pill">LIVE DESK</div>
</div>
<div class="ticker-wrap">
  <div class="ticker-tape">NSE · NIFTY 50 · BANK NIFTY · SENSEX · RELIANCE · TCS · INFY · BUY / SELL / HOLD · Educational analysis · Not a profit guarantee · </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_ai_signal_hero(primary: PredictionResult, latest: float, explanation: dict | None = None) -> None:
    """Primary decision card: signal, entry, target, stop, confidence, risk."""
    box = build_smart_box(primary, latest)
    color = SIGNAL_COLORS.get(box["signal"], "#94a3b8")
    explanation = explanation or {}
    reasons = explanation.get("reasons") or primary.reasons_simple or primary.reasons or []
    why = str(reasons[0]) if reasons else box["summary"]
    st.markdown(
        f"""
<div class="signal-hero" style="border-color:{color}">
  <div class="smart-kicker">AI SIGNAL · Smart Box</div>
  <div class="smart-signal" style="color:{color}">{box["headline"]}</div>
  <p class="smart-summary">{box["summary"]}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    if box["signal"] == "HOLD":
        a, b, c, d = st.columns(4)
        a.metric("Watch buy near", f"₹{box['consider_buy']:,.2f}")
        b.metric("Watch sell near", f"₹{box['consider_sell']:,.2f}")
        c.metric("Confidence", f"{box['confidence']:.0f}%")
        d.metric("Risk", box["risk_level"])
        st.info(
            f"HOLD means no high-conviction setup yet. A BUY becomes more interesting near "
            f"₹{box['consider_buy']:,.2f} with confirmation; a SELL / reduce near ₹{box['consider_sell']:,.2f}."
        )
    else:
        a, b, c, d, e = st.columns(5)
        a.metric("Entry", f"₹{box['entry']:,.2f}")
        b.metric("Target", f"₹{box['target']:,.2f}")
        c.metric("Stop-loss", f"₹{box['stop']:,.2f}")
        d.metric("Confidence", f"{box['confidence']:.0f}%")
        e.metric("Risk", box["risk_level"])
    st.caption(f"Why (short): {why} · Regime {box['regime']} · Trend {box['trend']} · Not a profit guarantee")


def render_market_overview(ms: Any, latest: float, primary: PredictionResult, symbol: str, bars: int, window_label: str) -> None:
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    phase = ms.phase.value.replace("_", " ").title()
    if phase.lower().startswith("closed"):
        phase = "Closed"
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Symbol", symbol)
    c2.metric("Live price", f"₹{latest:,.2f}")
    c3.metric("Session", phase)
    c4.metric("IST", ms.now_ist.strftime("%H:%M:%S"))
    c5.metric("Trend", (primary.trend or "—").title())
    c6.metric("Regime", primary.market_regime or "—")
    st.markdown(f'<div class="signal-strip" style="border-color:{color}"></div>', unsafe_allow_html=True)
    st.caption(window_label)


def render_sentiment_card(news_agg: dict | None, news_impacts: list | None) -> None:
    agg = news_agg or {}
    net = float(agg.get("net_score") or 0)
    score = int(max(0, min(100, round((net + 2.5) / 5 * 100))))
    tilt = str(agg.get("tilt") or "neutral").title()
    color = SIGNAL_COLORS["BUY"] if tilt.lower() == "bullish" else (
        SIGNAL_COLORS["SELL"] if tilt.lower() == "bearish" else SIGNAL_COLORS["HOLD"]
    )
    st.markdown("##### Market sentiment")
    st.markdown(
        f"""
<div class="sentiment-card">
  <div class="sentiment-score" style="color:{color}">{score}</div>
  <div class="sentiment-tilt" style="color:{color}">{tilt}</div>
  <div class="sentiment-copy">{agg.get("summary") or "No scored headlines this run."}</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.progress(min(max(score / 100.0, 0.0), 1.0))
    st.caption(f"From {agg.get('count', 0)} scored headlines · bull {agg.get('bull_score', 0)} / bear {agg.get('bear_score', 0)}")


def render_recent_analysis(history: PredictionHistoryStore, symbol: str) -> None:
    st.markdown("##### Recent analysis")
    df = history.to_dataframe(None, limit=8)
    if df.empty:
        st.caption("Your runs on this account will appear here.")
        return
    keep = [c for c in ("timestamp", "symbol", "signal", "confidence", "predicted_price", "accuracy_label") if c in df.columns]
    st.dataframe(df[keep], use_container_width=True, hide_index=True, height=220)


def render_performance_strip(history: PredictionHistoryStore, symbol: str) -> None:
    metrics = compute_accuracy_metrics(symbol, history)
    a, b, c, d = st.columns(4)
    a.metric("Win rate", f"{metrics['win_rate_pct']}%")
    b.metric("Accuracy ±1%", f"{metrics['accuracy_pct']}%")
    c.metric("Evaluated", int(metrics["evaluated"]))
    d.metric("P/L sim", f"{metrics['profit_loss_sim_pct']}%")
    st.caption(f"Performance for {symbol} on this account · educational simulation, not a profit guarantee")


def render_smart_box(primary: PredictionResult, latest: float, theme_name: str = "dark") -> None:
    """Glanceable recommendation — delegates to the hero signal card."""
    render_ai_signal_hero(primary, latest)


def render_top_bar(ms: Any, latest: float, primary: PredictionResult, symbol: str) -> None:
    """Live market header strip."""
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    c1, c2, c3, c4, c5, c6 = st.columns([1.1, 1.1, 1.2, 1.0, 1.0, 1.2])
    phase = ms.phase.value.replace("_", " ").title()
    if phase.lower().startswith("closed"):
        phase = "Closed"
    c1.metric("Symbol", symbol)
    c2.metric("IST Time", ms.now_ist.strftime("%H:%M:%S"))
    c3.metric("Session", phase)
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
    st.markdown("**Supporting evidence**")
    reasons = explanation.get("reasons") or primary.reasons_simple or primary.reasons
    if reasons:
        for r in reasons:
            st.markdown(f"• {r}")
    else:
        st.caption("No detailed reasons available for this run.")

    rejected = explanation.get("rejected_signals") or (primary.raw or {}).get("rejected_signals") or []
    if rejected:
        with st.expander("Conflicting / de-emphasized signals", expanded=False):
            for r in rejected[:8]:
                st.markdown(f"• {r}")

    st.markdown("**Suggested action**")
    st.info(explanation.get("suggested_action", "Watch the market and manage risk."))

    st.markdown("**Trend**")
    st.write(explanation.get("trend_summary", primary.trend.title()))
    if explanation.get("regime") or primary.market_regime:
        st.caption(f"Regime: `{(explanation.get('regime') or primary.market_regime)}`")

    preferred = explanation.get("preferred_techniques") or (primary.raw or {}).get("preferred_techniques") or []
    if preferred:
        st.caption("Techniques emphasized: " + ", ".join(preferred[:8]))

    md = explanation.get("report_markdown") or (primary.raw or {}).get("report_markdown")
    if md:
        with st.expander("Full analyst report", expanded=False):
            st.markdown(md)

    if primary.raw.get("market_read") or (
        primary.source and "GENAI" in str(primary.source) and primary.raw.get("genai")
    ):
        with st.expander("Full AI market read", expanded=False):
            st.markdown(primary.raw.get("market_read") or str(primary.raw.get("genai")))


def render_news_panel(news_impacts: list | None, equity_news: list | None = None) -> None:
    """News intelligence panel with bullish/bearish/neutral impact."""
    st.markdown("##### News Intelligence")
    items = news_impacts or []
    if not items and equity_news:
        st.caption("Raw headlines loaded — impact scoring unavailable this run.")
        for h in equity_news[:6]:
            title = h.get("title") if isinstance(h, dict) else getattr(h, "title", str(h))
            st.markdown(f"• {title}")
        return
    if not items:
        st.caption("No recent headlines scored.")
        return
    for item in items[:8]:
        if hasattr(item, "to_dict"):
            d = item.to_dict()
        elif isinstance(item, dict):
            d = item
        else:
            continue
        impact = d.get("impact", "neutral")
        color = SIGNAL_COLORS["BUY"] if impact == "bullish" else (
            SIGNAL_COLORS["SELL"] if impact == "bearish" else SIGNAL_COLORS["HOLD"]
        )
        st.markdown(
            f"<span style='color:{color};font-weight:600'>{impact.upper()}</span> "
            f"({d.get('strength', 0):.0%}) — {d.get('headline', '')[:110]}",
            unsafe_allow_html=True,
        )


def render_risk_plan_panel(risk_plan: dict | None, primary: PredictionResult) -> None:
    """Risk management: R:R, stops, position sizing."""
    st.markdown("##### Risk Management")
    plan = risk_plan or (primary.raw or {}).get("risk_plan") or {}
    if not plan:
        st.caption(f"Risk level: {primary.risk_level}")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("R:R", f"1:{plan.get('risk_reward_ratio', 0)}")
    c2.metric("Position", f"{plan.get('position_size_pct', 0):.1f}%")
    c3.metric("Risk/trade", f"{plan.get('risk_per_trade_pct', 0):.2f}%")
    for note in (plan.get("notes") or [])[:3]:
        st.caption(note)


def render_scenarios_panel(scenarios: list | None) -> None:
    """Bullish / base / bearish probability scenarios."""
    st.markdown("##### Alternative Scenarios")
    if not scenarios:
        st.caption("No scenario paths this run.")
        return
    rows = []
    for s in scenarios:
        if hasattr(s, "to_dict"):
            d = s.to_dict()
        elif isinstance(s, dict):
            d = s
        else:
            continue
        rows.append(
            {
                "Scenario": str(d.get("name", "")).title(),
                "Target": f"₹{float(d.get('target_price', 0)):,.2f}",
                "Probability": f"{float(d.get('probability', 0)) * 100:.0f}%",
                "Summary": d.get("summary", ""),
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_strategy_master_panel(primary: PredictionResult) -> None:
    """Show Alpha/Beta/Gamma filters + mandatory master JSON output."""
    raw = primary.raw or {}
    strategies = raw.get("strategies") or {}
    master = raw.get("master_output") or {}
    if not strategies and not master:
        return

    st.markdown("##### Strategy Filters (Alpha / Beta / Gamma)")
    if strategies:
        st.caption(
            f"Master regime: **{strategies.get('master_regime', '—')}** · "
            f"Primary filter: **{strategies.get('primary_strategy', '—')}**"
        )
        rows = []
        for key in ("alpha", "beta", "gamma"):
            s = strategies.get(key) or {}
            if not s:
                continue
            rows.append(
                {
                    "Strategy": s.get("name") or key.title(),
                    "Mode": s.get("label") or "",
                    "Signal": s.get("prediction") or "FLAT",
                    "Active": "Yes" if s.get("active") else "No",
                    "Note": (s.get("rationale") or "")[:120],
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        gamma = strategies.get("gamma") or {}
        if gamma.get("divergence"):
            st.warning(
                "Gamma divergence: highly positive sentiment without a higher high "
                "(possible distribution)."
            )

    if master:
        pred = master.get("prediction", "FLAT")
        color = (
            SIGNAL_COLORS["BUY"]
            if pred == "LONG"
            else SIGNAL_COLORS["SELL"]
            if pred == "SHORT"
            else SIGNAL_COLORS["HOLD"]
        )
        st.markdown("##### Master Prediction (JSON schema)")
        st.markdown(
            f"""
            <div class="compare-card" style="border-color:{color}">
              <div><b>Prediction:</b> <span style="color:{color}">{pred}</span>
              · Confidence {float(master.get('confidence_score') or 0) * 100:.0f}%</div>
              <div><b>Regime:</b> {master.get('market_regime', '—')}</div>
              <div><b>Trigger:</b> ₹{float((master.get('execution_metrics') or {}).get('trigger_price') or 0):,.2f}
              · <b>TP:</b> ₹{float((master.get('execution_metrics') or {}).get('take_profit_target') or 0):,.2f}
              · <b>SL:</b> ₹{float((master.get('execution_metrics') or {}).get('stop_loss_level') or 0):,.2f}</div>
              <div><b>Rationale:</b> {master.get('technical_rationale', '')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Raw master JSON (parser-ready)", expanded=False):
            st.code(raw.get("master_output_json") or str(master), language="json")


def render_what_to_do_now(explanation: dict, primary: PredictionResult) -> None:
    """Dedicated 'What to do now' action box."""
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    action = explanation.get("suggested_action") or "Watch the market and manage risk."
    st.markdown("##### What to do now")
    st.markdown(
        f"""
        <div class="compare-card" style="border-color:{color}">
          <div style="font-size:1.1rem;font-weight:700;color:{color}">{primary.signal}</div>
          <div>{action}</div>
          <div style="margin-top:0.4rem;opacity:0.85">{explanation.get('price_range', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_agent_trace(trace: list | None) -> None:
    """Show which specialist agents ran and what they concluded."""
    if not trace:
        return
    with st.expander("Multi-agent desk (orchestrator trace)", expanded=False):
        for step in trace:
            if isinstance(step, dict):
                st.markdown(f"**{step.get('agent', 'Agent')}** — {step.get('summary', '')}")
            else:
                st.write(step)


def merge_auto_indicators(
    manual: dict[str, bool],
    auto_flags: dict[str, bool] | None,
    *,
    use_auto: bool,
) -> dict[str, bool]:
    """Blend user toggles with regime-selected indicators when auto mode is on."""
    if not use_auto or not auto_flags:
        return manual
    merged = dict(manual)
    for key, val in auto_flags.items():
        if key in merged and val:
            merged[key] = True
    return merged


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
    """Toggles for each indicator overlay (sidebar or main desk)."""
    flags = dict(DEFAULT_INDICATORS)
    labels = {
        "ema": "EMA 9/20/50",
        "sma": "SMA 20/50",
        "vwap": "VWAP",
        "bollinger": "Bollinger",
        "rsi": "RSI",
        "macd": "MACD",
        "volume": "Volume",
        "atr": "ATR",
        "adx": "ADX",
        "support_resistance": "S/R",
        "fibonacci": "Fib retrace",
        "fib_extension": "Fib ext",
    }
    keys = list(labels)
    if sidebar:
        st.sidebar.markdown("### Chart indicators")
        for key, label in labels.items():
            flags[key] = st.sidebar.checkbox(label, value=flags[key], key=f"chart_ind_{key}")
        return flags

    st.markdown("##### Chart filters")
    st.caption("Turn overlays on or off. These update the candlestick chart.")
    cols = st.columns(4)
    for i, key in enumerate(keys):
        flags[key] = cols[i % 4].checkbox(labels[key], value=flags[key], key=f"chart_ind_{key}")
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
    scenarios: list | None = None,
    chart_key: str | None = None,
    interval: str = "5m",
    window_label: str | None = None,
) -> None:
    """Render the professional candlestick chart."""
    c_a, c_b, c_c = st.columns(3)
    show_levels = c_a.checkbox("Show target & stop lines", value=True, key="chart_show_levels")
    show_history = c_b.checkbox("Show older predictions on the tape", value=False, key="chart_show_old_preds")
    show_scenarios = c_c.checkbox("Show bull / bear what-if paths", value=False, key="chart_show_scenarios")

    hist = history.load_projection_history(symbol, 40) if show_history else None
    comparison = history.load_comparison_records(symbol, limit=12) if show_history else None
    fib_levels = list(fib.retracements.values()) if fib and indicators.get("fibonacci") else []
    y0, y1 = chart_y_range(df_ist, projection, fib_levels)
    if primary.target_price:
        y0 = min(y0, float(primary.target_price) * 0.995)
        y1 = max(y1, float(primary.target_price) * 1.005)
    if primary.stop_loss:
        y0 = min(y0, float(primary.stop_loss) * 0.995)
        y1 = max(y1, float(primary.stop_loss) * 1.005)

    pred_start = None
    pred_end = None

    buy_signals, sell_signals, hold_signals = [], [], []
    if show_history:
        for rec in history.load_history(symbol, limit=25):
            pt = (rec.timestamp, rec.predicted_price)
            if rec.signal == "BUY":
                buy_signals.append(pt)
            elif rec.signal == "SELL":
                sell_signals.append(pt)
            else:
                hold_signals.append(pt)

    scenario_series = None
    if show_scenarios and scenarios:
        scenario_series = {}
        for s in scenarios:
            name = getattr(s, "name", None) or (s.get("name") if isinstance(s, dict) else None)
            series = getattr(s, "series", None)
            if name and series is not None and len(series):
                scenario_series[str(name)] = series

    news_markers = None

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
        stop_loss=primary.stop_loss,
        prediction_start=pred_start,
        prediction_end=pred_end,
        comparison_records=comparison,
        scenario_series=scenario_series,
        news_markers=news_markers,
        uirevision=chart_key or f"{symbol}-{today}",
        interval=interval,
        show_history=show_history,
        show_levels=show_levels,
        show_scenarios=show_scenarios,
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=chart_key or f"chart_{symbol}",
        config={
            "scrollZoom": not mobile,
            "displayModeBar": not mobile,
            "displaylogo": False,
            "responsive": True,
        },
    )
    if window_label:
        st.caption(window_label)
    with st.expander("How to read this chart", expanded=True):
        last_px = float(df_ist["Close"].iloc[-1]) if df_ist is not None and len(df_ist) else 0
        st.markdown(
            f"""
**Candles** are what already traded (green up, red down). Left of the dashed **Now** line is history.

**Gold dashed line** is not a second market — it is a straight-line **guess** from the last close
(₹{last_px:,.2f}) toward the AI target (₹{primary.predicted_price:,.2f}).

- **BUY** means the model leans higher; watch whether candles follow the gold path.
- **SELL** means the model leans lower.
- **HOLD** means no strong setup; the gold path is only a reference.

Horizontal **gold** = target. Horizontal **red dotted** = stop-loss. This is educational analysis, not a profit guarantee.
"""
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
