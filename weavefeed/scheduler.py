"""
Scheduler for the Weavefeed prediction workflow.

Runs main.main() once per US trading day, 15-30 minutes after the NQ Regular
Trading Hours (RTH) open at 09:30 America/New_York:

    run window = [open + SCHEDULER_DELAY_MINUTES,
                  open + SCHEDULER_DELAY_MINUTES + SCHEDULER_GRACE_MINUTES]

Behaviour:
- Normally fires at the start of the window (default 09:45 ET).
- If the process starts or wakes inside the window (restart, laptop resume),
  it fires immediately. If it wakes after the window has closed, that day is
  skipped: a "start of day" prediction made later would be stale.
- Weekends and NYSE full-day holidays are skipped.
- A failing workflow run is logged and does not stop the scheduler.
- At most one run per trading day per process. State is in-memory only, so
  restarting inside the window after a successful run will run again.

Usage (from the weavefeed/ directory):
    python scheduler.py                 # run forever
    python scheduler.py --print-next    # show the next run window and exit

Does NOT perform evaluation (see evaluate.py).
"""

import argparse
import logging
import time as time_module
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from config import settings
from market_calendar import NY_TZ, RTH_OPEN, is_trading_day, market_now

logger = logging.getLogger(__name__)

# Upper bound on a single sleep so the loop re-checks the wall clock often
# and recovers promptly from suspend/resume or clock adjustments.
MAX_SLEEP_SECONDS = 30.0


def run_window(
    day: date,
    delay_minutes: Optional[int] = None,
    grace_minutes: Optional[int] = None,
) -> tuple[datetime, datetime]:
    """Return the (start, end) New York datetimes of the run window for `day`."""
    delay = settings.scheduler_delay_minutes if delay_minutes is None else delay_minutes
    grace = settings.scheduler_grace_minutes if grace_minutes is None else grace_minutes
    start = datetime.combine(day, RTH_OPEN, tzinfo=NY_TZ) + timedelta(minutes=delay)
    return start, start + timedelta(minutes=grace)


def next_run_window(
    now: datetime,
    last_run_day: Optional[date] = None,
) -> tuple[datetime, datetime]:
    """
    Find the next run window that has not yet closed.

    Args:
        now: Current time (timezone-aware).
        last_run_day: Trading day already handled; it and earlier days are skipped.

    Returns:
        (start, end) of the window. `start` may be in the past when `now`
        falls inside the window, meaning "run immediately".
    """
    day = now.astimezone(NY_TZ).date()
    while True:
        if is_trading_day(day) and (last_run_day is None or day > last_run_day):
            start, end = run_window(day)
            if now < end:
                return start, end
        day += timedelta(days=1)


def _default_job() -> None:
    # Imported lazily so `--print-next` and tests do not need DB/LLM dependencies.
    from main import main

    main()


def wait_and_run(
    last_run_day: Optional[date] = None,
    job: Callable[[], None] = _default_job,
    now_fn: Callable[[], datetime] = market_now,
    sleep_fn: Callable[[float], None] = time_module.sleep,
) -> date:
    """
    Block until the next run window opens, then run `job` once.

    Returns:
        The trading day that was handled (run or skipped), to pass back in as
        `last_run_day` on the next call.
    """
    start, end = next_run_window(now_fn(), last_run_day)
    day = start.date()
    logger.info(
        f"Next prediction run: {start:%Y-%m-%d %H:%M %Z} "
        f"(window closes {end:%H:%M %Z})"
    )

    while (remaining := (start - now_fn()).total_seconds()) > 0:
        sleep_fn(min(remaining, MAX_SLEEP_SECONDS))

    if now_fn() >= end:
        logger.warning(f"Missed run window for {day} (woke after {end:%H:%M %Z}); skipping")
        return day

    try:
        job()
    except Exception:
        logger.exception(f"Prediction workflow failed for {day}")
    return day


def run_forever() -> None:
    """Run the prediction workflow on every trading day until interrupted."""
    logger.info(
        f"Scheduler started (delay={settings.scheduler_delay_minutes}m, "
        f"grace={settings.scheduler_grace_minutes}m after "
        f"{RTH_OPEN:%H:%M} {NY_TZ.key})"
    )
    last_run_day: Optional[date] = None
    while True:
        last_run_day = wait_and_run(last_run_day)


def cli(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--print-next",
        action="store_true",
        help="print the next run window and exit",
    )
    args = parser.parse_args(argv)

    if args.print_next:
        start, end = next_run_window(market_now())
        print(f"{start:%Y-%m-%d %H:%M %Z} -> {end:%H:%M %Z}")
        return

    try:
        run_forever()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    cli()
