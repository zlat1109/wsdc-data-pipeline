"""Expected (unconfirmed) YoY projection: prior-year start ±1 week (WSDC rules)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable


EXPECTED_WINDOW_DAYS = 7
# Keep expected visible through the weekend + one week; then drop if still unconfirmed.
EXPECTED_STALE_GRACE_DAYS = 7
# Snap anniversary to the same weekday as the prior start (Thu→Thu, Fri→Fri).
# ±3 covers a full week uniquely without jumping to the next dance weekend.
EXPECTED_WEEKDAY_SNAP_DAYS = 3


def anniversary_date(start: date, target_year: int) -> date:
    """Same month/day in ``target_year`` (Feb 29 → Feb 28 in non-leap years)."""
    try:
        return start.replace(year=target_year)
    except ValueError:
        return date(target_year, 2, 28)


def snap_to_weekday(
    anchor: date,
    target_weekday: int,
    *,
    prefer_year: int | None = None,
) -> date:
    """Move ``anchor`` to the nearest day with ``target_weekday`` (Mon=0…Sun=6).

    Distance is always in ``[-3, 3]``. When the short snap leaves ``prefer_year``,
    try the opposite ±7 day candidate if it lands in that year (Jan/Dec edges).
    """
    delta = (target_weekday - anchor.weekday()) % 7
    if delta > EXPECTED_WEEKDAY_SNAP_DAYS:
        delta -= 7
    snapped = anchor + timedelta(days=delta)
    if prefer_year is None or snapped.year == prefer_year:
        return snapped
    alt = snapped + timedelta(days=7 if snapped.year < prefer_year else -7)
    if alt.year == prefer_year:
        return alt
    return snapped


def project_start_to_year(start: date, target_year: int) -> date:
    """Map a prior start into ``target_year``, preserving weekday near the anniversary.

    Naive month/day copy drifts ~1 weekday per year (Thu festivals land on Mon/Sun
    by year+2). Snap keeps typical Thu/Fri starts realistic for expected stubs.
    """
    anchor = anniversary_date(start, target_year)
    return snap_to_weekday(anchor, start.weekday(), prefer_year=target_year)


def project_end_from_prior(
    *,
    prior_start: date,
    prior_end: date | None,
    projected_start: date,
) -> date | None:
    """Keep the prior edition span when projecting end_date."""
    if not isinstance(prior_end, date):
        return None
    return projected_start + timedelta(days=max((prior_end - prior_start).days, 0))


def within_expected_window(projected: date, actual: date, *, days: int = EXPECTED_WINDOW_DAYS) -> bool:
    return abs((actual - projected).days) <= days


def is_stale_expected(
    *,
    start: date,
    end: date | None,
    as_of: date,
    grace_days: int = EXPECTED_STALE_GRACE_DAYS,
    event_year: int | None = None,
) -> bool:
    """True when an expected row should leave the calendar.

    Past **event/results years** never keep expected (only confirmed / hiatus /
    cancelled belong there). Use ``event_year`` when known so a Dec→Jan span
    snapped into the prior calendar year is not dropped on 1 Jan of the target
    year. Without ``event_year``, fall back to the span's end year (or start).

    In the current/future event year, expected expires once ``end`` (or start)
    plus grace days is before ``as_of``.
    """
    last = end if isinstance(end, date) else start
    ref_year = int(event_year) if event_year is not None else last.year
    if ref_year < as_of.year:
        return True
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
        # Allow Dec spill from weekday snap only when the span still touches target_year.
        end = project_end_from_prior(
            prior_start=start,
            prior_end=row.get("end_date") if isinstance(row.get("end_date"), date) else None,
            projected_start=projected,
        )
        touches_target = projected.year == target_year or (
            isinstance(end, date) and end.year == target_year
        )
        if not touches_target:
            continue
        seen.add(eid)
        stub = dict(row)
        stub["start_date"] = projected
        stub["end_date"] = end
        stub["status"] = "expected"
        stub["source"] = "expected_yoy"
        stub["kind"] = "registry"
        stub["year"] = target_year
        stub.pop("kind_from_schedule", None)
        stub["projected_from_year"] = start.year
        stub["projected_from_start"] = start.isoformat()
        out.append(stub)
    return out
