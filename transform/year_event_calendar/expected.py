"""Expected (unconfirmed) YoY projection: prior-year start ±1 week (WSDC rules)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


EXPECTED_WINDOW_DAYS = 7
# Keep expected visible through the weekend + one week; then drop if still unconfirmed.
EXPECTED_STALE_GRACE_DAYS = 7


def project_start_to_year(start: date, target_year: int) -> date:
    """Map a prior-year start_date into ``target_year`` (same month/day)."""
    try:
        return start.replace(year=target_year)
    except ValueError:
        # Feb 29 → Feb 28 in non-leap years
        return date(target_year, 2, 28)


def within_expected_window(projected: date, actual: date, *, days: int = EXPECTED_WINDOW_DAYS) -> bool:
    return abs((actual - projected).days) <= days


def is_stale_expected(
    *,
    start: date,
    end: date | None,
    as_of: date,
    grace_days: int = EXPECTED_STALE_GRACE_DAYS,
) -> bool:
    """True when an expected row should leave the calendar.

    Past years never keep expected (only confirmed / hiatus / cancelled belong
    there). In the current/future year, expected expires once ``end`` (or start)
    plus grace days is before ``as_of`` — the projected weekend passed without
    confirmation or official hiatus/cancel.
    """
    if start.year < as_of.year:
        return True
    last = end if isinstance(end, date) else start
    return last + timedelta(days=grace_days) < as_of


def match_expected_to_confirmed(
    *,
    event_id: int | str,
    projected_start: date,
    confirmed_by_event: dict[int | str, list[date]],
    window_days: int = EXPECTED_WINDOW_DAYS,
) -> date | None:
    """Return matching confirmed start if within ±window_days, else None.

    ``confirmed_by_event`` may include starts from adjacent years so a NYE
    projection (e.g. 2026-12-31) is satisfied by a published Jan date in the
    next year (SwingCo 2027-01-07) and does not leave a ghost expected.
    """
    for actual in confirmed_by_event.get(event_id, []):
        if within_expected_window(projected_start, actual, days=window_days):
            return actual
    return None


def iter_expected_candidates(
    prior_rows: Iterable[dict],
    *,
    target_year: int,
    skip_event_ids: set[int | str],
) -> list[dict]:
    """Build expected stubs from prior-year day-dated editions.

    ``skip_event_ids`` should include any event already represented in the
    target year as confirmed, cancelled, or hiatus (per product rule: keep
    expected until explicit hiatus/cancelled — so once confirmed/cancelled/
    hiatus exists for that event_id in the year, do not emit expected).
    """
    out: list[dict] = []
    seen: set[int | str] = set()
    for row in prior_rows:
        eid = row.get("event_id")
        if eid is None or eid in skip_event_ids or eid in seen:
            continue
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        projected = project_start_to_year(start, target_year)
        if projected.year != target_year:
            continue
        seen.add(eid)
        stub = dict(row)
        stub["start_date"] = projected
        end = row.get("end_date")
        if isinstance(end, date):
            delta = (end - start).days
            stub["end_date"] = projected + timedelta(days=max(delta, 0))
        else:
            stub["end_date"] = None
        stub["status"] = "expected"
        stub["source"] = "expected_yoy"
        stub["kind"] = "registry"
        stub["year"] = target_year
        stub.pop("kind_from_schedule", None)
        stub["projected_from_year"] = start.year
        stub["projected_from_start"] = start.isoformat()
        out.append(stub)
    return out
