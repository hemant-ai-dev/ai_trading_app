"""API Management / status desk — free APIs, SQLite usage stats."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from db.database import DatabaseError, db_path
from services.api_monitor import (
    NOT_PROVIDED,
    derive_status,
    set_provider_enabled,
    usage_recent,
    usage_summary,
)


def _fmt_dt(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(val)


def _probe(url: str, timeout: float = 8.0) -> tuple[bool, str]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AngadTrading/1.0)"})
        with urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if 200 <= int(status) < 400:
                return True, f"HTTP {status}"
            return False, f"HTTP {status}"
    except Exception as exc:
        return False, str(exc)[:180]


def render_api_management(_user: dict) -> None:
    st.markdown('<div class="terminal-title">API Management</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="terminal-sub">Free data sources only · secrets stay in env / Streamlit secrets · not a profit guarantee</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"SQLite: `{db_path()}`")

    try:
        rows = usage_summary()
    except DatabaseError as exc:
        st.error(f"Could not load API status: {exc}")
        return

    if not rows:
        st.warning("API catalog is empty. Restart the app to initialize SQLite.")
        return

    status_colors = {
        "active": "#26a69a",
        "inactive": "#64748b",
        "failed": "#ef5350",
        "rate-limited": "#f0b90b",
    }

    for row in rows:
        status = derive_status(row)
        color = status_colors.get(status, "#94a3b8")
        used = int(row.get("TodayUsage") or 0)
        ok = int(row.get("TodaySuccess") or 0)
        fail = int(row.get("TodayFailure") or 0)
        key_state = (
            "Set via environment or Streamlit secrets (not stored in SQLite)"
            if row.get("RequiresApiKey")
            else "not required"
        )

        st.markdown(
            f"""
            <div class="compare-card" style="border-color:{color}">
              <div style="display:flex;justify-content:space-between;gap:0.75rem;flex-wrap:wrap">
                <div>
                  <div class="smart-kicker">{row.get('Category')}</div>
                  <div style="font-size:1.15rem;font-weight:700">{row.get('ApiName')}</div>
                  <div>{row.get('Purpose')}</div>
                </div>
                <div style="text-align:right">
                  <div style="color:{color};font-weight:800;letter-spacing:0.06em">{status.upper()}</div>
                  <div>Free / Paid: <b>{"Free" if row.get("IsFree") else "Paid (not used)"}</b></div>
                </div>
              </div>
              <div style="margin-top:0.65rem;font-size:0.9rem;line-height:1.55">
                <div><b>Endpoint:</b> {row.get("Endpoint")}</div>
                <div><b>Free usage limit:</b> {row.get("FreeUsageLimit")}</div>
                <div><b>Current usage (today):</b> {used} ({ok} ok / {fail} failed)</div>
                <div><b>Remaining requests:</b> {NOT_PROVIDED}</div>
                <div><b>Last successful request:</b> {_fmt_dt(row.get("LastSuccessUtc"))}</div>
                <div><b>Latest error:</b> {row.get("LastError") or "—"}</div>
                <div><b>Configuration:</b> {key_state}</div>
                <div style="opacity:0.8">{row.get("PricingNote")}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        enabled = bool(row.get("IsEnabled"))
        new_en = c1.toggle("Enabled", value=enabled, key=f"en_{row['ApiCode']}")
        if new_en != enabled:
            set_provider_enabled(str(row["ApiCode"]), new_en)
            st.rerun()
        if c2.button("Health check", key=f"ping_{row['ApiCode']}"):
            _run_health_check(str(row["ApiCode"]), str(row.get("Endpoint") or ""))
        c3.caption("API keys are not saved in the database.")

    st.markdown("#### Recent requests")
    try:
        recent = usage_recent(None, 40)
    except DatabaseError as exc:
        st.error(str(exc))
        return
    if not recent:
        st.caption("No calls logged yet. Open the trading desk to generate traffic.")
        return
    df = pd.DataFrame(recent)
    keep = [
        "ApiName",
        "RequestUtc",
        "Operation",
        "Success",
        "HttpStatus",
        "ResponseMs",
        "QuotaRemaining",
        "ErrorMessage",
    ]
    cols = [c for c in keep if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)


def _run_health_check(api_code: str, endpoint: str) -> None:
    from services.api_monitor import log_usage

    probes = {
        "yfinance": "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1d&range=5d",
        "stooq": "https://stooq.com/q/d/l/?s=infy.in&i=d",
        "yahoo_news": "https://finance.yahoo.com/quote/INFY.NS/news",
        "bbc_rss": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "nyt_rss": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    }
    t0 = datetime.now(timezone.utc)
    if api_code == "local_ta":
        log_usage("local_ta", operation="health_check", success=True, endpoint=endpoint, http_status=200, response_ms=1)
        st.success("Local indicators are available (no network).")
        return
    url = probes.get(api_code) or endpoint.split("{")[0] or endpoint
    ok, msg = _probe(url)
    ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    log_usage(
        api_code,
        operation="health_check",
        success=ok,
        endpoint=url,
        http_status=200 if ok else None,
        response_ms=ms,
        error=None if ok else msg,
    )
    if ok:
        st.success(f"{api_code}: {msg}")
    else:
        st.error(f"{api_code}: {msg}")
