import hashlib
import json
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.loader import load_settings, reload_settings
from db.sql_config import SqlConfigLoader
from data_fetch import get_stock_data, today_live_series
from db.sql_store import SOURCE_GENAI, SOURCE_RULE, SqlStore, _ts_ist_naive
from genai_predictor import build_indicators_summary, build_logic_snapshot, genai_brain_prediction
from indicators import apply_indicators
from intraday_forecast import build_comparison_series, ensure_ist_index
from level_plan import chart_y_range, snapshot_levels
from market_calendar import format_market_context_for_llm, get_market_status
from market_intel import format_headlines_indexed_for_prompt, news_digest_for_cache
from providers.llm_openai import NullLLM
from providers.registry import build_llm_provider, build_news_intel_provider
from signal_engine import get_signal
from ui.audit_tables import render_audit_detail_tables, render_audit_summary
from ui.chart_builder import build_live_prediction_chart
from ui.signal_panel import render_signal_decision_block
from ui.styles import inject_responsive_css

SETTINGS = load_settings()
IST = ZoneInfo("Asia/Kolkata")
SQL_STORE = SqlStore(SETTINGS)
SQL_CFG = SqlConfigLoader(SQL_STORE)


def _build_llm():
    return build_llm_provider(SETTINGS)


def _load_intel_cached(symbol: str, include_world_rss: bool):
    news_cfg = SETTINGS.get("news", {}).get("yahoo_rss") or {}
    ttl_sec = float(news_cfg.get("intel_cache_ttl_seconds") or 600)
    key = f"intel_v1|{symbol.upper()}|{include_world_rss}"
    entry = st.session_state.get(key)
    now = time.time()
    if entry and (now - entry["ts"]) < ttl_sec:
        return entry["equity"], entry["world"]
    provider = build_news_intel_provider(SETTINGS)
    equity, world = provider.gather(symbol.strip(), include_world_rss)
    st.session_state[key] = {"ts": now, "equity": equity, "world": world}
    return equity, world


def _cached(key: str, fetch_fn):
    if st.session_state.get("ck") == key and st.session_state.get("cv") is not None:
        return st.session_state.cv
    data = fetch_fn()
    st.session_state.ck = key
    st.session_state.cv = data
    return data


st.set_page_config(
    page_title="Angad Gen AI Desk",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_responsive_css()

st.title("🧠 Angad — Gen AI Prediction Desk")
st.caption("Monitor predictions · All APIs & settings loaded from SQL")

st.sidebar.header("⚙ Control")
if st.sidebar.button("Reload config from SQL"):
    SETTINGS = reload_settings()
    SQL_STORE = SqlStore(SETTINGS)
    st.session_state["angad_sql_status"] = "Config reloaded from SQL"
index_presets = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Sensex": "^BSESN",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Custom": "custom",
}
preset = st.sidebar.selectbox("Symbol", list(index_presets.keys()))
stock = st.sidebar.text_input("Ticker", "INFY.NS") if preset == "Custom" else index_presets[preset]
period = st.sidebar.selectbox("Period", ["1d", "5d", "1mo"], index=1)
interval = st.sidebar.selectbox("Interval", ["1m", "5m", "15m", "1h"], index=1)
auto_refresh = st.sidebar.toggle("Auto-refresh ~60s", value=True)
include_world_rss = st.sidebar.toggle("World RSS", value=True)
st.session_state.angad_mobile_mode = st.sidebar.toggle("Compact chart (mobile)", value=False)
genai_primary = st.sidebar.toggle("Gen AI as primary prediction", value=True)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_board():
    ms = get_market_status()
    llm = _build_llm()
    genai_on = not isinstance(llm, NullLLM)

    health = SQL_CFG.health()
    c1, c2, c3 = st.columns(3)
    c1.metric("IST", ms.now_ist.strftime("%H:%M"))
    c2.metric("Session", ms.phase.value.replace("_", " "))
    c3.metric("Data store", "Connected" if health.get("ok") else "Check SQL")

    with st.spinner("Loading…"):
        df = get_stock_data(stock, period, interval)
        equity_news, world_news = _load_intel_cached(stock, include_world_rss)

    if df.empty:
        st.warning("No market data.")
        return

    df = apply_indicators(df)
    df_ist = ensure_ist_index(df)
    rule = get_signal(df)
    latest = float(df["Close"].iloc[-1])
    lv = snapshot_levels(df, rule)
    logic_snap = build_logic_snapshot(df, rule)

    try:
        purge = SQL_STORE.run_retention_purge_if_due(min_hours_between=24)
        if purge and purge.get("deleted", 0) > 0:
            st.session_state["angad_purge_note"] = (
                f"Retention: removed {purge['deleted']} rows older than {purge['retention_months']} months"
            )
        n_bars = SQL_STORE.upsert_market_bars(stock, df_ist, interval)
        st.session_state["angad_sql_status"] = f"Saved {n_bars} bars → SQL"
        st.session_state.pop("angad_sql_error", None)
    except Exception as ex:
        st.session_state["angad_sql_error"] = str(ex)

    today = ms.now_ist.date()
    anchor_key = f"anchor|{stock}|{today}"
    today_slice = df_ist.loc[df_ist.index.map(lambda t: t.date()) == today]
    if anchor_key not in st.session_state and len(today_slice) > 0:
        st.session_state[anchor_key] = {"anchor_price": float(today_slice["Close"].iloc[0])}
    anchor = st.session_state.get(anchor_key)

    _, rule_proj, cmp_note = build_comparison_series(df_ist, float(rule["target"]), ms, anchor)
    live_line = today_live_series(df_ist, ms)
    if len(live_line) == 0 and len(today_slice) > 0:
        live_line = today_slice["Close"]

    try:
        SQL_STORE.upsert_live_bars(stock, live_line)
    except Exception:
        pass

    headline_block, _ = format_headlines_indexed_for_prompt(equity_news, world_news)
    summary = build_indicators_summary(df)
    market_ctx = format_market_context_for_llm(ms)
    ref_json = json.dumps({**lv, "rule": rule}, ensure_ascii=False)
    digest_hash = hashlib.sha256(news_digest_for_cache(equity_news, world_news).encode()).hexdigest()[:24]

    brain = None
    if genai_on:
        bkey = f"brain|{stock}|{latest:.2f}|{ms.phase}|{digest_hash}"

        def _fetch_brain():
            return genai_brain_prediction(
                stock=stock,
                df=df,
                rule_result=rule,
                indicators_summary=summary,
                market_context=market_ctx,
                headline_block=headline_block,
                reference_levels_json=ref_json,
                ms=ms,
                llm=llm,
                settings=SETTINGS,
            )

        brain = _cached(bkey, _fetch_brain)

    use_genai = bool(brain and genai_primary)
    primary_signal = brain["signal"] if use_genai else rule["signal"]
    primary_conf = brain["confidence"] if use_genai else rule["confidence"]
    primary_target = brain["target"] if use_genai else rule["target"]
    primary_stop = brain["stop_loss"] if use_genai else rule["stop_loss"]
    primary_reason = (brain.get("market_read") or "") if use_genai else rule["reason"]
    primary_score = rule.get("score") if not use_genai else None
    pred_series = brain.get("projection_series") if use_genai else rule_proj
    primary_source = SOURCE_GENAI if use_genai else SOURCE_RULE
    source_label = "Gen AI Brain" if use_genai else "Rule engine (reference)"

    try:
        if use_genai and pred_series is not None and len(pred_series) > 0:
            model = (SETTINGS.get("llm", {}).get("openai") or {}).get("model_json", "gpt")
            SQL_STORE.save_prediction(
                stock=stock,
                source_type=SOURCE_GENAI,
                is_primary=True,
                model_name=model,
                signal=brain["signal"],
                confidence=brain["confidence"],
                stop_loss=brain["stop_loss"],
                target=brain["target"],
                reason=primary_reason[:2000],
                market_phase=ms.phase.value,
                period=period,
                interval=interval,
                last_close=latest,
                proj_series=pred_series,
                logic_snapshot={**logic_snap, "genai_output": brain.get("raw_json")},
                genai_brain=brain,
            )
        elif pred_series is not None and len(pred_series) > 0:
            SQL_STORE.save_prediction(
                stock=stock,
                source_type=SOURCE_RULE,
                is_primary=True,
                signal=rule["signal"],
                confidence=rule["confidence"],
                score=rule.get("score"),
                stop_loss=rule["stop_loss"],
                target=rule["target"],
                reason=rule["reason"],
                market_phase=ms.phase.value,
                period=period,
                interval=interval,
                last_close=latest,
                proj_series=pred_series,
                logic_snapshot=logic_snap,
            )
        lookup = {_ts_ist_naive(ts): float(px) for ts, px in live_line.items()} if len(live_line) else {}
        SQL_STORE.evaluate_accuracy(stock, lookup)
    except Exception as ex:
        st.session_state["angad_sql_error"] = f"SQL save: {ex}"

    acc = SQL_STORE.load_accuracy_summary(stock, primary_source)

    tab_decision, tab_chart, tab_history = st.tabs(
        ["📋 Signal · Logic · Reason", "📊 Chart", "📜 History & accuracy"]
    )

    with tab_decision:
        render_signal_decision_block(
            signal=primary_signal,
            confidence=primary_conf,
            target=primary_target,
            stop=primary_stop,
            last_close=latest,
            source_label=source_label,
            reason=rule["reason"],
            score=primary_score if primary_score is not None else rule.get("score"),
            market_regime=rule.get("market_regime"),
            brain=brain if use_genai else None,
            logic_snap=logic_snap,
            rule=rule,
            acc_summary=acc,
        )
        if brain and brain.get("news_cited"):
            st.markdown("#### 📰 News used | वापरले बातम्या")
            rows = []
            for n in brain["news_cited"]:
                if isinstance(n, dict):
                    rows.append(
                        {
                            "ID": n.get("headline_id", "—"),
                            "Why (English)": n.get("why_it_matters", "—"),
                        }
                    )
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if not genai_on:
            st.info(
                "Gen AI off — set `openai.api_key` in SQL: "
                "`UPDATE api_config SET config_value='your-key' WHERE provider_code='openai' AND config_key='api_key'`"
            )
        st.caption(cmp_note)

    with tab_chart:
        st.caption("**Green** = live price · **Red solid** = current prediction (saved to SQL) · **Light red** = past predictions")
        y0, y1 = chart_y_range(df_ist, pred_series, None, [])
        hist = SQL_STORE.load_historical_predictions(stock, primary_source, 50)
        fig = build_live_prediction_chart(
            df_ist=df_ist,
            live_line=live_line,
            current_pred=pred_series,
            hist_predictions=hist,
            y0=y0,
            y1=y1,
            today=today,
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"scrollZoom": True, "displayModeBar": not st.session_state.angad_mobile_mode},
        )

    with tab_history:
        st.markdown("#### Recent predictions (readable table)")
        audit = SQL_STORE.load_audit_trail(stock, limit=20)
        render_audit_summary(audit)
        if not audit.empty:
            st.markdown("#### Pick a run to see logic used")
            run_ids = audit["run_id"].astype(int).tolist()
            pick = st.selectbox("Run #", run_ids, format_func=lambda x: f"Run {x}")
            row = audit[audit["run_id"] == pick].iloc[0]
            render_audit_detail_tables(row)
        st.markdown("#### Latest market bars from SQL")
        bars = SQL_STORE.query_recent_bars(stock, 20)
        if not bars.empty:
            bars = bars.rename(
                columns={
                    "bar_time_ist": "Time (IST)",
                    "open_price": "Open",
                    "high_price": "High",
                    "low_price": "Low",
                    "close_price": "Close",
                    "volume": "Volume",
                }
            )
            st.dataframe(bars, use_container_width=True, hide_index=True)
        acc_g = SQL_STORE.load_accuracy_summary(stock, SOURCE_GENAI)
        acc_r = SQL_STORE.load_accuracy_summary(stock, SOURCE_RULE)
        st.markdown("#### Data retention (6-month auto-delete)")
        st.caption(
            f"Policy: **{SQL_STORE.get_retention_months()} months** — "
            "predictions, bars, and accuracy older than that are removed automatically."
        )
        purge_hist = SQL_STORE.load_purge_history(5)
        if not purge_hist.empty:
            st.dataframe(purge_hist, use_container_width=True, hide_index=True)
        st.dataframe(
            pd.DataFrame(
                [
                    {"Source": "Gen AI", **{k: acc_g.get(k) for k in ("evaluated", "hit_rate_pct", "avg_error_pct")}},
                    {"Source": "Rule", **{k: acc_r.get(k) for k in ("evaluated", "hit_rate_pct", "avg_error_pct")}},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


render_board()

with st.sidebar:
    st.divider()
    h = SQL_CFG.health()
    if h.get("ok"):
        st.caption(f"Store connected · {h.get('config_keys', 0)} settings from SQL")
    else:
        st.caption("Store unavailable — check SQL service")
    if st.session_state.get("angad_purge_note"):
        st.caption(st.session_state["angad_purge_note"])
    if st.session_state.get("angad_sql_status"):
        st.success(st.session_state["angad_sql_status"])
    if st.session_state.get("angad_sql_error"):
        st.error(st.session_state["angad_sql_error"])
