"""Infer WSDC Tier and competitor ranges from observed placement points.

Rebuilt after catalog rebuild. Natural key:
(event_id, event_year, event_month, division, role, dance).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from transform.knowledge.tier_rules import (  # noqa: E402
    RULES_EDITIONS,
    TIER_DEFINITIONS,
    chart_vectors,
    edition_for_date,
    resolve_chart_version,
)

STATUS_MATCHED = "matched"
STATUS_LEGACY = "legacy_chart"
STATUS_NO_TIER = "no_tier_system"
STATUS_NO_POINTS = "no_points"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNMATCHED = "unmatched"

_AGGREGATE_SQL = """
SELECT
    r.event_id,
    r.event_year,
    r.event_month,
    r.division,
    r.role,
    COALESCE(NULLIF(trim(r.dance), ''), 'West Coast Swing') AS dance,
    ed.edition_id,
    MAX(r.points) FILTER (
        WHERE r.result_standardized = '1'
    ) AS observed_points_1,
    MAX(r.points) FILTER (
        WHERE r.result_standardized = '2'
    ) AS observed_points_2,
    MAX(r.points) FILTER (
        WHERE r.result_standardized = '3'
    ) AS observed_points_3,
    MAX(r.points) FILTER (
        WHERE r.result_standardized = '4'
    ) AS observed_points_4,
    MAX(r.points) FILTER (
        WHERE r.result_standardized = '5'
    ) AS observed_points_5,
    COUNT(*) FILTER (
        WHERE r.result_standardized = 'Final' AND COALESCE(r.points, 0) > 0
    )::int AS finalists,
    COUNT(DISTINCT r.dancer_id) FILTER (
        WHERE COALESCE(r.points, 0) > 0
    )::int AS scored_dancers
FROM core.results r
LEFT JOIN core.event_editions ed
    ON ed.event_id = r.event_id
   AND ed.event_year = r.event_year
   AND ed.event_month = r.event_month
WHERE r.event_id IS NOT NULL
  AND r.event_year IS NOT NULL
  AND r.event_month IS NOT NULL
  AND r.division IS NOT NULL
  AND r.role IS NOT NULL
GROUP BY
    r.event_id, r.event_year, r.event_month, r.division, r.role,
    COALESCE(NULLIF(trim(r.dance), ''), 'West Coast Swing'),
    ed.edition_id
"""

_INSERT_SQL = """
INSERT INTO core.edition_division_tiers (
    event_id, event_year, event_month, division, role, dance, edition_id,
    rules_version,
    observed_points_1, observed_points_2, observed_points_3,
    observed_points_4, observed_points_5,
    finalists, scored_dancers,
    tier, status, vector_distance, range_basis,
    rule_min_competitors, rule_max_competitors,
    est_min_competitors, est_max_competitors, range_conflict
) VALUES (
    %(event_id)s, %(event_year)s, %(event_month)s, %(division)s, %(role)s,
    %(dance)s, %(edition_id)s, %(rules_version)s,
    %(observed_points_1)s, %(observed_points_2)s, %(observed_points_3)s,
    %(observed_points_4)s, %(observed_points_5)s,
    %(finalists)s, %(scored_dancers)s,
    %(tier)s, %(status)s, %(vector_distance)s, %(range_basis)s,
    %(rule_min_competitors)s, %(rule_max_competitors)s,
    %(est_min_competitors)s, %(est_max_competitors)s, %(range_conflict)s
)
"""


@dataclass(frozen=True)
class TierMatch:
    tier: int | None
    status: str
    vector_distance: int
    rules_version: str | None
    range_basis: str | None
    rule_min: int | None
    rule_max: int | None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def observed_vector(row: dict[str, Any]) -> tuple[int | None, ...]:
    return tuple(_as_int(row.get(f"observed_points_{i}")) for i in range(1, 6))


def vector_l1_distance(
    observed: tuple[int | None, ...],
    chart: tuple[int, int, int, int, int],
) -> int | None:
    """L1 distance on placements where observed is not None. None if no overlap."""
    total = 0
    compared = 0
    for obs, exp in zip(observed, chart):
        if obs is None:
            continue
        total += abs(obs - exp)
        compared += 1
    if compared == 0:
        return None
    return total


def _defs_for_version(rules_version: str) -> dict[int, tuple[int, int | None]]:
    out: dict[int, tuple[int, int | None]] = {}
    for d in TIER_DEFINITIONS:
        if d.rules_version == rules_version:
            out[d.tier] = (d.min_competitors, d.max_competitors)
    return out


def match_vector(
    observed: tuple[int | None, ...],
    as_of: date,
    scored_dancers: int,
) -> TierMatch:
    ed = edition_for_date(as_of)
    if ed is None:
        return TierMatch(
            tier=None,
            status=STATUS_UNMATCHED,
            vector_distance=0,
            rules_version=None,
            range_basis=None,
            rule_min=None,
            rule_max=None,
        )

    if all(v is None or v == 0 for v in observed):
        if ed.tier_basis == "none":
            defs = _defs_for_version(ed.rules_version).get(0, (ed.min_role_competitors, None))
            return TierMatch(
                tier=0,
                status=STATUS_NO_POINTS,
                vector_distance=0,
                rules_version=ed.rules_version,
                range_basis="none",
                rule_min=defs[0],
                rule_max=defs[1],
            )
        return TierMatch(
            tier=None,
            status=STATUS_NO_POINTS,
            vector_distance=0,
            rules_version=ed.rules_version,
            range_basis=ed.tier_basis,
            rule_min=ed.min_role_competitors,
            rule_max=None,
        )

    if ed.tier_basis == "none":
        chart = chart_vectors(ed.rules_version)
        flat = chart.get(0)
        if flat is None:
            return TierMatch(None, STATUS_UNMATCHED, 0, ed.rules_version, "none", None, None)
        dist = vector_l1_distance(observed, flat)
        if dist == 0:
            status, distance = STATUS_NO_TIER, 0
        elif dist is not None:
            status, distance = STATUS_NO_TIER, dist
        else:
            status, distance = STATUS_UNMATCHED, 0
        defs = _defs_for_version(ed.rules_version).get(0, (ed.min_role_competitors, None))
        return TierMatch(0, status, distance, ed.rules_version, "none", defs[0], defs[1])

    # Exact match on current edition chart
    current = chart_vectors(ed.rules_version)
    exact = [
        tier
        for tier, pts in current.items()
        if vector_l1_distance(observed, pts) == 0
    ]
    if len(exact) == 1:
        tier = exact[0]
        lo, hi = _defs_for_version(ed.rules_version)[tier]
        return TierMatch(tier, STATUS_MATCHED, 0, ed.rules_version, ed.tier_basis, lo, hi)
    if len(exact) > 1:
        return TierMatch(None, STATUS_AMBIGUOUS, 0, ed.rules_version, ed.tier_basis, None, None)

    # Exact match on any other edition (legacy / transition)
    legacy_hits: list[tuple[str, int]] = []
    seen_owner_tier: set[tuple[str, int]] = set()
    for other in RULES_EDITIONS:
        if other.rules_version == ed.rules_version:
            continue
        owner = resolve_chart_version(other.rules_version)
        for tier, pts in chart_vectors(other.rules_version).items():
            if vector_l1_distance(observed, pts) != 0:
                continue
            key = (owner, tier)
            if key in seen_owner_tier:
                continue
            seen_owner_tier.add(key)
            legacy_hits.append((other.rules_version, tier))
    if len(legacy_hits) == 1:
        ver, tier = legacy_hits[0]
        lo, hi = _defs_for_version(ver)[tier]
        return TierMatch(tier, STATUS_LEGACY, 0, ver, ed.tier_basis, lo, hi)
    if len(legacy_hits) > 1:
        # Prefer the chronologically closest edition to as_of
        scored: list[tuple[int, str, int]] = []
        for ver, tier in legacy_hits:
            other = next(e for e in RULES_EDITIONS if e.rules_version == ver)
            end = other.valid_to or date(9999, 12, 31)
            scored.append((abs((end - as_of).days), ver, tier))
        scored.sort()
        if scored and (len(scored) == 1 or scored[0][0] < scored[1][0]):
            _, ver, tier = scored[0]
            lo, hi = _defs_for_version(ver)[tier]
            return TierMatch(tier, STATUS_LEGACY, 0, ver, ed.tier_basis, lo, hi)
        return TierMatch(None, STATUS_AMBIGUOUS, 0, ed.rules_version, ed.tier_basis, None, None)

    # Nearest on current chart
    candidates: list[tuple[int, int]] = []  # (distance, tier)
    for tier, pts in current.items():
        dist = vector_l1_distance(observed, pts)
        if dist is not None:
            candidates.append((dist, tier))
    if not candidates:
        return TierMatch(None, STATUS_UNMATCHED, 0, ed.rules_version, ed.tier_basis, None, None)

    candidates.sort()
    best_dist = candidates[0][0]
    best_tiers = [t for d, t in candidates if d == best_dist]
    if len(best_tiers) > 1:
        return TierMatch(None, STATUS_AMBIGUOUS, best_dist, ed.rules_version, ed.tier_basis, None, None)

    tier = best_tiers[0]
    lo, hi = _defs_for_version(ed.rules_version)[tier]
    return TierMatch(tier, STATUS_MATCHED, best_dist, ed.rules_version, ed.tier_basis, lo, hi)


def tighten_range(
    rule_min: int | None,
    rule_max: int | None,
    scored_dancers: int,
) -> tuple[int | None, int | None, bool]:
    if rule_min is None and rule_max is None:
        est_min = scored_dancers if scored_dancers > 0 else None
        return est_min, None, False
    lo = rule_min if rule_min is not None else 0
    est_min = max(lo, scored_dancers)
    conflict = rule_max is not None and scored_dancers > rule_max
    est_max = rule_max
    if conflict:
        # Keep rule_max as soft upper bound but flag conflict; est_min still scored.
        pass
    return est_min, est_max, conflict


def infer_row(row: dict[str, Any]) -> dict[str, Any]:
    year = int(row["event_year"])
    month = int(row["event_month"])
    as_of = date(year, month, 15)
    observed = observed_vector(row)
    scored = int(row.get("scored_dancers") or 0)
    match = match_vector(observed, as_of, scored)
    est_min, est_max, conflict = tighten_range(match.rule_min, match.rule_max, scored)

    return {
        "event_id": int(row["event_id"]),
        "event_year": year,
        "event_month": month,
        "division": row["division"],
        "role": row["role"],
        "dance": row["dance"],
        "edition_id": row.get("edition_id"),
        "rules_version": match.rules_version,
        "observed_points_1": observed[0],
        "observed_points_2": observed[1],
        "observed_points_3": observed[2],
        "observed_points_4": observed[3],
        "observed_points_5": observed[4],
        "finalists": int(row.get("finalists") or 0),
        "scored_dancers": scored,
        "tier": match.tier,
        "status": match.status,
        "vector_distance": match.vector_distance,
        "range_basis": match.range_basis,
        "rule_min_competitors": match.rule_min,
        "rule_max_competitors": match.rule_max,
        "est_min_competitors": est_min,
        "est_max_competitors": est_max,
        "range_conflict": conflict,
    }


def rebuild_edition_tiers(conn: Any) -> tuple[int, dict[str, int]]:
    """Truncate and rebuild core.edition_division_tiers. Returns (rows, status_counts)."""
    with conn.cursor() as cur:
        cur.execute(_AGGREGATE_SQL)
        columns = [d.name for d in cur.description]
        raw_rows = [dict(zip(columns, r)) for r in cur.fetchall()]

        inferred = [infer_row(r) for r in raw_rows]
        cur.execute("TRUNCATE core.edition_division_tiers")

        cols = [
            "event_id",
            "event_year",
            "event_month",
            "division",
            "role",
            "dance",
            "edition_id",
            "rules_version",
            "observed_points_1",
            "observed_points_2",
            "observed_points_3",
            "observed_points_4",
            "observed_points_5",
            "finalists",
            "scored_dancers",
            "tier",
            "status",
            "vector_distance",
            "range_basis",
            "rule_min_competitors",
            "rule_max_competitors",
            "est_min_competitors",
            "est_max_competitors",
            "range_conflict",
        ]
        placeholders = ", ".join(f"%({c})s" for c in cols)
        insert_sql = (
            "INSERT INTO core.edition_division_tiers ("
            + ", ".join(cols)
            + f") VALUES ({placeholders})"
        )
        batch_size = 500
        for i in range(0, len(inferred), batch_size):
            cur.executemany(insert_sql, inferred[i : i + batch_size])

        status_counts: dict[str, int] = {}
        for row in inferred:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    return len(inferred), status_counts
