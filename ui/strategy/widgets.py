"""Dashboard UI components for the trading terminal."""

from __future__ import annotations

from typing import Any
import html

import pandas as pd
import streamlit as st

from charts.accuracy_dashboard import build_accuracy_dashboard
from charts.price_chart import DEFAULT_INDICATORS, build_trading_chart
from level_plan import chart_y_range
from prediction.accuracy import compute_accuracy_metrics
from prediction.history_store import PredictionHistoryStore
from prediction.models import PredictionResult
from ui.smart_box import build_smart_box
from . import viz


SIGNAL_COLORS = {"BUY": "#2ee6a6", "SELL": "#ff5d7a", "HOLD": "#c084fc"}


def _inr(value: float) -> str:
    return f"₹{float(value):,.2f}"


def _hero_tiles(items: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<div class="hero-tile"><span>{html.escape(label)}</span><b>{html.escape(val)}</b></div>'
        for label, val in items
    )
    return f'<div class="hero-tiles">{cells}</div>'


def render_ai_signal_hero(primary: PredictionResult, latest: float, explanation: dict | None = None) -> None:
    """Primary decision card: signal, entry, target, stop, confidence, risk."""
    box = build_smart_box(primary, latest)
    color = SIGNAL_COLORS.get(box["signal"], "#94a3b8")
    explanation = explanation or {}
    reasons = explanation.get("reasons") or primary.reasons_simple or primary.reasons or []
    why = str(reasons[0]) if reasons else box["summary"]
    if box["signal"] == "HOLD":
        tiles = _hero_tiles(
            [
                ("Watch buy near", _inr(box["consider_buy"])),
                ("Watch sell near", _inr(box["consider_sell"])),
                ("Confidence", f"{box['confidence']:.0f}%"),
                ("Risk", str(box["risk_level"])),
            ]
        )
        hold_note = ""
    else:
        tiles = _hero_tiles(
            [
                ("Entry", _inr(box["entry"])),
                ("Target", _inr(box["target"])),
                ("Stop-loss", _inr(box["stop"])),
                ("Confidence", f"{box['confidence']:.0f}%"),
                ("Risk", str(box["risk_level"])),
            ]
        )
        hold_note = ""
    st.markdown(
        f"""
<div class="signal-hero" style="border-color:{color}">
  <div class="smart-kicker">AI SIGNAL</div>
  <div class="smart-signal" style="color:{color}">{html.escape(str(box["headline"]))}</div>
  {tiles}
  {hold_note}
  <p class="hero-why">{html.escape(why)} · {html.escape(str(box["regime"])).replace("_", " ")} · {html.escape(str(box["trend"]))} · not a profit guarantee</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_market_overview(ms: Any, latest: float, primary: PredictionResult, symbol: str, bars: int, window_label: str) -> None:
    color = SIGNAL_COLORS.get(primary.signal, "#95a5a6")
    phase = ms.phase.value.replace("_", " ").title()
    if phase.lower().startswith("closed"):
        phase = "Closed"
    regime = (primary.market_regime or "—").replace("_", " ").title()
    trend = (primary.trend or "—").title()
    st.markdown(
        f"""
<div class="kpi-strip" style="border-color:{color}">
  <div><span>Symbol</span><b>{html.escape(str(symbol))}</b></div>
  <div><span>Last</span><b>{_inr(latest)}</b></div>
  <div><span>Session</span><b>{html.escape(phase)}</b></div>
  <div><span>IST</span><b>{html.escape(ms.now_ist.strftime("%H:%M:%S"))}</b></div>
  <div><span>Trend</span><b>{html.escape(trend)}</b></div>
  <div><span>Regime</span><b>{html.escape(regime)}</b></div>
</div>
<p class="hero-why" style="margin-top:0.35rem">{html.escape(window_label)}</p>
""",
        unsafe_allow_html=True,
    )


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


def render_today_panel(
    *,
    latest: float,
    primary: PredictionResult,
    window_label: str,
) -> None:
    st.markdown('<div class="glass-kicker">Today’s AI read</div>', unsafe_allow_html=True)
    st.plotly_chart(
        viz.prediction_confidence_donut(primary),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    regime = (primary.market_regime or "—").replace("_", " ").title()
    st.markdown(
        f"""
<div class="stat-grid">
  <div class="stat-tile"><span>Last close</span><b>₹{latest:,.2f}</b></div>
  <div class="stat-tile"><span>Target</span><b>₹{primary.target_price:,.2f}</b></div>
  <div class="stat-tile"><span>Stop</span><b>₹{primary.stop_loss:,.2f}</b></div>
  <div class="stat-tile"><span>Regime</span><b>{html.escape(regime)}</b></div>
  <div class="stat-tile"><span>Trend</span><b>{html.escape((primary.trend or "—").title())}</b></div>
  <div class="stat-tile"><span>Risk</span><b>{html.escape(str(primary.risk_level))}</b></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_insight_charts(
    *,
    symbol: str,
    df_ist: pd.DataFrame,
    ctx: dict[str, Any],
    history: PredictionHistoryStore,
    news_agg: dict | None,
    latest: float | None = None,
    primary: PredictionResult | None = None,
) -> None:
    rsi = None
    try:
        rsi = float((ctx or {}).get("rsi"))
    except (TypeError, ValueError):
        rsi = None
    st.markdown(
        '<div class="glass-kicker">Insight charts</div>'
        '<p class="hello-sub" style="margin-bottom:0.6rem">Volume, conviction mix, RSI, path, simulated P/L, news, and levels — same analysis, easier to scan.</p>',
        unsafe_allow_html=True,
    )
    r1, r2, r3 = st.columns(3, gap="medium")
    with r1:
        st.plotly_chart(viz.volume_profile(df_ist), use_container_width=True, config={"displayModeBar": False})
    with r2:
        st.plotly_chart(viz.signal_mix_donut(history, symbol), use_container_width=True, config={"displayModeBar": False})
    with r3:
        st.plotly_chart(viz.rsi_gauge(rsi), use_container_width=True, config={"displayModeBar": False})
    s1, s2, s3 = st.columns(3, gap="medium")
    with s1:
        st.plotly_chart(viz.close_spark(df_ist, "Close (daily path)"), use_container_width=True, config={"displayModeBar": False})
    with s2:
        st.plotly_chart(viz.pnl_bars(history, symbol), use_container_width=True, config={"displayModeBar": False})
    with s3:
        st.plotly_chart(viz.news_sentiment_donut(news_agg), use_container_width=True, config={"displayModeBar": False})
    t1, t2 = st.columns(2, gap="medium")
    with t1:
        st.plotly_chart(viz.ma_ribbon(df_ist), use_container_width=True, config={"displayModeBar": False})
    with t2:
        last = latest
        if last is None and df_ist is not None and not df_ist.empty:
            last = float(df_ist["Close"].iloc[-1])
        if primary is not None and last is not None:
            st.plotly_chart(viz.price_levels_map(float(last), primary), use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption("Price map appears after a successful analysis run.")
    tilt = str((news_agg or {}).get("tilt") or "neutral").title()
    st.caption(f"News tilt **{tilt}** · educational charts only — not a profit guarantee.")
    st.markdown("##### Recent calls")
    df = history.to_dataframe(symbol, limit=10)
    if df.empty:
        st.caption("No saved calls yet for this symbol.")
    else:
        keep = [c for c in ("timestamp", "signal", "confidence", "predicted_price", "accuracy_label", "profit_loss_sim_pct") if c in df.columns]
        st.dataframe(df[keep], use_container_width=True, hide_index=True, height=180)


def render_performance_strip(history: PredictionHistoryStore, symbol: str) -> None:
    metrics = compute_accuracy_metrics(symbol, history)
    a, b, c, d = st.columns(4)
    a.metric("Win rate", f"{metrics['win_rate_pct']}%")
    b.metric("Accuracy ±1%", f"{metrics['accuracy_pct']}%")
    c.metric("Evaluated", int(metrics["evaluated"]))
    d.metric("P/L sim", f"{metrics['profit_loss_sim_pct']}%")
    st.caption(f"Performance for {symbol} on this account · educational simulation, not a profit guarantee")


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


def render_trade_plan_panel(plan: dict | None) -> None:
    """Potential setup from the analyst — existing card language, educational only."""
    if not plan:
        return
    st.markdown("##### Potential setup")
    st.caption(plan.get("disclaimer") or "Model path, not a guaranteed outcome.")
    a, b, c, d = st.columns(4)
    a.metric("Status", plan.get("status") or "—")
    b.metric("Direction", plan.get("direction") or "—")
    c.metric("R:R", f"1:{plan.get('rr')}" if plan.get("rr") is not None else "—")
    d.metric("Model probability", f"{plan.get('probability') or 0:.0f}%")
    st.write(
        f"**{plan.get('name') or plan.get('symbol')}** last ₹{float(plan.get('spot') or 0):,.2f} · "
        f"entry ₹{plan.get('entry_low')}–₹{plan.get('entry_high')} · SL ₹{plan.get('stop')} · "
        f"T1 ₹{plan.get('target1')} · T2 ₹{plan.get('target2')}"
    )
    st.caption(plan.get("entry_reason") or "")
    st.caption(plan.get("stop_reason") or "")
    st.caption(plan.get("target_reason") or "")
    st.caption(plan.get("exit_condition") or "")
    sized = plan.get("sizing") or {}
    if sized.get("warning"):
        st.warning(str(sized["warning"]) + " Not an executed order.")
    elif sized.get("configured"):
        st.caption(
            f"Theoretical size {sized.get('qty')} (lot {sized.get('lot_size')}) · "
            f"risk ₹{sized.get('risk_rupees')} of ₹{sized.get('budget_rupees')} budget."
        )
    elif not sized.get("configured"):
        st.caption(sized.get("warning") or "Configure capital in Risk limits to see a theoretical size.")
    status = str(plan.get("status") or "")
    if status in ("STOP LOSS", "TARGET 1", "TARGET 2", "INVALIDATED") and st.session_state.get("alert_setup", True):
        st.info(f"Setup status **{status}**. This is a desk alert, not proof that an order was filled.")
    rel = plan.get("strategy_reliability") or {}
    st.caption(
        f"Strategy **{plan.get('strategy')}** · {rel.get('note') or ''} "
        f"Completed sample {rel.get('sample') or 0}."
    )


def render_market_frames_panel(frames: dict | None) -> None:
    if not frames or not frames.get("ok"):
        return
    st.markdown("##### Market context (from available bars)")
    cur = frames.get("current") or {}
    day = frames.get("daily") or {}
    week = frames.get("weekly") or {}
    st.write(
        f"OHLC ₹{cur.get('open')} / {cur.get('high')} / {cur.get('low')} / {cur.get('close')} · "
        f"prev close ₹{cur.get('previous_close')} · Δ {cur.get('change')} ({cur.get('pct_change')}%)"
    )
    st.caption(
        f"Daily: prev H/L ₹{day.get('previous_high')} / ₹{day.get('previous_low')} · "
        f"S/R ₹{day.get('recent_support')} / ₹{day.get('recent_resistance')}"
    )
    st.caption(
        f"Weekly trend {week.get('trend')} · week close ₹{week.get('close')} · "
        f"prior week ₹{week.get('previous_week_close')} · longer-term { (frames.get('longer_term') or {}).get('trend') }"
    )


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
                "Direction": d.get("direction") or "—",
                "Target": f"₹{float(d.get('target_price', 0)):,.2f}",
                "Probability": f"{float(d.get('probability', 0)) * 100:.0f}%",
                "Trigger": d.get("trigger") or d.get("summary", ""),
                "Invalidation": d.get("invalidation") or "",
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
    pred_track=None,
    actual_track=None,
    sql_projection=None,
    sql_comparison=None,
    pred_meta=None,
) -> None:
    """Render the professional candlestick chart."""
    c_a, c_b, c_c = st.columns(3)
    show_levels = c_a.checkbox("Show target & stop lines", value=True, key="chart_show_levels")
    show_history = c_b.checkbox("Show older AI paths", value=True, key="chart_show_old_preds")
    show_scenarios = c_c.checkbox("Show bull / bear what-if paths", value=False, key="chart_show_scenarios")

    # Persistent store first: the yellow line is rebuilt from SQLite TPrediction.
    if show_history:
        if sql_projection is not None and not sql_projection.empty:
            hist = sql_projection
        else:
            hist = history.load_projection_history(symbol, 40)
        comparison = sql_comparison if sql_comparison else history.load_comparison_records(symbol, limit=12)
    else:
        hist = None
        comparison = None
    fib_levels = list(fib.retracements.values()) if fib and indicators.get("fibonacci") else []
    y0, y1 = chart_y_range(df_ist, projection, fib_levels)
    for series in (pred_track, actual_track, live_line):
        if series is not None and getattr(series, "empty", True) is False and len(series):
            y0 = min(y0, float(series.min()))
            y1 = max(y1, float(series.max()))
    if pred_meta is not None and not getattr(pred_meta, "empty", True):
        y0 = min(y0, float(pred_meta["predicted_price"].min()))
        y1 = max(y1, float(pred_meta["predicted_price"].max()))
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
        pred_track=pred_track,
        actual_track=actual_track,
        pred_meta=pred_meta,
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
    with st.expander("How to read this chart", expanded=False):
        st.markdown(
            f"""
**Candles** are already-traded prices (green up, red down).

**Green actual line** is the last market print at each refresh.

**Solid yellow line** is the stored forecast for each target time, rebuilt from the database. It does not change when the actual price prints.

**Dashed yellow marks** are forecasts whose target time is still ahead.

**Dashed path from the last close** is the current scenario path — a guess, not extra history.

Horizontal **gold** = target. Horizontal **red dotted** = stop-loss. Educational analysis only, not a profit guarantee.
"""
        )


def render_prediction_history(symbol: str, history: PredictionHistoryStore) -> None:
    """Full prediction history table with P/L simulation."""
    df = history.to_dataframe(symbol, limit=100)
    if df.empty:
        st.info(
            "No legacy file rows for this symbol. Permanent forecasts are in the archive table, "
            "written by continuous prediction — not by refreshing this chart."
        )
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


def render_accuracy_section(symbol: str, history: PredictionHistoryStore, theme_name: str = "dark", user_id: int | None = None) -> None:
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

    if user_id:
        _render_sql_prediction_stats(symbol, user_id)


def _render_sql_prediction_stats(symbol: str, user_id: int) -> None:
    """Performance from the permanent SQLite store — never fabricated."""
    from prediction import archive

    st.divider()
    st.markdown("##### Stored prediction performance (SQLite archive)")
    try:
        stats = archive.performance_stats(int(user_id), symbol)
    except Exception as exc:
        st.warning(f"Prediction statistics unavailable: {exc}")
        return
    if not stats["total_predictions"]:
        st.caption("No stored predictions for this instrument yet. Continuous prediction writes a row each minute while the market is open and this symbol is watched.")
        return
    a, b, c, d, e, f = st.columns(6)
    a.metric("Total", stats["total_predictions"])
    b.metric("Pending", stats["pending"])
    c.metric("Evaluated", stats["evaluated"])
    d.metric("Direction acc.", f"{stats['direction_accuracy_pct']}%" if stats["direction_accuracy_pct"] is not None else "—")
    e.metric("MAE (pts)", stats["mean_abs_error"] if stats["mean_abs_error"] is not None else "—")
    f.metric("MAPE %", stats["mean_abs_pct_error"] if stats["mean_abs_pct_error"] is not None else "—")
    st.caption(
        f"Range hits: {stats['range_hits']} of {stats['direction_total']} evaluated "
        f"({stats['range_pct'] or 0}%). Period {stats['period_from']} → {stats['period_to']}. "
        "Signed error is actual minus predicted. Percentage error uses the price at generation "
        "as the denominator. Direction and range are scored separately. "
        "These figures describe stored forecasts only — not profitability."
    )
    cal = stats.get("calibration") or {}
    base = stats.get("baselines") or {}
    with st.expander("Calibration vs baselines (stored evaluations)", expanded=False):
        st.caption(cal.get("note") or "Insufficient probability samples.")
        if cal.get("n"):
            st.write(
                f"n={cal.get('n')} · Brier {cal.get('brier')} · log loss {cal.get('log_loss')} · "
                f"ECE {cal.get('ece')} · RMSE {cal.get('rmse')}"
                + (" · preliminary" if cal.get("preliminary") else "")
            )
        st.caption(base.get("note") or "")
        if base.get("n"):
            st.write(
                f"Model MAE {base.get('model_mae')} vs no-change MAE {base.get('no_change_mae')} "
                f"(beats no-change: {base.get('beats_no_change')}) · n={base.get('n')}"
            )
        caution = stats.get("regime_caution") or []
        if caution:
            st.dataframe(caution, use_container_width=True, hide_index=True)
    errs = stats.get("error_over_time") or []
    if errs:
        with st.expander("Error over time", expanded=False):
            st.dataframe(
                [
                    {
                        "Evaluated": r.get("EvaluatedAt"),
                        "Horizon": r.get("Timeframe"),
                        "Regime": r.get("MarketRegime"),
                        "Model": r.get("model_version"),
                        "Abs error": r.get("AbsError"),
                        "Error %": r.get("ErrorPct"),
                        "Direction": r.get("DirectionOk"),
                        "In range": r.get("RangeOk"),
                    }
                    for r in errs[-40:]
                ],
                use_container_width=True,
                hide_index=True,
            )
    for title, key in (
        ("By horizon", "by_timeframe"),
        ("By market regime", "by_regime"),
        ("By model version", "by_model"),
        ("By instrument", "by_symbol"),
    ):
        rows = stats.get(key) or []
        if not rows:
            continue
        with st.expander(title, expanded=(key == "by_timeframe")):
            st.dataframe(
                [
                    {
                        "Key": r.get("key") or "—",
                        "Evaluated": r.get("n"),
                        "Direction acc. %": r.get("direction_accuracy_pct"),
                        "MAE": r.get("mae"),
                        "MAPE %": r.get("mape"),
                        "In range": r.get("range_hits"),
                    }
                    for r in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
