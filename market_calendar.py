"""Indian equity cash session (XNSE) via pandas_market_calendars — not official exchange data; verify critical dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

import pandas as pd
import pandas_market_calendars as mcal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
_XNSE = None


def _calendar():
    global _XNSE
    if _XNSE is None:
        _XNSE = mcal.get_calendar("XNSE")
    return _XNSE


class SessionPhase(str, Enum):
    HOLIDAY_OR_WEEKEND = "closed_calendar"
    PRE_OPEN = "pre_open"
    OPEN = "open"
    POST_CLOSE = "post_close"


@dataclass
class MarketStatus:
    now_ist: datetime
    as_of_date_ist: date
    phase: SessionPhase
    is_trading_day: bool
    next_session_date: date
    session_open_ist: Optional[datetime]
    session_close_ist: Optional[datetime]
    reason: str


def _is_nse_trading_day(d: date) -> bool:
    cal = _calendar()
    vd = cal.valid_days(start_date=d, end_date=d)
    return len(vd) > 0


def _session_bounds_ist(d: date) -> tuple[datetime, datetime] | None:
    """Regular cash session open/close in IST."""
    cal = _calendar()
    sched = cal.schedule(start_date=d, end_date=d)
    if sched.empty:
        return None
    o = sched.iloc[0]["market_open"].tz_convert(IST)
    c = sched.iloc[0]["market_close"].tz_convert(IST)
    return (o, c)


def next_nse_trading_date(on_or_after: date) -> date:
    cal = _calendar()
    for off in range(0, 20):
        d = on_or_after + timedelta(days=off)
        vd = cal.valid_days(start_date=d, end_date=d)
        if len(vd) > 0:
            return vd[0].tz_convert(IST).date()
    return on_or_after


def get_market_status(now_ist: datetime | None = None) -> MarketStatus:
    now_ist = now_ist or datetime.now(IST)
    if now_ist.tzinfo is None:
        now_ist = now_ist.replace(tzinfo=IST)
    else:
        now_ist = now_ist.astimezone(IST)

    today = now_ist.date()
    trading_today = _is_nse_trading_day(today)

    if not trading_today:
        nxt = next_nse_trading_date(today)
        return MarketStatus(
            now_ist=now_ist,
            as_of_date_ist=today,
            phase=SessionPhase.HOLIDAY_OR_WEEKEND,
            is_trading_day=False,
            next_session_date=nxt,
            session_open_ist=None,
            session_close_ist=None,
            reason="XNSE calendar: no regular session today (weekend or exchange holiday).",
        )

    bounds = _session_bounds_ist(today)
    if bounds is None:
        nxt = next_nse_trading_date(today + timedelta(days=1))
        return MarketStatus(
            now_ist=now_ist,
            as_of_date_ist=today,
            phase=SessionPhase.HOLIDAY_OR_WEEKEND,
            is_trading_day=False,
            next_session_date=nxt,
            session_open_ist=None,
            session_close_ist=None,
            reason="No session row for today (unusual); treating as non-session.",
        )

    open_ist, close_ist = bounds
    if now_ist < open_ist:
        phase = SessionPhase.PRE_OPEN
        reason = "Trading day — pre-open (before 9:15 IST regular session)."
    elif now_ist > close_ist:
        phase = SessionPhase.POST_CLOSE
        reason = "Trading day — regular session has ended for today."
    else:
        phase = SessionPhase.OPEN
        reason = "Trading day — regular session open (9:15–15:30 IST)."

    nxt = today
    if phase == SessionPhase.POST_CLOSE:
        nxt = next_nse_trading_date(today + timedelta(days=1))

    return MarketStatus(
        now_ist=now_ist,
        as_of_date_ist=today,
        phase=phase,
        is_trading_day=True,
        next_session_date=nxt,
        session_open_ist=open_ist,
        session_close_ist=close_ist,
        reason=reason,
    )


def format_market_context_for_llm(ms: MarketStatus) -> str:
    parts = [
        "Indian NSE cash market (XNSE calendar, IST).",
        f"Local time: {ms.now_ist.strftime('%Y-%m-%d %H:%M IST')}.",
        f"Status: {ms.phase.value} — {ms.reason}",
        f"Next session date for projections: {ms.next_session_date.isoformat()}.",
    ]
    if ms.session_open_ist and ms.session_close_ist:
        parts.append(
            f"Today's regular hours: {ms.session_open_ist.strftime('%H:%M')}–{ms.session_close_ist.strftime('%H:%M')} IST."
        )
    return " ".join(parts)
