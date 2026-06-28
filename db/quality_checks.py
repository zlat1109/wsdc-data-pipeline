"""Post-load Supabase quality checks aligned with preprocess audit codes.

Each check maps to a historical data-quality problem and its fix layer:
  - parse/preprocess knowledge maps
  - repair scripts
  - manual review items from quality_reports/latest.json
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warn", "info"]


@dataclass(frozen=True)
class QualityCheck:
    name: str
    sql: str
    max_value: int
    severity: Severity
    category: str
    description: str
    fix_hint: str = ""


# Core invariants (CI gate — must stay error).
CORE_CHECKS: tuple[QualityCheck, ...] = (
    QualityCheck(
        name="results_null_location_id",
        sql="SELECT count(*) FROM core.results WHERE location_id IS NULL",
        max_value=0,
        severity="error",
        category="location",
        description="Cloud parse drops location_id; resolve.py backfills from event_location.",
        fix_hint="Run preprocess + load, or scripts/repair_results_location.py",
    ),
    QualityCheck(
        name="split_names_same_geo",
        sql="""
        WITH per AS (
            SELECT r.event_name_raw, r.event_id,
                   mode() WITHIN GROUP (ORDER BY l.event_city) AS city,
                   mode() WITHIN GROUP (ORDER BY l.event_country) AS country
            FROM core.results r
            LEFT JOIN core.locations l ON l.location_id = r.location_id
            WHERE r.event_name_raw IS NOT NULL
            GROUP BY 1, 2
        ),
        splits AS (
            SELECT event_name_raw FROM per GROUP BY 1 HAVING count(DISTINCT event_id) > 1
        )
        SELECT count(*) FROM (
            SELECT p.event_name_raw
            FROM per p JOIN splits s ON s.event_name_raw = p.event_name_raw
            GROUP BY p.event_name_raw
            HAVING count(DISTINCT p.city || '|' || coalesce(p.country, '')) = 1
        ) t
        """,
        max_value=0,
        severity="error",
        category="event_naming",
        description="Same raw event name + same geo must not map to multiple event_id.",
        fix_hint="scripts/merge_event_ids.py + MERGE_EVENT_ID_MAP",
    ),
    QualityCheck(
        name="noncanonical_divisions",
        sql="""
        SELECT count(*) FROM core.results
        WHERE division IN ('All-Stars', 'Champions', 'Masters')
        """,
        max_value=0,
        severity="error",
        category="levels",
        description="Legacy plural division labels from old parser/registry.",
        fix_hint="scripts/repair_divisions.py",
    ),
    QualityCheck(
        name="points_history_drift",
        sql="""
        SELECT count(*) FROM history.dancer_points_history h
        WHERE h.valid_to IS NULL AND NOT EXISTS (
            SELECT 1 FROM core.dancer_points p
            WHERE p.dancer_id = h.dancer_id AND p.role = h.role
              AND p.dance = h.dance AND p.level = h.level
              AND p.total_points = h.total_points
        )
        """,
        max_value=0,
        severity="error",
        category="history",
        description="SCD2 open row must match core.dancer_points snapshot.",
        fix_hint="scripts/reconcile_points_history.py",
    ),
)

# Extended checks — regressions from knowledge/repair layer.
EXTENDED_CHECKS: tuple[QualityCheck, ...] = (
    QualityCheck(
        name="orphan_location_id",
        sql="""
        SELECT count(*) FROM core.results r
        LEFT JOIN core.locations l ON l.location_id = r.location_id
        WHERE l.location_id IS NULL
        """,
        max_value=0,
        severity="error",
        category="location",
        description="results.location_id must exist in core.locations.",
        fix_hint="transform/geography/resolve.py + repair_results_location.py",
    ),
    QualityCheck(
        name="orphan_event_id",
        sql="""
        SELECT count(*) FROM core.results r
        LEFT JOIN core.events e ON e.event_id = r.event_id
        WHERE e.event_id IS NULL
        """,
        max_value=0,
        severity="error",
        category="event_naming",
        description="Every result event_id must exist in core.events.",
        fix_hint="db/seed_event_aliases.py seed_result_only_events",
    ),
    QualityCheck(
        name="editions_null_location_id",
        sql="SELECT count(*) FROM core.event_editions WHERE location_id IS NULL",
        max_value=0,
        severity="error",
        category="location",
        description="Event editions derive location from results mode location_id.",
        fix_hint="scripts/repair_locations.py + rebuild_event_catalog",
    ),
    QualityCheck(
        name="all_caps_cities",
        sql="""
        SELECT count(*) FROM core.locations
        WHERE event_city = upper(event_city)
          AND event_city ~ '[A-Z]'
          AND length(trim(event_city)) > 2
        """,
        max_value=0,
        severity="error",
        category="location",
        description="ALL CAPS city names (CHICAGO, TOULOUSE, WILMINGTON DEL).",
        fix_hint="transform/geography/city.py + scripts/repair_locations.py",
    ),
    QualityCheck(
        name="location_id_multiple_strings",
        sql="""
        SELECT count(*) FROM (
            SELECT location_id FROM core.locations
            GROUP BY location_id HAVING count(DISTINCT event_location) > 1
        ) t
        """,
        max_value=0,
        severity="error",
        category="location",
        description="One location_id must not have conflicting event_location strings.",
        fix_hint="Consolidate in location_info + core.locations",
    ),
    QualityCheck(
        name="city_equals_country",
        sql="""
        SELECT count(*) FROM core.locations
        WHERE trim(event_city) = trim(event_country)
          AND trim(event_city) <> ''
          AND location_id NOT IN (159, 244)
        """,
        max_value=0,
        severity="warn",
        category="location",
        description="city=country usually geocode bug; Singapore ids 159/244 whitelisted.",
        fix_hint="LOCATION_ID_CORRECTIONS or city-state allowlist in quality_audit",
    ),
    QualityCheck(
        name="double_space_event_location",
        sql="""
        SELECT count(*) FROM core.locations
        WHERE event_location LIKE '%  %'
        """,
        max_value=0,
        severity="warn",
        category="location",
        description="Double spaces in location strings (Moscow,  Russia).",
        fix_hint="normalize whitespace in city.py / repair_locations",
    ),
    QualityCheck(
        name="catalog_duplicate_city_token",
        sql="""
        SELECT count(*) FROM core.event_catalog
        WHERE typical_location ~ ', ([^,]+), \\1,'
           OR typical_location ~ ', ([^,]+), \\1$'
        """,
        max_value=0,
        severity="warn",
        category="location",
        description="Duplicated city in typical_location (Madrid, Madrid, Spain).",
        fix_hint="Fix schedule enrich or sync from event_editions",
    ),
    QualityCheck(
        name="phantom_ids_not_merged",
        sql="""
        SELECT count(*) FROM core.event_catalog
        WHERE event_id IN (443, 444, 467, 486, 487, 488)
          AND coalesce(registry_status, '') NOT IN ('merged', 'inactive')
        """,
        max_value=0,
        severity="error",
        category="event_naming",
        description="Phantom registry ids must be merged/inactive (Swing&Snow, Grand Nationals).",
        fix_hint="db/catalog_registry.py PHANTOM_ALIAS_TO_CANONICAL",
    ),
    QualityCheck(
        name="swing_snow_alias",
        sql="""
        SELECT CASE WHEN EXISTS (
            SELECT 1 FROM core.event_aliases
            WHERE alias = 'Swing&Snow' AND event_id = 215
        ) THEN 0 ELSE 1 END
        """,
        max_value=0,
        severity="error",
        category="event_naming",
        description="Swing&Snow spelling variant must alias to canonical event_id 215.",
        fix_hint="core.event_aliases + EVENT_NAME_VARIANT_TO_CATALOG",
    ),
    QualityCheck(
        name="catalog_with_editions_missing_typical_location",
        sql="""
        SELECT count(*) FROM core.event_catalog
        WHERE edition_count > 0
          AND (typical_location IS NULL OR trim(typical_location) = '')
        """,
        max_value=0,
        severity="error",
        category="location",
        description="Events with results must have typical_location in catalog.",
        fix_hint="rebuild_event_catalog + enrich_known_events",
    ),
)

ALL_CHECKS: tuple[QualityCheck, ...] = CORE_CHECKS + EXTENDED_CHECKS


def run_quality_checks(
    checks: tuple[QualityCheck, ...] = ALL_CHECKS,
) -> dict:
    """Execute checks against Supabase; return structured report."""
    from connection import connect

    results: list[dict] = []
    with connect() as conn:
        with conn.cursor() as cur:
            for check in checks:
                cur.execute(check.sql)
                value = int(cur.fetchone()[0])
                ok = value <= check.max_value
                results.append(
                    {
                        "name": check.name,
                        "category": check.category,
                        "severity": check.severity,
                        "value": value,
                        "max_value": check.max_value,
                        "ok": ok,
                        "description": check.description,
                        "fix_hint": check.fix_hint,
                    }
                )

    errors = [r for r in results if not r["ok"] and r["severity"] == "error"]
    warns = [r for r in results if not r["ok"] and r["severity"] == "warn"]
    return {
        "checks": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["ok"]),
            "errors": len(errors),
            "warnings": len(warns),
        },
    }


def report_needs_attention(report: dict) -> bool:
    summary = report.get("summary") or {}
    return int(summary.get("errors", 0)) > 0 or int(summary.get("warnings", 0)) > 0
