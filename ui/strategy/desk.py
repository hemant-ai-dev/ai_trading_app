"""Strategy desk: filters + analysis layout (submodel of strategy)."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from config.timeframes import PERIODS, TIMEFRAME_PRESETS, default_interval, intervals_for_period, label_for
from prediction import archive as pred_archive
from ui.chat_panel import render_desk_chat, render_task_composer
from ui.strategy.widgets import (
    collect_indicator_flags,
    merge_auto_indicators,
    render_accuracy_section,
    render_agent_trace,
    render_ai_explanation_panel,
    render_ai_signal_hero,
    render_compare_card,
    render_confidence_meter,
    render_fibonacci_panel,
    render_indicator_snapshot,
    render_insight_charts,
    render_main_chart,
    render_market_overview,
    render_news_panel,
    render_performance_strip,
    render_prediction_history,
    render_recent_analysis,
    render_risk_meter,
    render_risk_plan_panel,
    render_scenarios_panel,
    render_sentiment_card,
    render_strategy_master_panel,
    render_today_panel,
    render_trade_plan_panel,
    render_market_frames_panel,
    render_volume_analysis,
    render_what_to_do_now,
)

INDEX_PRESETS = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Sensex": "^BSESN",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "Custom": "custom",
}


def render_strategy_workspace(user: dict, *, theme_name: str) -> None:
    history = st.session_state["history_store"]

    f1, f2, f3, f4, f5 = st.columns([1.45, 1.7, 0.95, 0.95, 1.15])
    with f1:
        preset = st.selectbox("Symbol", list(INDEX_PRESETS.keys()), key="desk_symbol_preset")
    with f2:
        tf_choice = st.selectbox(
            "Timeframe",
            [row["label"] for row in TIMEFRAME_PRESETS],
            index=1,
            key="desk_timeframe",
        )
    with f3:
        auto_refresh = st.toggle("Auto-refresh", value=True, key="desk_auto_refresh")
    with f4:
        include_world = st.toggle("World news", value=True, key="desk_world_news")
    if preset == "Custom":
        stock = st.text_input("Ticker", "INFY.NS", key="desk_custom_ticker")
    else:
        stock = INDEX_PRESETS[preset]
    with f5:
        from workers.prediction_scheduler import is_watched, set_watch, watch_exists

        if not watch_exists(int(user["user_id"]), stock):
            set_watch(int(user["user_id"]), stock, True)
        live_pred = st.toggle(
            "Continuous AI predictions",
            value=is_watched(int(user["user_id"]), stock),
            key=f"desk_live_pred_{stock}",
            help="Background engine stores a timestamped prediction for this instrument every minute "
            "(1m/5m/15m/30m/60m/EOD horizons) and evaluates each against the real price at its target time.",
        )
        set_watch(int(user["user_id"]), stock, bool(live_pred))
    tf_row = next(row for row in TIMEFRAME_PRESETS if row["label"] == tf_choice)

    use_advanced = st.toggle("Advanced period / interval", value=False, key="desk_advanced_tf")
    if use_advanced:
        a1, a2 = st.columns(2)
        with a1:
            period = st.selectbox(
                "Period",
                PERIODS,
                index=PERIODS.index(tf_row["period"]) if tf_row["period"] in PERIODS else 1,
                key="desk_period",
            )
        allowed_iv = intervals_for_period(period)
        default_iv = tf_row["interval"] if tf_row["interval"] in allowed_iv else default_interval(period)
        iv_index = allowed_iv.index(default_iv) if default_iv in allowed_iv else 0
        with a2:
            interval = st.selectbox("Interval", allowed_iv, index=iv_index, key=f"desk_interval_{period}")
    else:
        period, interval = tf_row["period"], tf_row["interval"]

    with st.expander("Risk limits (theoretical size only)", expanded=False):
        st.caption("Used for position-size math. Never places an order. Leave capital at 0 if you do not want a size.")
        st.session_state.setdefault("risk_capital", 0.0)
        st.session_state.setdefault("risk_max_pct", 1.0)
        st.session_state.setdefault("risk_max_daily_pct", 3.0)
        st.session_state.setdefault("risk_max_positions", 3)
        st.session_state.setdefault("risk_max_instrument_pct", 25.0)
        st.session_state.setdefault("alert_setup", True)
        st.number_input("Available capital (₹)", min_value=0.0, step=1000.0, key="risk_capital")
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.number_input("Max risk / trade %", min_value=0.1, max_value=10.0, step=0.1, key="risk_max_pct")
        c_r2.number_input("Max daily loss %", min_value=0.1, max_value=20.0, step=0.1, key="risk_max_daily_pct")
        c_r3.number_input("Max simultaneous positions", min_value=1, max_value=20, step=1, key="risk_max_positions")
        st.number_input("Max exposure per instrument %", min_value=1.0, max_value=100.0, step=1.0, key="risk_max_instrument_pct")
        st.toggle("Desk alerts for SL / target / invalidation", key="alert_setup")

    with st.expander("Chart indicator filters", expanded=False):
        indicator_flags = collect_indicator_flags(sidebar=False)
        auto_indicators = st.toggle(
            "Auto-select indicators for the current regime",
            value=False,
            key="desk_auto_indicators",
            help="Let the analysis emphasize tools that fit the current market regime.",
        )

    @st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
    def render_dashboard() -> None:
        try:
            with st.spinner("Fetching live market data and running analysis…"):
                result = st.session_state["analysis"].analyze(
                    symbol=stock,
                    period=period,
                    interval=interval,
                    use_genai=False,
                    include_world_news=include_world,
                    user_id=int(user["user_id"]),
                )
        except Exception as exc:
            st.error(f"Analysis stopped before the chart could be drawn: {exc}")
            return

        if result.get("error"):
            st.warning(result["error"] + " Try another timeframe (weekends often have no 1-day session).")
            return
        if result.get("fallback_note"):
            st.info(result["fallback_note"])

        from workers.orchestrator import tick_open_tasks

        tick_open_tasks(
            int(user["user_id"]),
            {
                "market": st.session_state["analysis"].market,
                "analysis": st.session_state["analysis"],
                "default_symbol": stock,
            },
        )

        ms = result["market_status"]
        primary = result["primary"]
        explanation = result["explanation"]
        df_ist = result["df_ist"]
        live_line = result["live_line"]
        projection = result["projection"]
        latest = result["latest_price"]
        today = ms.now_ist.date()
        st.session_state["last_market_ai"] = {"symbol": stock, "spot": latest, "primary": primary}
        ctx = primary.indicator_snapshot or {}
        fib = ctx.get("fibonacci")
        sr = ctx.get("support_resistance")
        scenarios = result.get("scenarios") or []
        news_impacts = result.get("news_impacts") or (primary.raw or {}).get("news_impacts")
        news_agg = (primary.raw or {}).get("news_aggregate") or {}
        risk_plan = (primary.raw or {}).get("risk_plan")
        agent_trace = (primary.raw or {}).get("agent_trace")
        chart_flags = merge_auto_indicators(
            indicator_flags, result.get("indicator_flags"), use_auto=auto_indicators
        )
        # Persistent yellow line: rebuild overlays from the SQLite archive.
        try:
            sql_hist = pred_archive.load_projection_paths(int(user["user_id"]), stock, 40)
            sql_cmp = pred_archive.load_evaluated_records(int(user["user_id"]), stock, 12)
        except Exception:
            sql_hist, sql_cmp = None, None
        bars = 0 if df_ist is None else len(df_ist)
        if df_ist is not None and bars:
            t0, t1 = df_ist.index[0], df_ist.index[-1]
            start_txt = t0.strftime("%d %b %Y %H:%M") if hasattr(t0, "strftime") else str(t0)
            end_txt = t1.strftime("%d %b %Y %H:%M") if hasattr(t1, "strftime") else str(t1)
            window_label = (
                f"Date filter: {label_for(period, interval)} · "
                f"{start_txt} → {end_txt} IST · {bars} candles"
            )
        else:
            window_label = f"Date filter: {label_for(period, interval)} · no candles"

        st.markdown("##### Market overview")
        render_market_overview(ms, latest, primary, stock, bars, window_label)

        top, side = st.columns([1.65, 1.0], gap="small")
        with top:
            render_ai_signal_hero(primary, latest, explanation)
            chart_id = f"chart_{stock}_{period}_{interval}_{theme_name}_{bars}"
            render_main_chart(
                df_ist=df_ist,
                live_line=live_line,
                projection=projection,
                fib=fib,
                sr=sr,
                primary=primary,
                history=history,
                symbol=stock,
                today=today,
                mobile=True,
                theme_name=theme_name,
                indicators=chart_flags,
                scenarios=scenarios,
                chart_key=chart_id,
                interval=interval,
                window_label=None,
                pred_track=result.get("pred_track"),
                actual_track=result.get("actual_track"),
                pred_meta=result.get("pred_meta"),
                sql_projection=None if result.get("pred_meta") is not None and len(result.get("pred_meta")) else sql_hist,
                sql_comparison=sql_cmp,
            )
        with side:
            render_today_panel(latest=latest, primary=primary, window_label=window_label)

        tab_desk, tab_insights, tab_detail, tab_opt, tab_chat, tab_history, tab_accuracy = st.tabs(
            [
                "Tape",
                "Insights",
                "Analysis",
                "Options AI",
                "Chat & tasks",
                "History",
                "Accuracy",
            ]
        )
        with tab_desk:
            st.caption(window_label)
            st.markdown("##### Market AI — predicted vs actual (session ticks)")
            from prediction.session_tape import SessionTapeStore

            tape = SessionTapeStore(history.path)
            cmp_df = tape.comparison_table(stock, today, limit=24)
            if cmp_df.empty:
                st.caption("Ticks appear about every minute while Auto-refresh is on and the cash session is open.")
            else:
                st.dataframe(cmp_df, use_container_width=True, hide_index=True, height=240)
            perf = tape.performance(stock, today)
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Direction accuracy", f"{perf.get('direction_accuracy_pct') or '—'}%")
            p2.metric("Close", perf.get("close") or 0)
            p3.metric("Incorrect direction", perf.get("direction_incorrect") or 0)
            p4.metric("Avg |error|", perf.get("avg_abs_error") if perf.get("avg_abs_error") is not None else "—")

        with tab_insights:
            render_insight_charts(
                symbol=stock,
                df_ist=df_ist,
                ctx=ctx,
                history=history,
                news_agg=news_agg,
                latest=latest,
                primary=primary,
            )
            render_performance_strip(history, stock)

        with tab_detail:
            q1, q2 = st.columns([1.35, 1.0], gap="medium")
            with q1:
                render_ai_explanation_panel(primary, explanation)
                render_strategy_master_panel(primary)
                latest_eval = history.latest_evaluated(stock)
                render_compare_card(primary, latest, latest_eval)
                render_scenarios_panel(scenarios)
                render_agent_trace(agent_trace)
                render_indicator_snapshot(ctx)
                render_volume_analysis(ctx)
                render_fibonacci_panel(fib)
            with q2:
                atr = float(ctx.get("atr") or 0)
                render_what_to_do_now(explanation, primary)
                render_risk_meter(primary.risk_level, atr, latest)
                render_risk_plan_panel(risk_plan, primary)
                render_trade_plan_panel(result.get("trade_plan"))
                render_market_frames_panel(result.get("market_frames"))
                with st.expander("Setup screener (free-data universe scan)", expanded=False):
                    st.caption(
                        "Ranks a fixed universe on confirmation, liquidity proxy and R:R from free daily data. "
                        "Decision support only — not a buy list."
                    )
                    if st.button("Scan universe", key=f"screener_{stock}"):
                        from api import gateway as _gw

                        with st.spinner("Scanning universe (free daily bars)..."):
                            scan = _gw.get_screener()
                        if scan.get("ok") and scan.get("rows"):
                            import pandas as _pd

                            srows = scan["rows"]
                            sshow = _pd.DataFrame(
                                [
                                    {
                                        "Symbol": r.get("symbol"),
                                        "Signal": r.get("signal"),
                                        "Status": r.get("status"),
                                        "Score": r.get("screen_score"),
                                        "R:R": r.get("rr"),
                                        "Confidence": r.get("confidence"),
                                        "Entry": f"{r.get('entry_low')}–{r.get('entry_high')}",
                                        "SL": r.get("stop"),
                                        "T1": r.get("target1"),
                                    }
                                    for r in srows
                                ]
                            )
                            st.dataframe(sshow, use_container_width=True, hide_index=True)
                            st.caption(scan.get("disclaimer") or "")
                        elif scan.get("ok"):
                            st.info("Scan returned no setups this run.")
                        else:
                            st.warning(scan.get("error") or "Universe scan unavailable.")
                render_sentiment_card(news_agg, news_impacts)
                render_news_panel(news_impacts, result.get("equity_news"))
                render_recent_analysis(history, stock)
                render_confidence_meter(primary.confidence, primary.signal)
                st.markdown("##### Market trend")
                st.write(f"**{(ctx.get('trend_dir') or primary.trend).title()}** · Regime: `{(primary.market_regime or '').replace('_', ' ')}`")
                candle_pats = (primary.raw or {}).get("candle_patterns") or ctx.get("patterns") or []
                chart_pats = (primary.raw or {}).get("chart_patterns") or []
                if candle_pats or chart_pats:
                    st.markdown("##### Pattern recognition")
                    for p in candle_pats[:6]:
                        if isinstance(p, dict):
                            st.markdown(f"• {p.get('name')} — {p.get('reason', '')}")
                        else:
                            st.markdown(f"• {p}")
                    for p in chart_pats[:6]:
                        if isinstance(p, dict):
                            st.markdown(f"• {p.get('name')} — {p.get('reason', '')}")
                        else:
                            st.markdown(f"• {p}")

        with tab_opt:
            st.markdown("##### Option Chain AI")
            st.caption("Full chain, expiry picker, premium chart, and history live in the Options workspace. Prediction and trade recommendation stay separate.")
            st.write(
                f"Market AI on **{stock}**: last ₹{latest:,.2f} · predicted ₹{primary.predicted_price:,.2f} · "
                f"{primary.signal} · {primary.confidence:.0f}% confidence · educational only."
            )
            st.info("Open **Options** in the top nav to load Yahoo expiries, CE/PE tables, and the recommendation box.")

        with tab_chat:
            render_desk_chat(user, result, stock)
            st.divider()
            render_task_composer(user, stock)

        with tab_history:
            st.markdown("#### Prediction history")
            st.caption(
                "Each row stores timestamp, market price, AI signal, confidence, "
                "actual outcome, accuracy, and simulated P/L for this account."
            )
            render_prediction_history(stock, history)
            sql_rows = pred_archive.list_predictions(int(user["user_id"]), stock, limit=40)
            if sql_rows:
                st.markdown("##### Append-only SQLite archive (TPrediction)")
                st.dataframe(
                    [
                        {
                            "When": r["CreatedAt"],
                            "Price": r["MarketPrice"],
                            "Signal": r["Signal"],
                            "Predicted": r["PredictedPrice"],
                            "Range": f"{r['PriceLow']}–{r['PriceHigh']}",
                            "Conf": r["Confidence"],
                            "Regime": r["MarketRegime"],
                            "Actual": r["ActualPrice"],
                        }
                        for r in sql_rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        with tab_accuracy:
            st.markdown("#### Accuracy statistics")
            render_accuracy_section(stock, history, theme_name=theme_name, user_id=int(user["user_id"]))

    render_dashboard()
