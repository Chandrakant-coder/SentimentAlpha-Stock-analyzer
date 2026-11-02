"""NSE session helpers.

Yahoo Finance daily bars for *.NS tickers are delayed historical session data,
not a live quote. Saturday/Sunday never have a new NSE closing price.
"""

from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
# Regular cash-market close is 15:30 IST. Yahoo's daily bar is typically
# published after the session; treat 16:30 IST as "today's bar may exist".
PROVIDER_BAR_READY = datetime.time(16, 30)
NSE_CASH_CLOSE = datetime.time(15, 30)


def as_ist(now: Optional[datetime.datetime] = None) -> datetime.datetime:
    if now is None:
        return datetime.datetime.now(IST)
    if now.tzinfo is None:
        return now.replace(tzinfo=IST)
    return now.astimezone(IST)


def previous_weekday(d: datetime.date) -> datetime.date:
    d = d - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


def last_completed_nse_session(now: Optional[datetime.datetime] = None) -> datetime.date:
    """Latest weekday session that should already have a Yahoo daily bar.

    Does not model exchange holidays; a holiday may look like a missing session.
    """
    now_ist = as_ist(now)
    d = now_ist.date()
    if d.weekday() >= 5:
        return previous_weekday(d)
    if now_ist.timetz().replace(tzinfo=None) < PROVIDER_BAR_READY:
        return previous_weekday(d)
    return d


def normalize_session_date(value) -> Optional[datetime.date]:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def missing_expected_session(
    latest_market_date,
    now: Optional[datetime.datetime] = None,
) -> bool:
    latest = normalize_session_date(latest_market_date)
    if latest is None:
        return True
    expected = last_completed_nse_session(now)
    return latest < expected


def publication_session_date(published_at: datetime.datetime) -> datetime.date:
    """Map an article timestamp onto the first session that can observe it.

    Naive timestamps are treated as IST (Indian financial RSS coverage).
    Copy published at or after the 15:30 IST cash close is assigned to the
    next calendar day so it cannot enter a same-session close signal.
    """
    if published_at.tzinfo is None:
        dt = published_at.replace(tzinfo=IST)
    else:
        dt = published_at.astimezone(IST)
    d = dt.date()
    if dt.time() >= NSE_CASH_CLOSE:
        d = d + datetime.timedelta(days=1)
    return d
