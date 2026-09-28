"""Map WSDC dump ``competitions`` rows onto our ``core.event_editions``.

WCS only. Division ids follow dump ``divisions.id`` → ``core.levels.level_id``.
Empty dump ``leader_tier`` / ``follower_tier`` are intentionally not loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

from transform.dump_edition_dates import (
    DumpEditionRow,
    _lookup_edition,
    canonical_event_id,
    edition_index,
    parse_date,
)

# dump divisions.id → our canonical core.levels.level
DUMP_DIVISION_ID_TO_LEVEL: dict[int, str] = {
    1: "Juniors",
    2: "Master",  # dump: Masters
    3: "Newcomer",
    4: "Novice",
    5: "Intermediate",
    6: "Advanced",
    7: "Champion",  # dump: Champions
    8: "All-Star",  # dump: All-Stars
    9: "Invitational",
    10: "Professional",
    12: "Sophisticated",
    13: "Teacher",
}

WCS_DANCE = "West Coast Swing"
WCS_DANCETYPE_ID = 1


@dataclass(frozen=True)
class DumpCompetitionRow:
    competition_id: int
    competitionevent_id: int
    dancetype_id: int
    division_id: int
    leader_count: int | None
    follower_count: int | None
    finals_count: int | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class EditionKeyRow:
    edition_id: int
    event_id: int
    event_year: int
    event_month: int
    start_date: date | None = None
    end_date: date | None = None
    event_name: str = ""


@dataclass(frozen=True)
class CompetitionLoadRow:
    competition_id: int
    competitionevent_id: int
    edition_id: int | None
    level_id: int
    level: str
    dance: str
    leader_count: int | None
    follower_count: int | None
    finals_count: int | None
    match_status: str
    dump_created_at: datetime | None
    dump_updated_at: datetime | None


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        return None


def parse_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def level_for_dump_division(division_id: int) -> str | None:
    return DUMP_DIVISION_ID_TO_LEVEL.get(int(division_id))


def build_ce_to_edition_id(
    dump_events: Sequence[DumpEditionRow],
    editions: Sequence[EditionKeyRow] | Iterable[Mapping[str, Any]],
) -> dict[int, int]:
    """Map dump ``competitionevents.id`` → our ``edition_id`` when matchable."""
    rows: list[EditionKeyRow] = []
    for raw in editions:
        if isinstance(raw, EditionKeyRow):
            rows.append(raw)
            continue
        rows.append(
            EditionKeyRow(
                edition_id=int(raw["edition_id"]),
                event_id=int(raw["event_id"]),
                event_year=int(raw["event_year"]),
                event_month=int(raw["event_month"]),
                start_date=parse_date(raw.get("start_date")),
                end_date=parse_date(raw.get("end_date")),
                event_name=str(raw.get("event_name") or ""),
            )
        )

    date_index = edition_index(
        [
            {
                "event_id": r.event_id,
                "event_year": r.event_year,
                "event_month": r.event_month,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "event_name": r.event_name,
            }
            for r in rows
        ]
    )
    edition_id_by_key = {
        (r.event_id, r.event_year, r.event_month): r.edition_id for r in rows
    }

    out: dict[int, int] = {}
    for dump in dump_events:
        if dump.start_date is None:
            continue
        canon = canonical_event_id(dump.series_event_id, dump.event_name)
        found = _lookup_edition(date_index, canon, dump.start_date, dump.end_date)
        if found is None:
            continue
        key, _ = found
        edition_id = edition_id_by_key.get(key)
        if edition_id is not None:
            out[dump.competitionevent_id] = edition_id
    return out


def plan_competition_rows(
    competitions: Sequence[DumpCompetitionRow],
    ce_to_edition: Mapping[int, int],
    *,
    wcs_only: bool = True,
) -> list[CompetitionLoadRow]:
    """Build load rows; unmatched keep ``edition_id=None`` for investigation."""
    planned: list[CompetitionLoadRow] = []
    for row in competitions:
        if wcs_only and int(row.dancetype_id) != WCS_DANCETYPE_ID:
            continue
        level = level_for_dump_division(row.division_id)
        if level is None:
            # Not insertable (no core.levels row); caller counts via summary filter.
            continue
        edition_id = ce_to_edition.get(row.competitionevent_id)
        planned.append(
            CompetitionLoadRow(
                competition_id=row.competition_id,
                competitionevent_id=row.competitionevent_id,
                edition_id=edition_id,
                level_id=int(row.division_id),
                level=level,
                dance=WCS_DANCE,
                leader_count=row.leader_count,
                follower_count=row.follower_count,
                finals_count=row.finals_count,
                match_status="matched" if edition_id is not None else "unmatched",
                dump_created_at=row.created_at,
                dump_updated_at=row.updated_at,
            )
        )
    return planned


def count_skipped_divisions(
    competitions: Sequence[DumpCompetitionRow], *, wcs_only: bool = True
) -> int:
    n = 0
    for row in competitions:
        if wcs_only and int(row.dancetype_id) != WCS_DANCETYPE_ID:
            continue
        if level_for_dump_division(row.division_id) is None:
            n += 1
    return n


def summarize_plans(rows: Sequence[CompetitionLoadRow]) -> dict[str, int]:
    summary = {
        "total": len(rows),
        "matched": 0,
        "unmatched": 0,
        "with_both_counts": 0,
    }
    for row in rows:
        summary[row.match_status] = summary.get(row.match_status, 0) + 1
        if row.leader_count is not None and row.follower_count is not None:
            summary["with_both_counts"] += 1
    return summary
