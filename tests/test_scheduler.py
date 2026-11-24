"""
Unit tests for market_calendar and scheduler.

No database, network or LLM access: the clock, sleep and job are injected.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weavefeed"))
)

import scheduler
from config import Settings
from market_calendar import NY_TZ, is_trading_day, nyse_holidays
from scheduler import next_run_window, run_window, wait_and_run


def ny(y, m, d, hh=0, mm=0, ss=0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=NY_TZ)


@pytest.fixture(autouse=True)
def default_window(monkeypatch):
    """Pin delay/grace so tests do not depend on a local .env."""
    monkeypatch.setattr(scheduler.settings, "scheduler_delay_minutes", 15)
    monkeypatch.setattr(scheduler.settings, "scheduler_grace_minutes", 15)


# ========== market_calendar ==========

@pytest.mark.parametrize("year, expected", [
    (2024, {date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
            date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
            date(2024, 11, 28), date(2024, 12, 25)}),
    (2025, {date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
            date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
            date(2025, 11, 27), date(2025, 12, 25)}),
    (2026, {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
            date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
            date(2026, 11, 26), date(2026, 12, 25)}),
])
def test_nyse_holidays_match_published_schedule(year, expected):
    assert nyse_holidays(year) == expected


def test_holiday_observance_rules():
    # Jul 4 2027 is a Sunday -> observed Monday Jul 5
    assert date(2027, 7, 5) in nyse_holidays(2027)
    # Dec 25 2027 is a Saturday -> observed Friday Dec 24
    assert date(2027, 12, 24) in nyse_holidays(2027)
    # Jan 1 2022 was a Saturday: NYSE does NOT close on the preceding Dec 31
    assert date(2021, 12, 31) not in nyse_holidays(2021)
    # Juneteenth only from 2022; Jun 19 2022 was a Sunday -> Monday Jun 20
    assert not any(d.month == 6 for d in nyse_holidays(2021))
    assert date(2022, 6, 20) in nyse_holidays(2022)


def test_is_trading_day():
    assert is_trading_day(date(2026, 11, 24))       # Tuesday
    assert not is_trading_day(date(2026, 11, 28))   # Saturday
    assert not is_trading_day(date(2026, 11, 29))   # Sunday
    assert not is_trading_day(date(2026, 11, 26))   # Thanksgiving
    assert not is_trading_day(date(2026, 4, 3))     # Good Friday


# ========== run_window ==========

def test_run_window_defaults_to_open_plus_15_to_30_minutes():
    start, end = run_window(date(2026, 11, 24))
    assert (start.hour, start.minute) == (9, 45)
    assert (end.hour, end.minute) == (10, 0)
    assert start.tzinfo is NY_TZ


def test_run_window_tracks_dst_in_utc():
    # 09:45 ET is 14:45 UTC in winter (EST) and 13:45 UTC in summer (EDT)
    winter, _ = run_window(date(2026, 1, 12))
    summer, _ = run_window(date(2026, 7, 13))
    assert winter.utcoffset() == timedelta(hours=-5)
    assert summer.utcoffset() == timedelta(hours=-4)


def test_run_window_honours_configured_delay_and_grace(monkeypatch):
    monkeypatch.setattr(scheduler.settings, "scheduler_delay_minutes", 20)
    monkeypatch.setattr(scheduler.settings, "scheduler_grace_minutes", 5)
    start, end = run_window(date(2026, 11, 24))
    assert (start.hour, start.minute) == (9, 50)
    assert (end.hour, end.minute) == (9, 55)


# ========== next_run_window ==========

def test_next_run_before_window_is_same_day():
    start, _ = next_run_window(ny(2026, 11, 24, 8, 0))
    assert start == ny(2026, 11, 24, 9, 45)


def test_next_run_inside_window_is_immediate():
    start, end = next_run_window(ny(2026, 11, 24, 9, 50))
    assert start == ny(2026, 11, 24, 9, 45)   # already past -> run now
    assert end == ny(2026, 11, 24, 10, 0)


def test_next_run_after_window_rolls_to_next_trading_day():
    start, _ = next_run_window(ny(2026, 11, 24, 10, 0))  # exactly at window end
    assert start == ny(2026, 11, 25, 9, 45)


def test_next_run_skips_weekend():
    start, _ = next_run_window(ny(2026, 11, 20, 12, 0))  # Friday midday
    assert start == ny(2026, 11, 23, 9, 45)               # Monday


def test_next_run_skips_holiday():
    start, _ = next_run_window(ny(2026, 11, 25, 12, 0))  # Wed before Thanksgiving
    assert start == ny(2026, 11, 27, 9, 45)               # Friday


def test_next_run_skips_already_handled_day():
    start, _ = next_run_window(ny(2026, 11, 24, 9, 50), last_run_day=date(2026, 11, 24))
    assert start == ny(2026, 11, 25, 9, 45)


def test_next_run_uses_new_york_date_not_host_date():
    # 23:00 UTC Mon Nov 23 == 18:00 ET Mon Nov 23 -> next is Tue Nov 24
    now_utc = datetime(2026, 11, 23, 23, 0, tzinfo=timezone.utc)
    start, _ = next_run_window(now_utc)
    assert start == ny(2026, 11, 24, 9, 45)


# ========== wait_and_run ==========

class FakeClock:
    """Deterministic clock; sleeping advances time."""

    def __init__(self, now: datetime):
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


def test_wait_and_run_sleeps_until_window_then_runs_job_once():
    clock = FakeClock(ny(2026, 11, 24, 9, 0))
    job = MagicMock()

    handled = wait_and_run(job=job, now_fn=clock, sleep_fn=clock.sleep)

    job.assert_called_once()
    assert handled == date(2026, 11, 24)
    assert clock.now >= ny(2026, 11, 24, 9, 45)
    assert max(clock.sleeps) <= scheduler.MAX_SLEEP_SECONDS


def test_wait_and_run_runs_immediately_when_started_inside_window():
    clock = FakeClock(ny(2026, 11, 24, 9, 52))
    job = MagicMock()

    wait_and_run(job=job, now_fn=clock, sleep_fn=clock.sleep)

    job.assert_called_once()
    assert clock.sleeps == []


def test_wait_and_run_skips_day_when_woken_after_window():
    clock = FakeClock(ny(2026, 11, 24, 9, 0))
    job = MagicMock()

    def oversleep(seconds):          # simulate suspend: wake at 11:00
        clock.now = ny(2026, 11, 24, 11, 0)

    handled = wait_and_run(job=job, now_fn=clock, sleep_fn=oversleep)

    job.assert_not_called()
    assert handled == date(2026, 11, 24)


def test_wait_and_run_survives_job_failure():
    clock = FakeClock(ny(2026, 11, 24, 9, 50))
    job = MagicMock(side_effect=RuntimeError("LLM down"))

    handled = wait_and_run(job=job, now_fn=clock, sleep_fn=clock.sleep)

    job.assert_called_once()
    assert handled == date(2026, 11, 24)


def test_consecutive_calls_do_not_rerun_same_day():
    clock = FakeClock(ny(2026, 11, 24, 9, 50))
    job = MagicMock()

    day = wait_and_run(job=job, now_fn=clock, sleep_fn=clock.sleep)
    # Job finished inside the window; next call must roll to the next trading day
    day2 = wait_and_run(last_run_day=day, job=job, now_fn=clock, sleep_fn=clock.sleep)

    assert day2 == date(2026, 11, 25)
    assert job.call_count == 2
    assert clock.now >= ny(2026, 11, 25, 9, 45)


# ========== config validation ==========

def test_settings_reject_window_longer_than_30_minutes():
    with pytest.raises(ValidationError):
        Settings(scheduler_delay_minutes=20, scheduler_grace_minutes=20)


def test_settings_accept_15_plus_15():
    s = Settings(scheduler_delay_minutes=15, scheduler_grace_minutes=15)
    assert (s.scheduler_delay_minutes, s.scheduler_grace_minutes) == (15, 15)
