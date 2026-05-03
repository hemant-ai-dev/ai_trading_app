import hashlib
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import plotly.graph_objects as go
import streamlit as st

from config.loader import load_settings
from data_fetch import get_stock_data
from genai_reason import (
    build_indicators_summary,
    full_chart_intel_analysis,
)
from indicators import apply_indicators
from intraday_forecast import (
    build_comparison_series,
    ensure_ist_index,
    qualitative_scenario_line,
)
from level_plan import (
    chart_y_range,
    default_chart_levels,
    format_full_deterministic_desk,
    merge_chart_levels,
    snapshot_levels,
)
from market_calendar import format_market_context_for_llm, get_market_status
from market_intel import (
    format_headlines_indexed_for_prompt,
    news_digest_for_cache,
)
from providers.llm_openai import NullLLM
from providers.registry import (
    build_llm_provider,
    build_news_intel_provider,
    resolve_openai_api_key,
)
from signal_engine import get_signal

SETTINGS = load_settings()
IST = ZoneInfo("Asia/Kolkata")


def _build_llm():
    key = resolve_openai_api_key(SETTINGS)
    if not key:
        try:
            key = str(st.secrets["OPENAI_API_KEY"])
        except (KeyError, FileNotFoundError, TypeError):
            key = None
    return build_llm_provider(SETTINGS, api_key_override=key)


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


def _cached_intel_analysis(cache_key: str, fetch_fn):
    if st.session_state.get("intel_ai_key") == cache_key and st.session_state.get("intel_ai_val") is not None:
        return st.session_state.intel_ai_val
    data = fetch_fn()
    st.session_state.intel_ai_key = cache_key
    st.session_state.intel_ai_val = data
    return data


def _redacted_settings_view(cfg: dict) -> dict:
    out = json.loads(json.dumps(cfg))

    def scrub(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                lk = k.lower()
                if any(x in lk for x in ("api_key", "secret", "token", "password")):
                    obj[k] = "***" if obj[k] else obj[k]
                else:
                    scrub(obj[k])
        elif isinstance(obj, list):
            for item in obj:
                scrub(item)

    scrub(out)
    return out


def _normalize_headline_id(raw: object) -> str:
    s = str(raw or "").strip().upper()
    return s


def _render_intel_tabs(intel: dict, headline_lookup: dict[str, str]) -> None:
    t_strategy, t_news, t_playbook, t_risk = st.tabs(
        ["Strategy & chart mapping", "News cited", "Conditional levels playbook", "Risks & limits"]
    )

    with t_strategy:
        st.markdown(f"### {intel.get('strategy_title') or 'Strategy overview'}")
        steps = intel.get("strategy_step_by_step") or []
        if steps:
            st.markdown("**Step-by-step (ties to indicator rules)**")
            for i, step in enumerate(steps, start=1):
                st.markdown(f"{i}. {step}")
        tech = intel.get("technical_rules_detail") or intel.get("technical_methods") or []
        if tech:
            st.markdown("**Technical checks referenced**")
            for line in tech:
                st.markdown(f"- {line}")
        if intel.get("prediction_mapping"):
            st.markdown("**How to read the chart lines**")
            st.markdown(intel["prediction_mapping"])

    with t_news:
        cited = intel.get("news_items_cited") or []
        if cited:
            st.markdown("**Headlines explicitly referenced (IDs → full title)**")
            for row in cited:
                if not isinstance(row, dict):
                    continue
                hid = _normalize_headline_id(row.get("headline_id"))
                title = headline_lookup.get(hid)
                note = row.get("why_it_matters") or row.get("note") or ""
                if title:
                    st.markdown(f"- **`[{hid}]`** {title}  \n  ↳ *Why it matters:* {note}")
                else:
                    st.markdown(f"- **`[{hid}]`** *(unknown ID — verify prompt)*  \n  ↳ {note}")
        else:
            st.caption("No headline citations returned — model may have stayed macro-only.")

        macro = intel.get("news_macro_interpretation") or ""
        if macro:
            st.markdown("**Macro / sentiment synthesis**")
            st.markdown(macro)

    with t_playbook:
        pb = intel.get("conditional_playbook") or {}
        if isinstance(pb, dict) and pb:
            disc = pb.get("disclaimer") or ""
            if disc:
                st.caption(disc)
            bp = pb.get("bullish_path") or pb.get("bullish_confirmation_path") or {}
            sp = pb.get("bearish_path") or pb.get("bearish_confirmation_path") or {}
            nz = pb.get("neutral_wait_zone") or {}

            st.markdown("#### Bullish confirmation path *(hypothetical / educational)*")
            if isinstance(bp, dict) and bp:
                st.markdown(
                    f"- **Trigger idea (above ~₹{bp.get('trigger_above_price', '—')}):** "
                    f"context for upward-follow-through scenarios.\n"
                    f"- **If that lift never happens:** {bp.get('if_price_never_reaches_above') or bp.get('wait_if_below_that') or '—'}\n"
                    f"- **Objective reference:** ₹{bp.get('objective_reference_price') or bp.get('objective_near') or '—'}\n"
                    f"- **Invalidation / reassessment reference:** ₹{bp.get('invalidation_reference_price') or bp.get('invalidation_near') or '—'}\n"
                    f"- **Derivatives education note:** {bp.get('educational_derivatives_note') or bp.get('option_analogy_note') or '—'}"
                )

            st.markdown("#### Bearish confirmation path *(hypothetical / educational)*")
            if isinstance(sp, dict) and sp:
                st.markdown(
                    f"- **Trigger idea (below ~₹{sp.get('trigger_below_price', '—')}):** "
                    f"context for downward-follow-through scenarios.\n"
                    f"- **If that break never happens:** {sp.get('if_price_never_reaches_below') or sp.get('wait_if_above_that') or '—'}\n"
                    f"- **Objective reference:** ₹{sp.get('objective_reference_price') or sp.get('objective_near') or '—'}\n"
                    f"- **Invalidation / reassessment reference:** ₹{sp.get('invalidation_reference_price') or sp.get('invalidation_near') or '—'}\n"
                    f"- **Derivatives education note:** {sp.get('educational_derivatives_note') or sp.get('option_analogy_note') or '—'}"
                )

            st.markdown("#### Neutral / wait pocket")
            if isinstance(nz, dict) and nz:
                lo = nz.get("lower_bound")
                hi = nz.get("upper_bound")
                beh = nz.get("behaviour") or nz.get("behavior") or nz.get("explanation") or ""
                st.markdown(f"- **Between ~₹{lo} and ~₹{hi}:** {beh}")
        else:
            st.info("GenAI playbook empty — see deterministic rule playbook below.")

        st.markdown("---")
        st.markdown("**How projections relate:**")
        st.markdown(intel.get("how_the_chart_was_built") or intel.get("prediction_mapping") or "—")

    with t_risk:
        st.markdown(intel.get("key_risks") or "—")
        st.markdown("---")
        st.markdown(intel.get("limitations") or "")
        tilt = float(intel.get("sentiment_tilt") or 0.0)
        st.caption(f"Purple overlay bounded tilt parameter: **{tilt:.2f}** (−1 bearish … +1 bullish).")


st.set_page_config(
    page_title=SETTINGS.get("app", {}).get("title", "GenAI Trading Tool"),
    page_icon="📈",
    layout="wide",
)

st.title(SETTINGS.get("app", {}).get("title", "📈 GenAI Intraday Dashboard (NSE)"))
st.caption(
    SETTINGS.get("app", {}).get(
        "subtitle",
        "Rule-based signals + GenAI commentary (news/macro) + comparable projection paths (IST).",
    )
)
st.warning(
    "Educational prototype — not financial advice. "
    "Green shows downloaded closes (updates with refresh); orange/purple are maths overlays, not promises of future OHLC."
)


with st.sidebar.expander("⚙ Active providers & config", expanded=False):
    st.markdown(
        "Swap backends via **`config/defaults.json`**, optional **`config/local.json`** (copy from "
        "`config/local.example.json`), or env: `TRADING_LLM_PROVIDER`, `TRADING_MARKET_DATA_PROVIDER`, "
        "`TRADING_NEWS_PROVIDER`, `TRADING_CONFIG_PATH`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`."
    )
    st.json(_redacted_settings_view(SETTINGS))


st.sidebar.header("⚙ Settings")
stock = st.sidebar.text_input("Enter Stock Symbol", "RELIANCE.NS")
period = st.sidebar.selectbox(
    "Select Period",
    ["1d", "5d", "1mo", "3mo"],
    index=1,
    help="Shorter windows refresh faster for intraday.",
)
interval = st.sidebar.selectbox(
    "Select Interval",
    ["1m", "5m", "15m", "1h", "1d"],
    index=1,
)
auto_refresh = st.sidebar.toggle("Auto-refresh ~60s (intraday)", value=True)
include_world_rss = st.sidebar.toggle(
    "Include world RSS headlines (macro/war/geopolitical)",
    value=True,
    help="RSS URLs are listed in config → news.yahoo_rss.rss_urls",
)


@st.fragment(run_every=timedelta(seconds=60) if auto_refresh else None)
def render_board():
    ms = get_market_status()
    llm = _build_llm()

    st.subheader("🇮🇳 NSE session (XNSE calendar)")
    mcol1, mcol2, mcol3 = st.columns(3)
    mcol1.metric("IST now", ms.now_ist.strftime("%Y-%m-%d %H:%M"))
    mcol2.metric("Calendar phase", ms.phase.value.replace("_", " "))
    mcol3.metric("Next session date", str(ms.next_session_date))
    st.caption(ms.reason)

    with st.spinner("Fetching market data & headlines…"):
        df = get_stock_data(stock, period, interval)
        equity_news, world_news = _load_intel_cached(stock, include_world_rss)

    if df.empty:
        st.warning("No data available.")
        return

    df = apply_indicators(df)
    df_ist = ensure_ist_index(df)

    result = get_signal(df)
    latest_price = float(df["Close"].iloc[-1])
    lv_snap = snapshot_levels(df, result)

    today = ms.now_ist.date()
    anchor_key = f"nse_anchor_v1|{stock}|{today.isoformat()}"
    today_mask = df_ist.index.map(lambda t: t.date()) == today
    today_slice = df_ist.loc[today_mask]
    session_anchor = None
    if anchor_key not in st.session_state and len(today_slice) > 0:
        st.session_state[anchor_key] = {"anchor_price": float(today_slice["Close"].iloc[0])}
    if anchor_key in st.session_state:
        session_anchor = st.session_state[anchor_key]

    _, proj_cmp, cmp_note = build_comparison_series(
        df_ist,
        float(result["target"]),
        ms,
        session_anchor,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📌 Stock", stock)
    col2.metric("💰 Last close", f"₹ {latest_price:.2f}")
    col3.metric("📢 Rule signal", result["signal"])
    col4.metric("🎯 Confidence", f'{result["confidence"]}%')

    col5, col6 = st.columns(2)
    col5.metric(
        "🛑 Rule invalidation ref",
        f'₹ {result["stop_loss"]}',
        help="Derived from ATR + signal direction.",
    )
    col6.metric("🚀 Rule objective ref", f'₹ {result["target"]}')

    sig = result["signal"]
    if sig == "BUY":
        st.success(
            f"**Rule posture: BUY** — scorecard ≥ 3. Use **₹{result['stop_loss']:.2f}** as invalidation *reference* and **₹{result['target']:.2f}** as objective *reference* (not advice).",
            icon="📈",
        )
    elif sig == "SELL":
        st.error(
            f"**Rule posture: SELL** — scorecard ≤ −2. Invalidation *reference* **₹{result['stop_loss']:.2f}**; stretch *reference* **₹{result['target']:.2f}**.",
            icon="📉",
        )
    else:
        st.warning(
            f"**Rule posture: HOLD** — score between buy and sell cuts. Prefer **wait** for a clear break vs VWAP with **₹{result['stop_loss']:.2f}** / **₹{result['target']:.2f}** as band references.",
            icon="⏸️",
        )
    st.caption(f"Raw factor tags: {result['reason']}")

    headline_block, headline_lookup = format_headlines_indexed_for_prompt(equity_news, world_news)
    summary = build_indicators_summary(df)
    market_ctx = format_market_context_for_llm(ms)
    digest = news_digest_for_cache(equity_news, world_news)
    digest_hash = hashlib.sha256(digest.encode("utf-8")).hexdigest()[:32]

    buy_sell_block = (
        f"Signal {result['signal']} at {result['confidence']}% confidence. "
        f"Rule invalidation/stop reference: ₹{result['stop_loss']}; rule objective/target reference: ₹{result['target']}. "
        f"Factors: {result['reason']}."
    )

    reference_levels_json = json.dumps(
        {
            **lv_snap,
            "signal": result["signal"],
            "confidence_shown_pct": result["confidence"],
        },
        ensure_ascii=False,
        indent=2,
    )

    ai_cache_key = (
        f"{stock}|{result['signal']}|{latest_price:.4f}|{ms.phase}|{digest_hash}|{summary[:120]}"
    )

    def _fetch_intel():
        return full_chart_intel_analysis(
            result["signal"],
            result["confidence"],
            result["reason"],
            summary,
            market_ctx,
            buy_sell_block,
            headline_block,
            reference_levels_json,
            llm,
            SETTINGS,
        )

    genai_on = not isinstance(llm, NullLLM)
    intel = _cached_intel_analysis(ai_cache_key, _fetch_intel) if genai_on else None

    st.subheader("📘 Full rule explanation (always available — read this first)")

    det_full = format_full_deterministic_desk(result["reason"], lv_snap, result["signal"])
    with st.container(border=True):
        st.markdown(det_full)

    st.subheader("🧠 GenAI layer (optional)")

    if intel:
        _render_intel_tabs(intel, headline_lookup)
        tilt = float(intel.get("sentiment_tilt") or 0.0)
        st.caption(
            f"GenAI tilt driving purple overlay: **{tilt:.2f}**. Rendered **{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}**."
        )
    elif genai_on:
        st.warning("GenAI JSON unavailable this run — only the rule sections above and chart lines are shown.")
    else:
        st.info(
            "**GenAI is off** (no `OPENAI_API_KEY` or `llm.provider` = none). "
            "Add a key in environment or Streamlit secrets to unlock tabs for headline citations and purple scenario line."
        )

    proj_qual = None
    if intel is not None and len(proj_cmp) > 0:
        proj_qual = qualitative_scenario_line(
            proj_cmp,
            float(result["target"]),
            float(intel.get("sentiment_tilt") or 0.0),
        )

    chart_levels = merge_chart_levels(
        intel.get("chart_reference_levels") if intel else None,
        default_chart_levels(lv_snap, result["signal"]),
    )[:10]

    y0, y1 = chart_y_range(df_ist, proj_cmp, proj_qual, chart_levels)

    st.subheader("📊 Same chart: actual trail + projections + reference guides")
    st.caption(
        cmp_note
        + " • Blue updates when data refreshes (nearest ‘real-time’ trail available via Yahoo interval)."
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_ist.index,
            y=df_ist["Close"],
            name="Actual closes (historical + latest bar)",
            line=dict(color="#5dade2", width=3.5),
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=proj_cmp.index,
            y=proj_cmp.values,
            name="Rule projection → objective",
            line=dict(color="#f5b041", width=5, dash="dash"),
            connectgaps=False,
        )
    )
    if proj_qual is not None and len(proj_qual) > 0:
        fig.add_trace(
            go.Scatter(
                x=proj_qual.index,
                y=proj_qual.values,
                name="GenAI bounded scenario tilt",
                line=dict(color="#af7ac5", width=4, dash="dot"),
                connectgaps=False,
            )
        )

    palette = {"spot": "#ecf0f1", "context": "#48c9b0", "trigger": "#f4d03f", "risk": "#ec7063", "target": "#58d68d", "ref": "#bdc3c7"}
    for row in chart_levels:
        price = float(row["price"])
        kind = str(row.get("kind") or "ref")
        color = palette.get(kind, "#95a5a6")
        fig.add_hline(
            y=price,
            line=dict(color=color, dash="dash", width=2),
            opacity=0.85,
            annotation_text=str(row.get("label") or "")[:48],
            annotation_position="top right",
            annotation_font_size=13,
            annotation_font_color=color,
        )

    fig.update_layout(
        template="plotly_dark",
        height=720,
        font=dict(size=14, color="#eaeaea"),
        xaxis_title="Time (IST)",
        yaxis_title="Price (₹)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="right",
            x=1,
            font=dict(size=14),
            bgcolor="rgba(0,0,0,0.35)",
        ),
        margin=dict(t=120, l=60, r=40, b=60),
        hovermode="x unified",
    )
    fig.update_xaxes(tickfont=dict(size=13), title_font=dict(size=15))
    fig.update_yaxes(
        range=[y0, y1],
        tickformat=".2f",
        separatethousands=True,
        tickfont=dict(size=13),
        title_font=dict(size=15),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📰 Indexed headline catalog (matches GenAI citations)"):
        st.code(headline_block or "(none)", language="markdown")

    st.subheader("📋 Indicator snapshot")
    st.dataframe(df.tail(12), use_container_width=True)


render_board()

st.caption(
    "Built with Python + Streamlit — holidays: pandas_market_calendars (XNSE). "
    "Providers: `config/defaults.json`, optional `config/local.json`, `providers/registry.py`."
)
