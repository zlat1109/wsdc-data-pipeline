"""Thu–Sun dance weekend helpers (WSDC-style weekend window)."""

from __future__ import annotations

from datetime import date, timedelta


def weekend_bounds(day: date) -> tuple[date, date]:
    """Return (Thursday, Sunday) for the dance weekend containing ``day``.

    Mon–Wed attach to the previous Thursday–Sunday window.
    """
    wd = day.weekday()  # Mon=0 … Sun=6
    if wd >= 3:  # Thu–Sun
        thursday = day - timedelta(days=wd - 3)
    else:
        thursday = day - timedelta(days=wd + 4)
    return thursday, thursday + timedelta(days=3)


def weekend_key(day: date) -> str:
    """Stable key ``YYYY-MM-DD`` of the weekend Thursday."""
    thursday, _ = weekend_bounds(day)
    return thursday.isoformat()
