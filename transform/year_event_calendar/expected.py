"""Expected (unconfirmed) YoY projection: prior-year start ±1 week (WSDC rules)."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Iterable


EXPECTED_WINDOW_DAYS = 7
# Keep expected visible through the weekend + one week; then drop if still unconfirmed.
EXPECTED_STALE_GRACE_DAYS = 7
# Snap anniversary to the same weekday as the prior start (Thu→Thu, Fri→Fri).
# ±3 covers a full week uniquely without jumping to the next dance weekend.
EXPECTED_WEEKDAY_SNAP_DAYS = 3
# Unlinked YoY bridge: do not resurrect list-only rows older than
# ``as_of.year - UNLINKED_PRIOR_LOOKBACK_YEARS`` (0 = current year and later
# published list years only).
UNLINKED_PRIOR_LOOKBACK_YEARS = 0

# Light stopwords for provisional unlinked series keys (avoid importing build).
_UNLINKED_KEY_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "of",
        "for",
        "wcs",
        "west",
        "coast",
        "swing",
        "dance",
        "trial",
        "event",
        "festival",
        "fest",
        "open",
        "championships",
        "championship",
    }
)


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


def match_expected_to_starts(
    *,
    series_key: int | str,
    projected_start: date,
    confirmed_starts_by_key: dict[int | str, list[date]],
    window_days: int = EXPECTED_WINDOW_DAYS,
) -> date | None:
    """Return a confirmed start within ±window_days for ``series_key``, else None.

    ``series_key`` is a catalog ``event_id`` or an unlinked series name key.
    ``confirmed_starts_by_key`` may include adjacent years so a NYE projection
    (e.g. 2026-12-31) is satisfied by a published Jan date in the next year.
    """
    for actual in confirmed_starts_by_key.get(series_key, []):
        if within_expected_window(projected_start, actual, days=window_days):
            return actual
    return None


def match_expected_to_confirmed(
    *,
    event_id: int | str,
    projected_start: date,
    confirmed_by_event: dict[int | str, list[date]],
    window_days: int = EXPECTED_WINDOW_DAYS,
) -> date | None:
    """Backward-compatible alias for :func:`match_expected_to_starts`."""
    return match_expected_to_starts(
        series_key=event_id,
        projected_start=projected_start,
        confirmed_starts_by_key=confirmed_by_event,
        window_days=window_days,
    )


def unlinked_series_key(
    *,
    name: str | None,
    country: str | None = None,
    city: str | None = None,
) -> str | None:
    """Stable key for provisional YoY stubs of list-only rows (no event_id).

    Uses alnum tokens minus light stopwords, drops a trailing city token when
    ``city`` is known, and strips edition-year suffixes (``… 2027``).
    """
    raw_tokens = re.findall(r"[a-z0-9]+", str(name or "").lower())
    if not raw_tokens:
        return None
    tokens = [tok for tok in raw_tokens if tok not in _UNLINKED_KEY_STOPWORDS]
    if not tokens:
        tokens = list(raw_tokens)
    city_tokens = re.findall(r"[a-z0-9]+", str(city or "").lower())
    if city_tokens and len(tokens) > len(city_tokens) and tokens[-len(city_tokens) :] == city_tokens:
        tokens = tokens[: -len(city_tokens)]
    # Drop edition-year suffixes in titles ("H-Town Throw Down 2027").
    tokens = [
        tok
        for tok in tokens
        if not (tok.isdigit() and len(tok) == 4 and tok.startswith("20"))
    ]
    if not tokens:
        tokens = list(raw_tokens)
    country_norm = " ".join(str(country or "").strip().lower().split())
    return f"{' '.join(tokens)}|{country_norm}"


# Backward-compatible alias (older call sites / tests).
unlinked_trial_series_key = unlinked_series_key


def _project_expected_stub(
    row: dict[str, Any],
    *,
    target_year: int,
    kind: str,
    provisional_unlinked: bool = False,
    unlinked_key: str | None = None,
) -> dict[str, Any] | None:
    """Shared YoY stub builder for catalog-backed and provisional unlinked rows."""
    start = row.get("start_date")
    if not isinstance(start, date):
        return None
    # Results year may be end-year for Dec→Jan weekends (year=2027, start=2026-12-30).
    # Project into the same calendar-year offset so NYE expected stay Dec→Jan, not
    # collapsed into late December of the results year.
    prior_results_year = int(row.get("year") or start.year)
    start_cal_year = target_year + (start.year - prior_results_year)
    projected = project_start_to_year(start, start_cal_year)
    end = project_end_from_prior(
        prior_start=start,
        prior_end=row.get("end_date") if isinstance(row.get("end_date"), date) else None,
        projected_start=projected,
    )
    touches_target = projected.year == target_year or (
        isinstance(end, date) and end.year == target_year
    )
    if not touches_target:
        return None
    stub = dict(row)
    stub["start_date"] = projected
    stub["end_date"] = end
    stub["status"] = "expected"
    stub["source"] = "expected_yoy"
    stub["kind"] = kind
    stub["year"] = target_year
    stub.pop("kind_from_schedule", None)
    if provisional_unlinked:
        stub["provisional_unlinked"] = True
        if unlinked_key:
            stub["unlinked_key"] = unlinked_key
    else:
        stub.pop("provisional_unlinked", None)
        stub.pop("unlinked_key", None)
    stub.pop("provisional_unlinked_trial", None)
    stub.pop("unlinked_trial_key", None)
    stub["projected_from_year"] = start.year
    stub["projected_from_start"] = start.isoformat()
    return stub


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
        stub = _project_expected_stub(row, target_year=target_year, kind="registry")
        if stub is None:
            continue
        seen.add(eid)
        out.append(stub)
    return out


def iter_unlinked_expected_candidates(
    prior_rows: Iterable[dict],
    *,
    target_year: int,
    skip_keys: set[str],
) -> list[dict]:
    """Project confirmed list-only rows (no catalog event_id) into ``target_year``.

    Temporary YoY bridge until a normal ``event_id`` appears. Future stubs are
    **Registry** and keep ``provisional_unlinked`` for debug. Callers choose
    which prior years to feed (lookback is enforced upstream).
    """
    out: list[dict] = []
    seen: set[str] = set()
    for row in prior_rows:
        if row.get("event_id") is not None:
            continue
        key = unlinked_series_key(
            name=row.get("name"),
            country=row.get("country"),
            city=row.get("city"),
        )
        if not key or key in skip_keys or key in seen:
            continue
        stub = _project_expected_stub(
            row,
            target_year=target_year,
            kind="registry",
            provisional_unlinked=True,
            unlinked_key=key,
        )
        if stub is None:
            continue
        seen.add(key)
        out.append(stub)
    return out


# Backward-compatible alias.
iter_unlinked_trial_expected_candidates = iter_unlinked_expected_candidates
