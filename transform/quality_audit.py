"""Data quality audit — detect naming/location defects for manual review.

Findings are logged, not auto-fixed. Mirrors notebook normalization pain points:
event name variants, year suffixes, location inconsistencies, orphan refs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from transform.geography.geo_event import (
    build_location_lookup,
    classify_event_id_pair,
    geo_key,
    resolve_result_geo,
)
from transform.knowledge import (
    EVENT_NAME_NORMALIZATION,
)
from transform.knowledge.locations import CITY_STATE_COUNTRIES
from transform.data_preprocessing import (
    validate_data_quality,
    validate_relationships,
)
from transform.normalize import CANONICAL_LEVELS, normalize_level

YEAR_SUFFIX_RE = re.compile(r"\s+(19|20)\d{2}\s*$")
YEAR_EMBEDDED_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class QualityFinding:
    category: str
    code: str
    severity: str
    message: str
    count: int = 0
    examples: list[dict[str, Any]] = field(default_factory=list)
    suggested_fix: str = ""
    fingerprint: str = ""
    is_new: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fingerprint(category: str, code: str, key: str) -> str:
    raw = f"{category}|{code}|{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def strip_event_year(name: str) -> str:
    return YEAR_SUFFIX_RE.sub("", name.strip())


def load_csv_bundle(data_dir: Path) -> dict[str, pd.DataFrame]:
    files = {
        "location_info": "location_info.csv",
        "events_wsdc": "events_wsdc.csv",
        "dancers_results_info": "dancers_results_info.csv",
        "dancer_role_info": "dancer_role_info.csv",
        "dancers_points_info": "dancers_points_info.csv",
        "scheduled_events": "scheduled_events.csv",
        "event_catalog": "event_catalog.csv",
        "edition_location_baseline": "edition_location_baseline.csv",
    }
    data: dict[str, pd.DataFrame] = {}
    for key, filename in files.items():
        path = data_dir / filename
        if path.exists():
            data[key] = pd.read_csv(path, dtype=str, low_memory=False)
    return data


def check_event_name_year_suffix(results: pd.DataFrame) -> QualityFinding | None:
    if "event_name" not in results.columns:
        return None
    names = results["event_name"].dropna().astype(str).str.strip()
    bad = sorted({n for n in names.unique() if YEAR_SUFFIX_RE.search(n)})
    if not bad:
        return None
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_YEAR_SUFFIX",
        severity="medium",
        message="Event names with trailing year (should be normalized to base name + event_year column)",
        count=len(bad),
        examples=[{"event_name": n} for n in bad[:15]],
        suggested_fix="Add mapping to EVENT_NAME_NORMALIZATION in transform/data_preprocessing.py",
        fingerprint=_fingerprint("event_naming", "EVENT_NAME_YEAR_SUFFIX", "|".join(bad[:5])),
    )


def check_event_name_variants_by_geo(
    results: pd.DataFrame,
    location_info: pd.DataFrame | None,
) -> list[QualityFinding]:
    """Split EVENT_NAME_VARIANTS by geography — merge candidates vs legit multi-geo names."""
    if "event_name" not in results.columns:
        return []

    lookup = build_location_lookup(location_info)
    enriched = results.copy()
    geo_keys: list[str] = []
    for _, row in enriched.iterrows():
        city, state, country = resolve_result_geo(row.to_dict(), lookup)
        geo_keys.append(geo_key(city, state, country))
    enriched["_geo_key"] = geo_keys

    same_geo_groups: dict[str, set[str]] = {}
    diff_geo_names: list[str] = []

    name_groups: dict[str, list[str]] = {}
    for name in enriched["event_name"].dropna().astype(str).str.strip().unique():
        base = strip_event_year(name).lower()
        name_groups.setdefault(base, set()).add(name)

    for base, variants in name_groups.items():
        if len(variants) <= 1:
            continue
        subset = enriched[enriched["event_name"].astype(str).str.strip().isin(variants)]
        distinct_geo = set(subset["_geo_key"].dropna().astype(str).unique()) - {""}
        if len(distinct_geo) > 1:
            diff_geo_names.append(base)
        else:
            same_geo_groups[base] = variants

    findings: list[QualityFinding] = []
    if same_geo_groups:
        examples = []
        for k, v in list(same_geo_groups.items())[:12]:
            subset = enriched[enriched["event_name"].astype(str).str.strip().isin(v)]
            gks = sorted(set(subset["_geo_key"].dropna().astype(str).unique()) - {""})
            examples.append({"base_key": k, "variants": sorted(v)[:8], "geo_keys": gks[:3]})
        findings.append(
            QualityFinding(
                category="event_naming",
                code="EVENT_NAME_VARIANTS_SAME_GEO",
                severity="high",
                message="Same event name variants share one geography (merge candidate)",
                count=len(same_geo_groups),
                examples=examples,
                suggested_fix="Unify via MERGE_EVENT_ID_MAP / EVENT_NAME_NORMALIZATION",
                fingerprint=_fingerprint(
                    "event_naming",
                    "EVENT_NAME_VARIANTS_SAME_GEO",
                    "|".join(sorted(same_geo_groups.keys())[:8]),
                ),
            )
        )
    if diff_geo_names:
        findings.append(
            QualityFinding(
                category="event_naming",
                code="EVENT_NAME_VARIANTS_DIFF_GEO",
                severity="info",
                message="Same base event name appears in multiple geographies (not a duplicate)",
                count=len(diff_geo_names),
                examples=[{"base_key": k} for k in diff_geo_names[:12]],
                suggested_fix="Keep separate geo-events; do not merge event_id across cities",
                fingerprint=_fingerprint(
                    "event_naming",
                    "EVENT_NAME_VARIANTS_DIFF_GEO",
                    "|".join(sorted(diff_geo_names)[:8]),
                ),
            )
        )
    return findings


def check_event_name_variants(results: pd.DataFrame) -> QualityFinding | None:
    if "event_name" not in results.columns:
        return None
    groups: dict[str, set[str]] = {}
    for name in results["event_name"].dropna().astype(str).str.strip().unique():
        key = strip_event_year(name).lower()
        groups.setdefault(key, set()).add(name)
    variants = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    if not variants:
        return None
    examples = [
        {"base_key": k, "variants": v[:8]}
        for k, v in list(variants.items())[:12]
    ]
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_VARIANTS",
        severity="high",
        message="Same event appears under multiple name spellings (possible duplicate event identity)",
        count=len(variants),
        examples=examples,
        suggested_fix="Unify via EVENT_NAME_NORMALIZATION or core.event_aliases",
        fingerprint=_fingerprint(
            "event_naming",
            "EVENT_NAME_VARIANTS",
            "|".join(sorted(variants.keys())[:8]),
        ),
    )


def check_event_name_unmapped(results: pd.DataFrame) -> QualityFinding | None:
    if "event_name" not in results.columns:
        return None
    canonical = set(EVENT_NAME_NORMALIZATION.values())
    keys = set(EVENT_NAME_NORMALIZATION.keys())
    known = canonical | keys

    suspicious: list[dict[str, str]] = []
    for name in sorted(results["event_name"].dropna().astype(str).str.strip().unique()):
        if name in known:
            continue
        base = strip_event_year(name)
        for ref in canonical:
            if _similar(base, ref) >= 0.88 and base != ref:
                suspicious.append({"event_name": name, "similar_to": ref, "score": round(_similar(base, ref), 3)})
                break

    if not suspicious:
        return None
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_SIMILAR_UNMAPPED",
        severity="medium",
        message="Event names similar to known canonical names but not in EVENT_NAME_NORMALIZATION",
        count=len(suspicious),
        examples=suspicious[:20],
        suggested_fix="Add explicit mapping to EVENT_NAME_NORMALIZATION",
        fingerprint=_fingerprint(
            "event_naming",
            "EVENT_NAME_SIMILAR_UNMAPPED",
            "|".join(x["event_name"] for x in suspicious[:10]),
        ),
    )


def check_event_names_unresolved_to_catalog(
    results: pd.DataFrame,
    events: pd.DataFrame | None,
) -> QualityFinding | None:
    """Result names that still won't join core.events after EVENT_NAME_NORMALIZATION."""
    if results is None or "event_name" not in results.columns:
        return None
    if events is None or "name" not in events.columns:
        return None

    normalized = results.copy()
    normalized["event_name"] = normalized["event_name"].replace(EVENT_NAME_NORMALIZATION)
    result_names = set(normalized["event_name"].dropna().astype(str).str.strip().unique())
    catalog = set(events["name"].dropna().astype(str).str.strip().unique())
    unresolved = sorted(result_names - catalog)
    if not unresolved:
        return None
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_UNRESOLVED_TO_CATALOG",
        severity="high",
        message="Result event names still absent from events_wsdc after normalization (will orphan in load)",
        count=len(unresolved),
        examples=[{"event_name": n} for n in unresolved[:25]],
        suggested_fix="Add to RESULT_TO_CATALOG_EVENT_NAME in transform/knowledge/event_aliases.py",
        fingerprint=_fingerprint(
            "event_naming",
            "EVENT_NAME_UNRESOLVED_TO_CATALOG",
            "|".join(unresolved[:10]),
        ),
    )


def check_event_name_not_in_catalog(
    results: pd.DataFrame,
    events: pd.DataFrame | None,
) -> QualityFinding | None:
    if results is None or "event_name" not in results.columns:
        return None
    result_names = set(results["event_name"].dropna().astype(str).str.strip().unique())
    if events is None or "name" not in events.columns:
        orphan = sorted(result_names)
    else:
        catalog = set(events["name"].dropna().astype(str).str.strip().unique())
        orphan = sorted(result_names - catalog)
    if not orphan:
        return None
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_NOT_IN_CATALOG",
        severity="low",
        message="Result event_name values absent from events_wsdc.csv (may be OK if resolved by name in load)",
        count=len(orphan),
        examples=[{"event_name": n} for n in orphan[:20]],
        suggested_fix="Verify events_wsdc export or add event instance after parse",
        fingerprint=_fingerprint(
            "event_naming",
            "EVENT_NAME_NOT_IN_CATALOG",
            "|".join(orphan[:10]),
        ),
    )


def check_location_format(location_info: pd.DataFrame) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    if location_info is None or location_info.empty:
        return findings

    if "event_location" in location_info.columns:
        locs = location_info["event_location"].fillna("").astype(str).str.strip()
        no_comma = location_info[locs.ne("") & ~locs.str.contains(",", regex=False)]
        if not no_comma.empty:
            examples = no_comma[["location_id", "event_location"]].head(15).to_dict("records")
            findings.append(
                QualityFinding(
                    category="location",
                    code="LOCATION_INCOMPLETE_FORMAT",
                    severity="medium",
                    message="Locations without comma (City, State/Country format expected)",
                    count=len(no_comma),
                    examples=examples,
                    suggested_fix="Add to EVENT_LOCATION_EXACT_CORRECTIONS or LOCATION_INFO_*_CORRECTIONS",
                    fingerprint=_fingerprint("location", "LOCATION_INCOMPLETE_FORMAT", str(len(no_comma))),
                )
            )

    if {"event_city", "event_country"}.issubset(location_info.columns):
        city = location_info["event_city"].fillna("").astype(str).str.strip()
        country = location_info["event_country"].fillna("").astype(str).str.strip()
        bad = location_info[(city != "") & (city == country)]
        # City-states (Singapore): city == country is correct; state stays empty (US-only).
        if not bad.empty:
            bad = bad[
                ~bad["event_country"]
                .fillna("")
                .astype(str)
                .str.strip()
                .isin(CITY_STATE_COUNTRIES)
            ]
        if not bad.empty:
            findings.append(
                QualityFinding(
                    category="location",
                    code="LOCATION_CITY_EQUALS_COUNTRY",
                    severity="high",
                    message="event_city equals event_country (likely parse/geocode defect)",
                    count=len(bad),
                    examples=bad[["location_id", "event_city", "event_country", "event_location"]]
                    .head(15)
                    .to_dict("records"),
                    suggested_fix="Fix in LOCATION_INFO_ID_CORRECTIONS or re-geocode",
                    fingerprint=_fingerprint("location", "LOCATION_CITY_EQUALS_COUNTRY", str(len(bad))),
                )
            )

    if "location_id" in location_info.columns and "event_location" in location_info.columns:
        dup = (
            location_info.groupby("location_id")["event_location"]
            .nunique()
            .reset_index(name="n")
        )
        dup = dup[dup["n"] > 1]
        if not dup.empty:
            examples = []
            for lid in dup["location_id"].head(10):
                rows = location_info[location_info["location_id"] == lid]["event_location"].unique()[:5]
                examples.append({"location_id": lid, "event_locations": list(rows)})
            findings.append(
                QualityFinding(
                    category="location",
                    code="LOCATION_ID_MULTIPLE_STRINGS",
                    severity="high",
                    message="Same location_id maps to multiple event_location strings in location_info",
                    count=len(dup),
                    examples=examples,
                    suggested_fix="Consolidate location_info rows for each location_id",
                    fingerprint=_fingerprint("location", "LOCATION_ID_MULTIPLE_STRINGS", str(len(dup))),
                )
            )

    return findings


def check_event_name_location_country_conflicts(
    results: pd.DataFrame,
    location_info: pd.DataFrame | None,
) -> QualityFinding | None:
    """Flag results where event_name implies a country different from location_id."""
    from transform.geography.event_location_guard import find_name_location_country_conflicts

    if results is None or results.empty or location_info is None:
        return None
    conflicts = find_name_location_country_conflicts(results, location_info)
    if not conflicts:
        return None
    examples = [
        {
            "event_name": c.event_name,
            "location_id": c.location_id,
            "location_country": c.location_country,
            "name_hints": list(c.name_hints),
            "rows": c.row_count,
        }
        for c in conflicts[:20]
    ]
    return QualityFinding(
        category="location",
        code="EVENT_NAME_LOCATION_COUNTRY_CONFLICT",
        severity="high",
        message=(
            "Event name implies a different country than results.location_id "
            "(often a shared/wrong location_id collision)"
        ),
        count=sum(c.row_count for c in conflicts),
        examples=examples,
        suggested_fix=(
            "Add EVENT_NAME_LOCATION_OVERRIDES + force_result_locations_from_event_name_overrides; "
            "see scripts/audit_event_location_mismatches.py"
        ),
        fingerprint=_fingerprint(
            "location",
            "EVENT_NAME_LOCATION_COUNTRY_CONFLICT",
            "|".join(f"{c.event_name}:{c.location_id}" for c in conflicts[:15]),
        ),
    )


def check_scheduled_vs_results_country(
    results: pd.DataFrame,
    location_info: pd.DataFrame | None,
    scheduled: pd.DataFrame | None,
) -> QualityFinding | None:
    """Calendar says one country, results location another → shared wrong location_id."""
    from transform.geography.event_location_guard import find_scheduled_country_conflicts

    if results is None or results.empty or scheduled is None or location_info is None:
        return None
    conflicts = find_scheduled_country_conflicts(results, location_info, scheduled)
    if not conflicts:
        return None
    examples = [
        {
            "event_name": c.event_name,
            "location_id": c.location_id,
            "results_country": c.results_country,
            "scheduled_country": c.scheduled_country,
            "scheduled_location": c.scheduled_location,
            "rows": c.row_count,
        }
        for c in conflicts[:20]
    ]
    return QualityFinding(
        category="location",
        code="SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT",
        severity="high",
        message=(
            "WSDC calendar country differs from results location country "
            "(shared/wrong location_id — Sea Dance / Med in Swing pattern)"
        ),
        count=sum(c.row_count for c in conflicts),
        examples=examples,
        suggested_fix=(
            "Verify venue, then add EVENT_NAME_LOCATION_OVERRIDES (or KNOWN_SERIES_MOVES "
            "if the event really moved); scripts/audit_event_location_mismatches.py"
        ),
        fingerprint=_fingerprint(
            "location",
            "SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT",
            "|".join(f"{c.event_name}:{c.location_id}" for c in conflicts[:15]),
        ),
    )


def check_event_id_canonical_location_mismatch(
    results: pd.DataFrame,
    location_info: pd.DataFrame | None,
    catalog: pd.DataFrame | None,
    editions: pd.DataFrame | None = None,
) -> QualityFinding | None:
    """Curated event_id location ≠ results/editions mode location country."""
    from transform.geography.event_location_guard import (
        find_event_id_canonical_location_mismatches,
    )

    if results is None or results.empty or location_info is None:
        return None
    conflicts = find_event_id_canonical_location_mismatches(
        results, location_info, catalog, editions
    )
    if not conflicts:
        return None
    examples = [
        {
            "event_id": c.event_id,
            "event_name": c.event_name,
            "canonical_source": c.canonical_source,
            "canonical_location": c.canonical_location,
            "canonical_country": c.canonical_country,
            "results_location_id": c.results_location_id,
            "results_country": c.results_country,
            "results_rows": c.results_rows,
            "editions_location_id": c.editions_location_id,
            "editions_country": c.editions_country,
            "mismatch_side": c.mismatch_side,
        }
        for c in conflicts[:20]
    ]
    return QualityFinding(
        category="location",
        code="EVENT_ID_CANONICAL_LOCATION_MISMATCH",
        severity="high",
        message=(
            "Results/editions location country differs from curated event_id "
            "canonical location (KNOWN / name override / upcoming)"
        ),
        count=sum(max(c.results_rows, 1) for c in conflicts),
        examples=examples,
        suggested_fix=(
            "Confirm venue, then add/update KNOWN_EVENT_METADATA[event_id] or "
            "EVENT_NAME_LOCATION_OVERRIDES + force_result_locations; "
            "see scripts/audit_event_location_mismatches.py section D"
        ),
        fingerprint=_fingerprint(
            "location",
            "EVENT_ID_CANONICAL_LOCATION_MISMATCH",
            "|".join(f"{c.event_id}:{c.results_location_id}" for c in conflicts[:15]),
        ),
    )


def check_edition_location_baseline_drift(
    results: pd.DataFrame,
    baseline: pd.DataFrame | None,
) -> QualityFinding | None:
    """Results mode location_id differs from frozen edition baseline CSV."""
    from transform.geography.edition_location_baseline import find_csv_baseline_drifts

    if baseline is None or baseline.empty:
        return None
    drifts = find_csv_baseline_drifts(results, baseline)
    if not drifts:
        return None
    examples = [
        {
            "event_id": d.event_id,
            "event_year": d.event_year,
            "event_month": d.event_month,
            "event_name": d.event_name,
            "baseline_location_id": d.baseline_location_id,
            "current_location_id": d.current_location_id,
            "result_rows": d.result_rows,
        }
        for d in drifts[:20]
    ]
    return QualityFinding(
        category="location",
        code="EDITION_LOCATION_BASELINE_DRIFT",
        severity="high",
        message=(
            "Results location_id for a known edition key differs from "
            "edition_location_baseline.csv (cross-load drift)"
        ),
        count=len(drifts),
        examples=examples,
        suggested_fix=(
            "Investigate shared wrong location_id; fix overrides/repair_locations. "
            "If venue change is legitimate, UPDATE core.edition_location_baseline in Supabase."
        ),
        fingerprint=_fingerprint(
            "location",
            "EDITION_LOCATION_BASELINE_DRIFT",
            "|".join(
                f"{d.event_id}:{d.event_year}-{d.event_month}:{d.current_location_id}"
                for d in drifts[:15]
            ),
        ),
    )


def check_baseline_vs_location_overrides(
    baseline: pd.DataFrame | None,
    location_info: pd.DataFrame | None,
) -> QualityFinding | None:
    """Baseline location_id disagrees with EVENT_NAME_LOCATION_OVERRIDES (poison seed)."""
    from transform.geography.edition_location_baseline import (
        find_baseline_override_conflicts,
    )

    if baseline is None or baseline.empty or location_info is None or location_info.empty:
        return None
    conflicts = find_baseline_override_conflicts(baseline, location_info)
    if not conflicts:
        return None
    examples = [
        {
            "event_id": c.event_id,
            "event_year": c.event_year,
            "event_month": c.event_month,
            "event_name": c.event_name,
            "baseline_location_id": c.baseline_location_id,
            "override_location_id": c.override_location_id,
            "override_location": c.override_location,
        }
        for c in conflicts[:20]
    ]
    return QualityFinding(
        category="location",
        code="BASELINE_VS_LOCATION_OVERRIDE",
        severity="high",
        message=(
            "edition_location_baseline location_id disagrees with "
            "EVENT_NAME_LOCATION_OVERRIDES (seed/auto-add froze a shared wrong lid)"
        ),
        count=len(conflicts),
        examples=examples,
        suggested_fix=(
            "Apply overrides + repair results/editions, then UPDATE "
            "core.edition_location_baseline to the override location_id "
            "(source='manual'). Cross-load drift alone cannot see poison seeds."
        ),
        fingerprint=_fingerprint(
            "location",
            "BASELINE_VS_LOCATION_OVERRIDE",
            "|".join(
                f"{c.event_id}:{c.baseline_location_id}->{c.override_location_id}"
                for c in conflicts[:15]
            ),
        ),
    )


def check_catalog_typical_vs_upcoming(
    catalog: pd.DataFrame | None,
) -> QualityFinding | None:
    """Catalog typical country ≠ upcoming country (stuck typical or series move)."""
    from transform.geography.event_location_guard import (
        find_catalog_typical_upcoming_conflicts,
    )

    if catalog is None or catalog.empty:
        return None
    conflicts = find_catalog_typical_upcoming_conflicts(catalog)
    if not conflicts:
        return None
    examples = [
        {
            "canonical_name": c.canonical_name,
            "typical_location": c.typical_location,
            "upcoming_location": c.upcoming_location,
        }
        for c in conflicts[:20]
    ]
    return QualityFinding(
        category="location",
        code="CATALOG_TYPICAL_UPCOMING_CONFLICT",
        severity="medium",
        message=(
            "event_catalog typical_location country differs from upcoming_location "
            "(stuck wrong typical OR real series move — research before remap)"
        ),
        count=len(conflicts),
        examples=examples,
        suggested_fix=(
            "If venue is stuck: EVENT_NAME_LOCATION_OVERRIDES + apply script. "
            "If the series moved: add to KNOWN_SERIES_MOVES in event_location_guard.py"
        ),
        fingerprint=_fingerprint(
            "location",
            "CATALOG_TYPICAL_UPCOMING_CONFLICT",
            "|".join(c.canonical_name for c in conflicts[:15]),
        ),
    )


def check_event_name_location_id_collision(
    results: pd.DataFrame,
    location_info: pd.DataFrame | None,
) -> QualityFinding | None:
    """Detect event names whose results span more than one location_id.

    This is the root cause of "Slovenian Open in Australia" style bugs: WSDC
    reuses or misassigns a location_id and the pipeline silently inherits it.
    Every canonical event_name should map to exactly one location_id (or zero
    if location is missing). More than one signals a collision or series move.
    """
    if results is None or results.empty:
        return None
    if "event_name" not in results.columns or "location_id" not in results.columns:
        return None

    loc_col = results["location_id"].astype(str).str.strip()
    name_col = results["event_name"].astype(str).str.strip()

    # Build country lookup to enrich examples
    loc_country: dict[str, str] = {}
    if location_info is not None and not location_info.empty:
        for _, row in location_info.iterrows():
            lid = str(row.get("location_id", "")).strip()
            country = str(row.get("event_country", "")).strip()
            if lid and country:
                loc_country[lid] = country

    examples = []
    for name, grp in results.groupby(name_col):
        ids = {
            v
            for v in grp["location_id"].astype(str).str.strip()
            if v and v not in {"", "nan"}
        }
        if len(ids) <= 1:
            continue
        id_list = sorted(ids, key=lambda x: int(x) if x.isdigit() else 0)
        countries = [loc_country.get(i, "?") for i in id_list]
        examples.append(
            {
                "event_name": name,
                "location_ids": id_list,
                "countries": countries,
                "row_count": len(grp),
            }
        )

    if not examples:
        return None

    examples.sort(key=lambda x: x["row_count"], reverse=True)
    return QualityFinding(
        category="location",
        code="EVENT_NAME_LOCATION_ID_COLLISION",
        severity="high",
        message=(
            f"{len(examples)} event name(s) map to multiple location_ids "
            "(shared or misassigned id — likely wrong country in some rows)"
        ),
        count=len(examples),
        examples=examples[:20],
        suggested_fix=(
            "Add to EVENT_NAME_LOCATION_OVERRIDES in transform/knowledge/events.py "
            "and run force_result_locations_from_event_name_overrides"
        ),
        fingerprint=_fingerprint(
            "location",
            "EVENT_NAME_LOCATION_ID_COLLISION",
            "|".join(e["event_name"] for e in examples[:15]),
        ),
    )


def check_non_canonical_levels(results: pd.DataFrame) -> QualityFinding | None:
    if "event_competition" not in results.columns:
        return None
    levels = results["event_competition"].dropna().astype(str).str.strip().unique()
    bad = []
    for level in levels:
        normalized = normalize_level(level)
        if normalized not in CANONICAL_LEVELS and level not in CANONICAL_LEVELS:
            bad.append({"raw_level": level, "normalized_attempt": normalized})
    if not bad:
        return None
    return QualityFinding(
        category="levels",
        code="NON_CANONICAL_DIVISION",
        severity="low",
        message="Division/level values outside canonical set (Tableau expects full words)",
        count=len(bad),
        examples=bad[:20],
        suggested_fix="Add alias to LEVEL_ALIASES in transform/normalize.py",
        fingerprint=_fingerprint("levels", "NON_CANONICAL_DIVISION", "|".join(x["raw_level"] for x in bad[:10])),
    )


def check_new_event_names(
    results: pd.DataFrame,
    previous_names: set[str] | None,
) -> QualityFinding | None:
    if not previous_names or "event_name" not in results.columns:
        return None
    current = set(results["event_name"].dropna().astype(str).str.strip().unique())
    new_names = sorted(current - previous_names)
    if not new_names:
        return None
    return QualityFinding(
        category="event_naming",
        code="EVENT_NAME_NEW_SINCE_LAST_RUN",
        severity="info",
        message="New event names appeared since last quality report (review naming)",
        count=len(new_names),
        examples=[{"event_name": n} for n in new_names[:25]],
        suggested_fix="Check if variant of existing event; add normalization rule if needed",
        fingerprint=_fingerprint(
            "event_naming",
            "EVENT_NAME_NEW_SINCE_LAST_RUN",
            "|".join(new_names[:15]),
        ),
    )


def check_trial_schedule_geo_gaps(
    scheduled: pd.DataFrame | None,
    location_info: pd.DataFrame | None,
) -> QualityFinding | None:
    """Trial Event rows on the list without usable location_id / coordinates."""
    if scheduled is None or scheduled.empty:
        return None
    if "status_event" not in scheduled.columns:
        return None

    status = scheduled["status_event"].astype(str).str.lower()
    trials = scheduled[status.str.contains("trial", na=False)].copy()
    if trials.empty:
        return None

    loc_coords: dict[str, bool] = {}
    if location_info is not None and not location_info.empty:
        for _, row in location_info.iterrows():
            lid = str(row.get("location_id") or "").strip()
            if not lid:
                continue
            try:
                lat = str(row.get("latitude") or "").strip()
                lon = str(row.get("longitude") or "").strip()
                loc_coords[lid] = bool(lat and lon and lat.lower() != "nan" and lon.lower() != "nan")
            except Exception:  # noqa: BLE001
                loc_coords[lid] = False

    examples: list[dict] = []
    for _, row in trials.iterrows():
        name = str(row.get("event_name") or "").strip()
        lid = str(row.get("location_id") or "").strip()
        if lid.lower() in {"", "nan", "none"}:
            examples.append(
                {
                    "event_name": name,
                    "start_date": str(row.get("start_date") or ""),
                    "location_raw": str(row.get("location_raw") or ""),
                    "reason": "missing_location_id",
                }
            )
            continue
        if not loc_coords.get(lid, False):
            examples.append(
                {
                    "event_name": name,
                    "start_date": str(row.get("start_date") or ""),
                    "location_raw": str(row.get("location_raw") or ""),
                    "location_id": lid,
                    "reason": "missing_coordinates",
                }
            )

    if not examples:
        return None

    examples.sort(key=lambda x: x.get("event_name") or "")
    return QualityFinding(
        category="location",
        code="TRIAL_SCHEDULE_GEO_GAP",
        severity="medium",
        message=(
            f"{len(examples)} Trial Event(s) on the WSDC list lack location_id "
            "or coordinates (list geo ensure_location / Google geocode)"
        ),
        count=len(examples),
        examples=examples[:20],
        suggested_fix=(
            "Re-run sync_events_list with GOOGLE_MAPS_API_KEY; or add city to "
            "location_info / CITY_CANONICAL_COORDINATES"
        ),
        fingerprint=_fingerprint(
            "location",
            "TRIAL_SCHEDULE_GEO_GAP",
            "|".join(e["event_name"] for e in examples[:15]),
        ),
    )


def _legacy_issues_to_findings(issues: list[dict]) -> list[QualityFinding]:
    out: list[QualityFinding] = []
    for issue in issues:
        code = f"LEGACY_{issue.get('field', 'unknown').upper()}"
        out.append(
            QualityFinding(
                category=issue.get("table", "general"),
                code=code,
                severity=str(issue.get("severity", "MEDIUM")).lower(),
                message=str(issue.get("issue", "")),
                count=1,
                examples=[{"detail": issue.get("examples", issue)}],
                suggested_fix="See transform/data_preprocessing.py validate_* functions",
                fingerprint=_fingerprint(code, issue.get("table", ""), str(issue.get("issue", ""))),
            )
        )
    return out


def run_audit(
    data: dict[str, pd.DataFrame],
    *,
    previous_event_names: set[str] | None = None,
) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    results = data.get("dancers_results_info")
    events = data.get("events_wsdc")
    location_info = data.get("location_info")

    if results is not None:
        for fn in (
            check_event_name_year_suffix,
            check_event_name_unmapped,
        ):
            item = fn(results)
            if item:
                findings.append(item)
        findings.extend(check_event_name_variants_by_geo(results, location_info))
        legacy = check_event_name_variants(results)
        if legacy:
            findings.append(legacy)
        item = check_event_names_unresolved_to_catalog(results, events)
        if item:
            findings.append(item)
        item = check_event_name_not_in_catalog(results, events)
        if item:
            findings.append(item)
        item = check_non_canonical_levels(results)
        if item:
            findings.append(item)
        item = check_new_event_names(results, previous_event_names)
        if item:
            findings.append(item)
        item = check_event_name_location_country_conflicts(results, location_info)
        if item:
            findings.append(item)
        item = check_event_name_location_id_collision(results, location_info)
        if item:
            findings.append(item)
        item = check_scheduled_vs_results_country(
            results, location_info, data.get("scheduled_events")
        )
        if item:
            findings.append(item)
        item = check_event_id_canonical_location_mismatch(
            results,
            location_info,
            data.get("event_catalog"),
            data.get("event_editions"),
        )
        if item:
            findings.append(item)
        item = check_edition_location_baseline_drift(
            results,
            data.get("edition_location_baseline"),
        )
        if item:
            findings.append(item)
        item = check_baseline_vs_location_overrides(
            data.get("edition_location_baseline"),
            location_info,
        )
        if item:
            findings.append(item)

    item = check_catalog_typical_vs_upcoming(data.get("event_catalog"))
    if item:
        findings.append(item)

    item = check_trial_schedule_geo_gaps(data.get("scheduled_events"), location_info)
    if item:
        findings.append(item)

    if location_info is not None:
        findings.extend(check_location_format(location_info))

    findings.extend(_legacy_issues_to_findings(validate_data_quality(data)))
    # validate_data_quality already includes relationships; avoid duplicate call

    return findings


def mark_new_findings(
    findings: list[QualityFinding],
    previous_fingerprints: set[str],
) -> None:
    for f in findings:
        f.is_new = f.fingerprint not in previous_fingerprints


def build_report(
    findings: list[QualityFinding],
    *,
    source: str = "local",
    run_id: int | None = None,
) -> dict[str, Any]:
    new_count = sum(1 for f in findings if f.is_new)
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        by_category[f.category] = by_category.get(f.category, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "run_id": run_id,
        "summary": {
            "total_findings": len(findings),
            "new_findings": new_count,
            "by_severity": by_severity,
            "by_category": by_category,
        },
        "findings": [f.to_dict() for f in findings],
        "event_names_snapshot": [],
    }


def load_previous_report(path: Path) -> tuple[set[str], set[str]]:
    """Return (previous_fingerprints, previous_event_names).

    Supports combined report (manual_review_required) and legacy flat findings.
    """
    if not path.exists():
        return set(), set()
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    manual = (data.get("manual_review_required") or {}).get("findings") or []
    legacy = data.get("findings") or []
    source_findings = manual if manual else legacy
    fps = {f.get("fingerprint", "") for f in source_findings if f.get("fingerprint")}
    names = set(data.get("event_names_snapshot") or [])
    return fps, names


def finalize_report(
    data: dict[str, pd.DataFrame],
    findings: list[QualityFinding],
    *,
    source: str = "local",
    run_id: int | None = None,
) -> dict[str, Any]:
    report = build_report(findings, source=source, run_id=run_id)
    if "dancers_results_info" in data and "event_name" in data["dancers_results_info"].columns:
        report["event_names_snapshot"] = sorted(
            data["dancers_results_info"]["event_name"].dropna().astype(str).str.strip().unique().tolist()
        )
    return report
