"""
US equity-market calendar helpers for Weavefeed.

Weavefeed anchors everything to the New York exchange clock: the Regular
Trading Hours (RTH) session for NQ opens at 09:30 America/New_York. These
helpers keep that logic independent of the host machine's timezone.

Holidays follow the NYSE full-day closure schedule (RTH is the cash-equity
session). Ad-hoc closures (e.g. national days of mourning) are NOT modelled.
"""

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)


def market_now() -> datetime:
    """Current time as a timezone-aware New York datetime."""
    return datetime.now(NY_TZ)


def market_today() -> date:
    """Current calendar date in New York (not the host's local date)."""
    return market_now().date()


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th (1-based) given weekday of a month. Monday=0 ... Sunday=6."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Last given weekday of a month."""
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _observed(d: date, *, saturday_to_friday: bool = True) -> date | None:
    """
    NYSE observance rule: Sunday holidays move to Monday, Saturday holidays
    move to Friday. New Year's Day is the exception - a Saturday Jan 1 is not
    observed on the previous Dec 31 (pass saturday_to_friday=False).
    """
    if d.weekday() == 6:
        return d + timedelta(days=1)
    if d.weekday() == 5:
        return d - timedelta(days=1) if saturday_to_friday else None
    return d


@lru_cache(maxsize=None)
def nyse_holidays(year: int) -> frozenset[date]:
    """Full-day NYSE closures falling in the given calendar year."""
    candidates = [
        _observed(date(year, 1, 1), saturday_to_friday=False),  # New Year's Day
        _nth_weekday(year, 1, 0, 3),                            # MLK Day
        _nth_weekday(year, 2, 0, 3),                            # Washington's Birthday
        _easter(year) - timedelta(days=2),                      # Good Friday
        _last_weekday(year, 5, 0),                              # Memorial Day
        _observed(date(year, 7, 4)),                            # Independence Day
        _nth_weekday(year, 9, 0, 1),                            # Labor Day
        _nth_weekday(year, 11, 3, 4),                           # Thanksgiving
        _observed(date(year, 12, 25)),                          # Christmas
    ]
    if year >= 2022:
        candidates.append(_observed(date(year, 6, 19)))         # Juneteenth
    return frozenset(d for d in candidates if d is not None and d.year == year)


def is_trading_day(d: date) -> bool:
    """True if the US equity RTH session is open on this date."""
    return d.weekday() < 5 and d not in nyse_holidays(d.year)
