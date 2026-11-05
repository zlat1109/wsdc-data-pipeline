"""Conflict checks: CR enrichment must not invent or contradict core entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from transform.competition_results.build import CrTables


@dataclass
class ConflictReport:
    issues: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def check_built_tables_against_core(
    tables: CrTables,
    *,
    known_dancer_ids: set[int],
    edition_event_ids: Mapping[int, int],
) -> ConflictReport:
    """Offline checks on built rows before/after load.

    ``edition_event_ids`` maps ``edition_id → event_id`` from core.event_editions.
    """
    report = ConflictReport()
    orphan_dancer = orphan_partner = 0
    identity_mismatch = 0
    redacted_named = 0
    orphan_edition = 0
    event_mismatch = 0
    matched_null = unmatched_set = 0
    unknown_level = 0

    # Levels we may emit (must exist in core.levels).
    allowed_levels = {
        "Newcomer",
        "Novice",
        "Intermediate",
        "Advanced",
        "All-Star",
        "Champion",
        "Master",
        "Sophisticated",
        "Juniors",
        "Invitational",
        "Professional",
        "Teacher",
    }

    for row in tables.round_results:
        did = _as_int(row.get("dancer_id"))
        if did is not None and did not in known_dancer_ids:
            orphan_dancer += 1
        pid = _as_int(row.get("partner_dancer_id"))
        if pid is not None and pid not in known_dancer_ids:
            orphan_partner += 1
        ident = str(row.get("cr_identity") or "")
        if did is not None and ident.isdigit() and did != int(ident):
            identity_mismatch += 1
        if ident.lower() == "redacted" and row.get("competitor_name"):
            redacted_named += 1

    for row in tables.editions:
        eid = _as_int(row.get("edition_id"))
        status = row.get("match_status")
        if status == "matched" and eid is None:
            matched_null += 1
        if status == "unmatched" and eid is not None:
            unmatched_set += 1
        if eid is not None and eid not in edition_event_ids:
            orphan_edition += 1
        elif eid is not None:
            canon = _as_int(row.get("canonical_event_id"))
            core_event = edition_event_ids[eid]
            if canon is not None and canon != core_event:
                event_mismatch += 1

    for row in tables.divisions:
        level = row.get("level")
        if level is not None and level not in allowed_levels:
            unknown_level += 1

    report.counts = {
        "orphan_dancer_fk": orphan_dancer,
        "orphan_partner_fk": orphan_partner,
        "dancer_id_ne_identity": identity_mismatch,
        "redacted_with_name": redacted_named,
        "orphan_edition_fk": orphan_edition,
        "edition_event_id_mismatch": event_mismatch,
        "matched_without_edition": matched_null,
        "unmatched_with_edition": unmatched_set,
        "unknown_level": unknown_level,
    }
    labels = {
        "orphan_dancer_fk": "dancer_id not in core.dancers",
        "orphan_partner_fk": "partner_dancer_id not in core.dancers",
        "dancer_id_ne_identity": "dancer_id ≠ numeric cr_identity",
        "redacted_with_name": "redacted competitor has a name",
        "orphan_edition_fk": "edition_id not in core.event_editions",
        "edition_event_id_mismatch": "canonical_event_id ≠ core edition event_id",
        "matched_without_edition": "match_status=matched but edition_id NULL",
        "unmatched_with_edition": "match_status=unmatched but edition_id set",
        "unknown_level": "level not in core.levels vocabulary",
    }
    for key, n in report.counts.items():
        if n:
            report.issues.append(f"{labels[key]}: {n}")
    return report


def assert_no_core_mutation_targets() -> tuple[str, ...]:
    """Tables CR loader must never write (parallel enrichment only)."""
    return (
        "core.results",
        "core.dancers",
        "core.events",
        "core.event_editions",
        "core.dancer_points",
        "core.dancer_roles",
        "core.locations",
    )


# SQL probes for live DB (max_value = 0).
CONFLICT_SQL: dict[str, str] = {
    "cr_orphan_dancer_fk": """
        SELECT count(*) FROM core.cr_round_results rr
        WHERE rr.dancer_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM core.dancers d WHERE d.dancer_id = rr.dancer_id
          )
    """,
    "cr_orphan_partner_fk": """
        SELECT count(*) FROM core.cr_round_results rr
        WHERE rr.partner_dancer_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM core.dancers d WHERE d.dancer_id = rr.partner_dancer_id
          )
    """,
    "cr_orphan_edition_fk": """
        SELECT count(*) FROM core.cr_editions e
        WHERE e.edition_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM core.event_editions ed WHERE ed.edition_id = e.edition_id
          )
    """,
    "cr_orphan_level_fk": """
        SELECT count(*) FROM core.cr_divisions d
        WHERE d.level IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM core.levels l WHERE l.level = d.level)
    """,
    "cr_dancer_id_ne_identity": """
        SELECT count(*) FROM core.cr_round_results rr
        WHERE rr.dancer_id IS NOT NULL
          AND rr.cr_identity ~ '^[0-9]+$'
          AND rr.dancer_id <> rr.cr_identity::int
    """,
    "cr_edition_event_id_mismatch": """
        SELECT count(*) FROM core.cr_editions e
        JOIN core.event_editions ed ON ed.edition_id = e.edition_id
        WHERE e.canonical_event_id IS NOT NULL
          AND e.canonical_event_id <> ed.event_id
    """,
    "cr_matched_without_edition": """
        SELECT count(*) FROM core.cr_editions
        WHERE match_status = 'matched' AND edition_id IS NULL
    """,
    "cr_unmatched_with_edition": """
        SELECT count(*) FROM core.cr_editions
        WHERE match_status = 'unmatched' AND edition_id IS NOT NULL
    """,
    "cr_redacted_with_name": """
        SELECT count(*) FROM core.cr_round_results
        WHERE cr_identity = 'redacted' AND competitor_name IS NOT NULL
    """,
}


def run_live_conflict_checks(conn) -> ConflictReport:
    """Execute CONFLICT_SQL against an open DB connection."""
    report = ConflictReport()
    with conn.cursor() as cur:
        for name, sql in CONFLICT_SQL.items():
            cur.execute(sql)
            n = int(cur.fetchone()[0])
            report.counts[name] = n
            if n:
                report.issues.append(f"{name}: {n}")
    return report
