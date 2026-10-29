"""Option Chain Intelligence workspace — separate from Market AI."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from auth.session import history_store_path
from data.cache import APP_CACHE
from market_calendar import get_market_status
from options.chain import expiry_meta, fetch_chain, list_expiries
from options.charts import prediction_bar, premium_chart
from options.intelligence import display_chain, recommend
from options.store import OptionPredictionStore
from prediction.session_tape import SessionTapeStore
from utils.logging import get_logger
from utils.time_utils import IST

logger = get_logger(__name__)

UNDERLYINGS = {
    "Nifty 50": "^NSEI",
    "Bank Nifty": "^NSEBANK",
    "Reliance": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "Infosys": "INFY.NS",
    "HDFC Bank": "HDFCBANK.NS",
}


def _store() -> OptionPredictionStore:
    user = st.session_state.get("auth_user") or {}
    path = history_store_path(int(user.get("user_id") or 0))
    return OptionPredictionStore(path)


def _tape() -> SessionTapeStore:
    user = st.session_state.get("auth_user") or {}
    path = history_store_path(int(user.get("user_id") or 0))
    return SessionTapeStore(path)


def _premium_map(chain: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for side in ("calls", "puts"):
        df = chain.get(side)
        if df is None or getattr(df, "empty", True):
            continue
        for _, r in df.iterrows():
            c = str(r.get("contract") or "")
            ltp = r.get("ltp")
            if c and ltp is not None and pd.notna(ltp):
                try:
                    v = float(ltp)
                    if v > 0:
                        out[c] = v
                except (TypeError, ValueError):
                    continue
    return out


def render_options_workspace(user: dict, *, theme_name: str = "dark") -> None:
    st.markdown(
        '<div class="hello-line">Option Chain Intelligence</div>'
        '<p class="hello-sub">Separate from Market AI. Educational screens only — not a broker, not a profit guarantee. '
        "Chain from NSE India public option-chain JSON when available.</p>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1.2, 2])
    with c1:
        name = st.selectbox("Underlying", list(UNDERLYINGS.keys()), key="opt_under_name")
        symbol = UNDERLYINGS[name]
    analysis = st.session_state.get("analysis")
    spot = None
    primary = None
    ctx: dict = {}
    cached = st.session_state.get("last_market_ai") or {}
    if cached.get("symbol") == symbol and cached.get("primary") is not None:
        spot = float(cached["spot"])
        primary = cached["primary"]
        ctx = primary.indicator_snapshot or {}
    elif analysis:
        try:
            df = analysis.market.get_ohlcv(symbol, "3mo", "1d")
            if df is not None and not df.empty:
                from indicators.calculator import apply_all_indicators, build_indicator_context
                from prediction.rule_engine import predict_rule_based

                ind = apply_all_indicators(df)
                ctx = build_indicator_context(ind)
                primary = predict_rule_based(ind, ctx)
                spot = float(ind["Close"].iloc[-1])
        except Exception as exc:
            st.warning(f"Underlying snapshot unavailable: {exc}")

    if st.button("Reload chain", key="opt_reload"):
        APP_CACHE.delete_prefix("opt-")
        st.rerun()
    st.caption("Snapshots are cached about 45 seconds. Use Reload chain for a fresh pull.")

    with st.spinner("Loading option chain..."):
        resolved, expiries = list_expiries(symbol)
    with c2:
        if not expiries:
            st.warning("Option-chain data is currently unavailable. Please try again.")
            expiry = ""
        else:
            expiry = st.selectbox("Expiry", expiries, key="opt_expiry")

    meta = expiry_meta(expiry) if expiry else {"valid": False, "status": "UNAVAILABLE", "days_remaining": None}
    ms = get_market_status()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Underlying", name)
    m2.metric("Spot", f"₹{spot:,.2f}" if spot else "—")
    m3.metric("Expiry", meta.get("expiry") or "—")
    m4.metric("Days left", meta.get("days_remaining") if meta.get("days_remaining") is not None else "—")
    m5.metric("Expiry status", meta.get("status") or "—")
    st.caption(
        f"Today {ms.now_ist.strftime('%d %b %Y %H:%M IST')} · session {ms.phase.value.replace('_', ' ')} · "
        f"expiry weekday {meta.get('expiry_day') or '—'} · "
        f"{'expiry day' if meta.get('is_expiry_day') else 'not expiry day'} · "
        f"{'new expiries listed' if len(expiries) > 1 else 'waiting on contract list'}"
    )

    with st.spinner("Loading option chain..."):
        chain = fetch_chain(symbol, expiry) if expiry else {"calls": pd.DataFrame(), "puts": pd.DataFrame(), "note": "Option-chain data is currently unavailable. Please try again.", "spot": None}
    if chain.get("spot") and not spot:
        spot = float(chain["spot"])
    if chain.get("note"):
        st.warning(chain["note"])
    elif expiry and (chain.get("calls") is None or (getattr(chain.get("calls"), "empty", True) and getattr(chain.get("puts"), "empty", True))):
        st.warning("Option-chain data is currently unavailable. Please try again.")

    rec = None
    if spot and primary:
        store = _store()
        prev = store.last_action(symbol, None)
        rec = recommend(
            underlying=symbol,
            spot=spot,
            predicted_underlying=float(primary.predicted_price),
            signal=primary.signal,
            trend=str(primary.trend or ctx.get("trend_dir") or ""),
            confidence=float(primary.confidence or 0),
            rsi=ctx.get("rsi"),
            macd=ctx.get("macd"),
            atr=ctx.get("atr"),
            vwap=ctx.get("vwap"),
            expiry=expiry or "",
            days_remaining=int(meta.get("days_remaining") or -1) if meta.get("valid") else -1,
            calls=chain.get("calls") if expiry else pd.DataFrame(),
            puts=chain.get("puts") if expiry else pd.DataFrame(),
            previous_action=prev,
        )
        store.append(
            {
                "underlying": symbol.upper(),
                "spot": spot,
                "expiry": expiry,
                "option_type": rec.get("contract_right"),
                "strike": rec.get("strike"),
                "contract": rec.get("contract"),
                "actual_premium": rec.get("premium"),
                "predicted_premium": rec.get("predicted_premium"),
                "predicted_underlying": rec.get("predicted_underlying"),
                "horizon": "1m",
                "stop": rec.get("stop"),
                "target": rec.get("target1"),
                "action": rec.get("action"),
                "signal": primary.signal,
                "confidence": rec.get("prediction", {}).get("confidence"),
                "market_regime": primary.market_regime,
                "model_version": rec.get("model_version"),
                "reasons": rec.get("reasons"),
            },
            user_id=int(user.get("user_id") or 0) or None,
        )

    tab_chain, tab_ai, tab_chart, tab_hist, tab_perf = st.tabs(
        ["Chain", "AI recommendation", "Option chart", "History", "Performance"]
    )
    with tab_chain:
        @st.fragment(run_every=timedelta(seconds=60))
        def _chain_tab() -> None:
            with st.spinner("Loading option chain..."):
                live = fetch_chain(symbol, expiry) if expiry else chain
            live_spot = float(live.get("spot") or spot or 0)
            uid = int(user.get("user_id") or 0)
            if uid and live_spot:
                try:
                    done = _store().evaluate_due(
                        user_id=uid, underlying=symbol, premiums=_premium_map(live), spot=live_spot
                    )
                    if done:
                        st.caption(f"{done} stored option prediction(s) just evaluated against this live snapshot.")
                except Exception as exc:
                    logger.warning("Option evaluation failed: %s", exc)
            if live.get("note"):
                st.warning(live["note"])
            if not live_spot:
                st.info("Loading market data... last price is required to tag ATM / ITM / OTM.")
                return
            left, right = st.columns(2)
            with left:
                st.markdown("##### Calls (CE)")
                shown = display_chain(live.get("calls"), live_spot)
                if shown is None or shown.empty:
                    st.warning("Option-chain data is currently unavailable. Please try again.")
                else:
                    st.dataframe(shown, use_container_width=True, hide_index=True, height=320)
            with right:
                st.markdown("##### Puts (PE)")
                shown = display_chain(live.get("puts"), live_spot)
                if shown is None or shown.empty:
                    st.warning("Option-chain data is currently unavailable. Please try again.")
                else:
                    st.dataframe(shown, use_container_width=True, hide_index=True, height=320)

        _chain_tab()

    with tab_ai:
        if rec:
            _render_recommendation(rec, primary)
        else:
            st.caption("Select an expiry with chain data to run Option Chain AI.")

    with tab_chart:
        if rec and rec.get("contract"):
            ser = _store().series(str(rec["contract"]))
            st.plotly_chart(
                premium_chart(
                    ser["predicted"],
                    ser["actual"],
                    entry_low=rec.get("entry_low"),
                    entry_high=rec.get("entry_high"),
                    stop=rec.get("stop"),
                    target1=rec.get("target1"),
                    target2=rec.get("target2"),
                ),
                use_container_width=True,
            )
            hist = _store().history(symbol, rec.get("contract"), limit=30)
            if not hist.empty:
                show = hist[["ts", "predicted_premium", "actual_premium", "action"]].rename(
                    columns={
                        "ts": "Time",
                        "predicted_premium": "AI premium",
                        "actual_premium": "Actual",
                        "action": "Action",
                    }
                )
                st.dataframe(show, use_container_width=True, hide_index=True, height=240)
        else:
            st.caption("No selected contract yet — option-chain data may be unavailable.")

    with tab_hist:
        oh = _store().history(symbol, limit=40)
        if oh.empty:
            st.caption("Option ticks appear after a recommendation is computed.")
        else:
            cols = [c for c in ("ts", "contract", "action", "predicted_premium", "actual_premium", "strike", "spot") if c in oh.columns]
            st.dataframe(oh[cols], use_container_width=True, hide_index=True, height=280)
        st.markdown("##### Underlying session ticks")
        tape = _tape().comparison_table(symbol, datetime.now(IST).date(), limit=40)
        if tape.empty:
            st.caption("Open Strategy with auto-refresh during the cash session to fill market ticks.")
        else:
            st.dataframe(tape, use_container_width=True, hide_index=True, height=280)

    with tab_perf:
        _render_performance(symbol, _tape(), _store())


def _render_recommendation(rec: dict, primary) -> None:
    pred = rec.get("prediction") or {}
    a, b = st.columns([1.15, 1.0])
    with a:
        st.markdown("##### Market AI (prediction only)")
        st.write(
            f"**{rec['underlying']}** last ₹{rec['spot']:,.2f} · AI expected "
            f"₹{pred.get('expected_underlying_low'):,.2f}–₹{pred.get('expected_underlying_high'):,.2f}"
        )
        st.caption("A directional guess does not automatically mean an option should be bought.")
        st.plotly_chart(prediction_bar(pred.get("call_probability", 50), pred.get("put_probability", 50)), use_container_width=True)
        st.caption(
            f"Direction **{pred.get('bias')}** · confidence {pred.get('confidence')}% "
            f"(calibration of this run, not a win rate) · strength {pred.get('signal_strength')} · PCR {pred.get('pcr')}"
        )
    with b:
        action = rec.get("action") or "NO TRADE"
        st.markdown("##### Option Chain AI (trade recommendation)")
        st.markdown(
            f"""
<div class="signal-hero">
  <div class="smart-kicker">OPTION CHAIN AI SIGNAL</div>
  <div class="smart-signal">{action}</div>
  <p class="hero-why">Underlying {rec.get('underlying')} · expiry {rec.get('expiry')} · bias {pred.get('bias')}</p>
</div>
""",
            unsafe_allow_html=True,
        )
        if rec.get("wait_text"):
            st.info(rec["wait_text"])
        if rec.get("strike"):
            st.write(
                f"**{rec.get('contract_right')} {rec['strike']:,.0f}** · premium ₹{rec.get('premium')} · "
                f"{rec.get('moneyness')}"
            )
            st.write(
                f"Entry ₹{rec.get('entry_low')}–₹{rec.get('entry_high')} · SL ₹{rec.get('stop')} · "
                f"T1 ₹{rec.get('target1')} · T2 ₹{rec.get('target2')} · T3 ₹{rec.get('target3')}"
            )
            st.write(
                f"Risk ₹{rec.get('risk')} · reward to T1 ₹{rec.get('reward')} · R:R 1:{rec.get('rr')} · "
                f"risk {rec.get('risk_level')}"
            )
            if rec.get("predicted_premium"):
                st.write(
                    f"AI expected premium ₹{rec.get('expected_premium_low')}–₹{rec.get('expected_premium_high')} "
                    f"(point ₹{rec.get('predicted_premium')})"
                )
            greeks = rec.get("greeks") or {}
            if greeks:
                st.caption(
                    f"Theoretical BS: Δ {greeks.get('delta')} Γ {greeks.get('gamma')} "
                    f"Θ/day {greeks.get('theta')} Vega {greeks.get('vega')} · "
                    f"intrinsic {greeks.get('intrinsic')} extrinsic {greeks.get('extrinsic')} — {greeks.get('note')}"
                )
        for line in rec.get("entry_why") or []:
            st.caption(line)
        for line in rec.get("reasons") or []:
            st.write(f"- {line}")
        if rec.get("exit_condition"):
            st.caption(rec["exit_condition"])
        if rec.get("trail_condition"):
            st.caption(rec["trail_condition"])
        st.caption("Educational levels from Yahoo last/IV proxies. Not an order and not a profit promise.")


def _render_performance(symbol: str, tape: SessionTapeStore, opt: OptionPredictionStore) -> None:
    user = st.session_state.get("auth_user") or {}
    mkt = tape.performance(symbol)
    op = opt.performance(symbol)
    st.markdown("##### Prediction performance (stored ticks only)")
    a, b, c, d = st.columns(4)
    a.metric("Underlying direction accuracy", f"{mkt.get('direction_accuracy_pct') or '—'}%")
    b.metric("Option premium direction", f"{op.get('direction_accuracy_pct') or '—'}%")
    c.metric("Underlying close (±0.12%)", mkt.get("close") or 0)
    d.metric("Option avg |error|", op.get("avg_abs_error") if op.get("avg_abs_error") is not None else "—")
    st.caption(
        f"Underlying ticks {mkt.get('count')} · higher {mkt.get('higher')} · lower {mkt.get('lower')} · "
        f"incorrect direction {mkt.get('direction_incorrect')} · avg |error| {mkt.get('avg_abs_error')}"
    )
    uid = int(user.get("user_id") or 0)
    if uid:
        try:
            sq = opt.option_stats(uid, symbol)
            st.markdown("##### Archived option predictions (SQLite, evaluated against live snapshots only)")
            e1, e2, e3, e4, e5 = st.columns(5)
            e1.metric("Total", sq.get("total") or 0)
            e2.metric("Pending", sq.get("pending") or 0)
            e3.metric("Evaluated", sq.get("evaluated") or 0)
            e4.metric("Direction accuracy", f"{sq.get('direction_accuracy_pct') if sq.get('direction_accuracy_pct') is not None else '—'}%" if sq.get("direction_total") else "—")
            e5.metric("Avg |premium error|", sq.get("mae") if sq.get("mae") is not None else "—")
            if not sq.get("direction_total"):
                st.caption("No archived option prediction has reached its target with a matching live snapshot yet — no accuracy figure is shown rather than inventing one.")
        except Exception as exc:
            logger.warning("Option archive stats failed: %s", exc)
    st.markdown("##### Horizons (predicted at t vs actual later)")
    hz = mkt.get("horizons") or {}
    if hz:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Horizon": k,
                        "Pairs": v.get("pairs"),
                        "Avg |error|": v.get("avg_abs_error"),
                        "Direction accuracy %": v.get("direction_accuracy_pct"),
                    }
                    for k, v in hz.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Need more session minutes on Strategy auto-refresh before horizon stats fill.")
