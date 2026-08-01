"""Bikram Sambat calendar helpers — presentation layer only.

PROJECT_PLAN.md Phase 3: streaks and schedules must use the Bikram Sambat (BS) calendar,
the civil calendar in Nepal. Scheduling *math* stays in UTC (see scheduler.py); BS is
applied only when showing dates and computing day-boundary streaks for Nepali users.

Wraps ``nepali-datetime`` when installed; degrades to ISO Gregorian otherwise so the app
never hard-fails on a missing optional dependency.
"""

from __future__ import annotations

from datetime import date


def to_bs_string(g: date) -> str:
    """Format a Gregorian date as a Bikram Sambat date string (YYYY-MM-DD BS)."""
    try:
        import nepali_datetime

        bs = nepali_datetime.date.from_datetime_date(g)
        return f"{bs.year:04d}-{bs.month:02d}-{bs.day:02d} BS"
    except Exception:
        return g.isoformat()  # fallback: Gregorian ISO


def same_bs_day(a: date, b: date) -> bool:
    """Whether two dates fall on the same BS calendar day (for streak counting)."""
    return to_bs_string(a) == to_bs_string(b)
