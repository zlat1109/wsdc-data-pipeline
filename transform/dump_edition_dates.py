"""Plan edition start/end fills from a WSDC clone ``competitionevents`` extract.

Match key (dump schema nuance):
  ``competitionevents.event_id`` = series registry id (= our ``event_id``),
  NOT ``competitionevents.id`` (per-edition PK).

Identity: series id → ``MERGE_EVENT_ID_MAP`` → existing ``(event_id, year, month)``.
Soul Flow rows titled as such map to ``SOUL_FLOW_PROVISIONAL_EVENT_ID``.

Stub = missing dates OR same-month day-1 / day-1 sentinel.
Auto-fill only when ours is stub and dump has day-precision.
Day≠day mismatches → conflict report only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from transform.knowledge.calendar_operator_overrides import SOUL_FLOW_PROVISIONAL_EVENT_ID
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

DATE_SOURCE_DUMP = "wsdc_dump"


@dataclass(frozen=True)
class DumpEditionRow:
    competitionevent_id: int
    series_event_id: int
    event_name: str
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class EditionDateRow:
    event_id: int
    event_year: int
    event_month: int
    start_date: date | None
    end_date: date | None
    event_name: str = ""


@dataclass(frozen=True)
class DatePlanRow:
    action: str  # fill | conflict | dump_stub | match | no_edition | skip_invalid | skip_duplicate
    dump_competitionevent_id: int
    dump_series_event_id: int
    canonical_event_id: int
    event_year: int
    event_month: int
    event_name: str
    dump_start: date | None
    dump_end: date | None
    ours_start: date | None
    ours_end: date | None


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if text.startswith("0000"):
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def is_month_stub(start: date | None, end: date | None) -> bool:
    """True when there is no real day-precision range."""
    if start is None or end is None:
        return True
    return (
        start.day == 1
        and end.day == 1
        and start.month == end.month
        and start.year == end.year
    )


def is_day_precision(start: date | None, end: date | None) -> bool:
    return start is not None and end is not None and not is_month_stub(start, end)


def is_valid_day_range(start: date | None, end: date | None) -> bool:
    """Day-precision with end >= start (rejects dump bot year typos)."""
    return is_day_precision(start, end) and end >= start  # type: ignore[operator]


def _dump_row_rank(row: DumpEditionRow) -> tuple[int, int, int]:
    """Higher is better: valid range, not Unconfirmed, newer competitionevent id."""
    name = (row.event_name or "").lower()
    valid = 1 if is_valid_day_range(row.start_date, row.end_date) else 0
    confirmed = 0 if "unconfirmed" in name else 1
    return (valid, confirmed, row.competitionevent_id)


def canonical_event_id(series_event_id: int, event_name: str = "") -> int:
    name = (event_name or "").strip().lower()
    if "soul flow" in name:
        return SOUL_FLOW_PROVISIONAL_EVENT_ID
    cur = int(series_event_id)
    seen: set[int] = set()
    while cur in MERGE_EVENT_ID_MAP and cur not in seen:
        seen.add(cur)
        cur = int(MERGE_EVENT_ID_MAP[cur])
    return cur


def load_competitionevents_tsv(path: Path | str) -> list[DumpEditionRow]:
    """Load non-PII slice: id, event_id, event_name, start_date, end_date[, ...]."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    out: list[DumpEditionRow] = []
    for line in text.splitlines():
        line = line.strip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        # Skip header if present
        if parts[0].lower() in {"id", "competitionevent_id"}:
            continue
        try:
            ce_id = int(parts[0])
            series_id = int(parts[1])
        except ValueError:
            continue
        out.append(
            DumpEditionRow(
                competitionevent_id=ce_id,
                series_event_id=series_id,
                event_name=parts[2] or "",
                start_date=parse_date(parts[3]),
                end_date=parse_date(parts[4]),
            )
        )
    return out


def edition_index(
    editions: Sequence[EditionDateRow] | Iterable[Mapping[str, Any]],
) -> dict[tuple[int, int, int], EditionDateRow]:
    out: dict[tuple[int, int, int], EditionDateRow] = {}
    for raw in editions:
        if isinstance(raw, EditionDateRow):
            row = raw
        else:
            row = EditionDateRow(
                event_id=int(raw["event_id"]),
                event_year=int(raw["event_year"]),
                event_month=int(raw["event_month"]),
                start_date=parse_date(raw.get("start_date")),
                end_date=parse_date(raw.get("end_date")),
                event_name=str(raw.get("event_name") or raw.get("canonical_name") or ""),
            )
        out[(row.event_id, row.event_year, row.event_month)] = row
    return out


def _lookup_edition(
    index: dict[tuple[int, int, int], EditionDateRow],
    event_id: int,
    start: date,
    end: date | None,
) -> tuple[tuple[int, int, int], EditionDateRow] | None:
    key = (event_id, start.year, start.month)
    hit = index.get(key)
    if hit is not None:
        return key, hit
    if end is not None and (end.year, end.month) != (start.year, start.month):
        key2 = (event_id, end.year, end.month)
        hit2 = index.get(key2)
        if hit2 is not None:
            return key2, hit2
    return None


def plan_dump_edition_dates(
    dump_rows: Sequence[DumpEditionRow],
    editions: Sequence[EditionDateRow] | Iterable[Mapping[str, Any]],
) -> list[DatePlanRow]:
    """Plan one action per dump row, but prefer the best dump row per edition.

    When several ``competitionevents`` map to the same ``(event_id, y, m)``
    (Unconfirmed draft + Active final, or bot year typos), only the highest-ranked
    row can ``fill`` / ``conflict`` / ``match``; losers become ``skip_invalid``.
    """
    index = edition_index(editions)
    plans: list[DatePlanRow] = []
    # edition key → (rank, plan_index of winner candidate)
    best_for_edition: dict[tuple[int, int, int], tuple[tuple[int, int, int], int]] = {}

    def _append(plan: DatePlanRow) -> int:
        plans.append(plan)
        return len(plans) - 1

    for dump in dump_rows:
        if dump.start_date is None:
            _append(
                DatePlanRow(
                    action="skip_invalid",
                    dump_competitionevent_id=dump.competitionevent_id,
                    dump_series_event_id=dump.series_event_id,
                    canonical_event_id=canonical_event_id(
                        dump.series_event_id, dump.event_name
                    ),
                    event_year=0,
                    event_month=0,
                    event_name=dump.event_name,
                    dump_start=dump.start_date,
                    dump_end=dump.end_date,
                    ours_start=None,
                    ours_end=None,
                )
            )
            continue

        # Reject end-before-start (and similar bot typos) up front.
        if dump.end_date is not None and dump.end_date < dump.start_date:
            _append(
                DatePlanRow(
                    action="skip_invalid",
                    dump_competitionevent_id=dump.competitionevent_id,
                    dump_series_event_id=dump.series_event_id,
                    canonical_event_id=canonical_event_id(
                        dump.series_event_id, dump.event_name
                    ),
                    event_year=dump.start_date.year,
                    event_month=dump.start_date.month,
                    event_name=dump.event_name,
                    dump_start=dump.start_date,
                    dump_end=dump.end_date,
                    ours_start=None,
                    ours_end=None,
                )
            )
            continue

        canon = canonical_event_id(dump.series_event_id, dump.event_name)
        found = _lookup_edition(index, canon, dump.start_date, dump.end_date)
        if found is None:
            _append(
                DatePlanRow(
                    action="no_edition",
                    dump_competitionevent_id=dump.competitionevent_id,
                    dump_series_event_id=dump.series_event_id,
                    canonical_event_id=canon,
                    event_year=dump.start_date.year,
                    event_month=dump.start_date.month,
                    event_name=dump.event_name,
                    dump_start=dump.start_date,
                    dump_end=dump.end_date,
                    ours_start=None,
                    ours_end=None,
                )
            )
            continue

        (eid, year, month), ours = found
        dump_stub = is_month_stub(dump.start_date, dump.end_date)
        ours_stub = is_month_stub(ours.start_date, ours.end_date)

        if dump_stub:
            action = "dump_stub"
        elif ours_stub:
            action = "fill"
        elif ours.start_date == dump.start_date and ours.end_date == dump.end_date:
            action = "match"
        else:
            action = "conflict"

        plan = DatePlanRow(
            action=action,
            dump_competitionevent_id=dump.competitionevent_id,
            dump_series_event_id=dump.series_event_id,
            canonical_event_id=eid,
            event_year=year,
            event_month=month,
            event_name=dump.event_name or ours.event_name,
            dump_start=dump.start_date,
            dump_end=dump.end_date,
            ours_start=ours.start_date,
            ours_end=ours.end_date,
        )
        idx = _append(plan)
        ed_key = (eid, year, month)
        rank = _dump_row_rank(dump)
        prev = best_for_edition.get(ed_key)
        if prev is None or rank > prev[0]:
            if prev is not None:
                # Demote previous winner — duplicate draft / stale row.
                old = plans[prev[1]]
                plans[prev[1]] = DatePlanRow(
                    action="skip_duplicate",
                    dump_competitionevent_id=old.dump_competitionevent_id,
                    dump_series_event_id=old.dump_series_event_id,
                    canonical_event_id=old.canonical_event_id,
                    event_year=old.event_year,
                    event_month=old.event_month,
                    event_name=old.event_name,
                    dump_start=old.dump_start,
                    dump_end=old.dump_end,
                    ours_start=old.ours_start,
                    ours_end=old.ours_end,
                )
            best_for_edition[ed_key] = (rank, idx)
        else:
            plans[idx] = DatePlanRow(
                action="skip_duplicate",
                dump_competitionevent_id=plan.dump_competitionevent_id,
                dump_series_event_id=plan.dump_series_event_id,
                canonical_event_id=plan.canonical_event_id,
                event_year=plan.event_year,
                event_month=plan.event_month,
                event_name=plan.event_name,
                dump_start=plan.dump_start,
                dump_end=plan.dump_end,
                ours_start=plan.ours_start,
                ours_end=plan.ours_end,
            )
    return plans


def summarize_plans(plans: Sequence[DatePlanRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in plans:
        counts[row.action] = counts.get(row.action, 0) + 1
    return counts


def fill_rows_for_upsert(
    plans: Sequence[DatePlanRow],
    *,
    scraped_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Payloads for ``upsert_edition_calendar_dates`` (fill actions only)."""
    from datetime import timezone

    now = scraped_at or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()
    for row in plans:
        if row.action != "fill":
            continue
        if not is_valid_day_range(row.dump_start, row.dump_end):
            continue
        key = (row.canonical_event_id, row.event_year, row.event_month)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "event_id": row.canonical_event_id,
                "event_year": row.event_year,
                "event_month": row.event_month,
                "planned_start_date": row.dump_start,
                "planned_end_date": row.dump_end,
                "calendar_status": "scheduled",
                "date_source": DATE_SOURCE_DUMP,
                "source_fingerprint": (
                    f"dump:competitionevents:{row.dump_competitionevent_id}"
                ),
                "calendar_title": row.event_name or None,
                "url": None,
                "match_via": "dump_competitionevents_series_id",
                "scraped_at": now,
                "updated_at": now,
            }
        )
    return out


def plans_as_dicts(plans: Sequence[DatePlanRow]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plan in plans:
        d = asdict(plan)
        for key in ("dump_start", "dump_end", "ours_start", "ours_end"):
            val = d[key]
            d[key] = val.isoformat() if isinstance(val, date) else None
        rows.append(d)
    return rows
