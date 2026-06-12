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

from transform.data_preprocessing import (
    EVENT_NAME_NORMALIZATION,
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
        bad = location_info[
            location_info["event_city"].fillna("").astype(str).str.strip()
            == location_info["event_country"].fillna("").astype(str).str.strip()
        ]
        bad = bad[bad["event_city"].fillna("").astype(str).str.strip() != ""]
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
        suggested_fix="Add to LEVEL_NORMALIZATION in transform/data_preprocessing.py or transform/normalize.py",
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
            check_event_name_variants,
            check_event_name_unmapped,
        ):
            item = fn(results)
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
    """Return (previous_fingerprints, previous_event_names)."""
    if not path.exists():
        return set(), set()
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    fps = {f.get("fingerprint", "") for f in data.get("findings", []) if f.get("fingerprint")}
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
