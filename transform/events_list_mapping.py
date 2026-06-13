"""Map WSDC Events List rows to points catalog (core.events)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

from parser.event_name_matcher import EVENT_NAME_MAPPINGS, find_best_match, fuzzy_match_score
from transform.events_list_normalize import normalize_url

AUTO_CONFIRM_SCORE = 0.95
REVIEW_SCORE = 0.75
LOCATION_DRIFT_THRESHOLD = 0.72

_REGION_ALIASES = {
    "polska": "poland",
    "deutschland": "germany",
    "nederland": "netherlands",
    "uk": "united kingdom",
}


def _norm_location(loc: str) -> str:
    if not loc:
        return ""
    s = loc.lower().strip()
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r",+", ",", s)
    s = re.sub(r"\s+", " ", s)
    for old, new in _REGION_ALIASES.items():
        s = re.sub(rf"\b{old}\b", new, s)
    return s


def _primary_city(loc: str) -> str:
    return _norm_location(loc).split(",")[0].strip()


def location_similarity(a: str, b: str) -> float:
    na, nb = _norm_location(a), _norm_location(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    city_a, city_b = _primary_city(a), _primary_city(b)
    if city_a and city_b and city_a == city_b:
        return max(0.92, SequenceMatcher(None, na, nb).ratio())
    return SequenceMatcher(None, na, nb).ratio()


def _names_equivalent(list_name: str, catalog_name: str) -> bool:
    return fuzzy_match_score(list_name, catalog_name) >= 0.95


@dataclass
class CatalogEvent:
    event_id: int
    name: str
    url: str
    url_norm: str
    typical_location: str = ""


@dataclass
class MappingResult:
    source_fingerprint: str
    list_name: str
    start_date: str
    location_raw: str
    list_url: str
    status_event: str
    match_status: str  # confirmed | suggested | new | review
    match_method: str  # url | explicit | exact_name | fuzzy | none
    confidence: float
    canonical_event_id: int | None = None
    canonical_name: str | None = None
    catalog_url: str | None = None
    typical_location: str | None = None
    location_score: float = 0.0
    location_flag: str = ""  # ok | drift | unknown
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_url_index(catalog: list[CatalogEvent]) -> dict[str, CatalogEvent]:
    index: dict[str, CatalogEvent] = {}
    for ev in catalog:
        if ev.url_norm and ev.url_norm not in index:
            index[ev.url_norm] = ev
    return index


def _resolve_by_catalog_name(list_name: str, catalog: list[CatalogEvent]) -> tuple[CatalogEvent | None, str]:
    """Match by explicit alias or exact catalog title before URL/fuzzy."""
    targets: list[str] = []
    if list_name in EVENT_NAME_MAPPINGS:
        targets.append(EVENT_NAME_MAPPINGS[list_name])
    targets.append(list_name)

    seen: set[str] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        for ev in catalog:
            if ev.name == target:
                if list_name in EVENT_NAME_MAPPINGS and EVENT_NAME_MAPPINGS[list_name] == ev.name:
                    return ev, "explicit"
                return ev, "exact_name"
    return None, "none"


def map_scheduled_event(
    row: dict[str, Any],
    catalog: list[CatalogEvent],
    url_index: dict[str, CatalogEvent],
    name_list: list[str],
) -> MappingResult:
    fp = row["source_fingerprint"]
    list_name = row.get("event_name") or ""
    list_url = row.get("url") or ""
    list_url_norm = normalize_url(list_url)
    location_raw = row.get("location_raw") or ""
    status_event = row.get("status_event") or ""

    base = MappingResult(
        source_fingerprint=fp,
        list_name=list_name,
        start_date=row.get("start_date") or "",
        location_raw=location_raw,
        list_url=list_url,
        status_event=status_event,
        match_status="review",
        match_method="none",
        confidence=0.0,
    )

    matched: CatalogEvent | None = None
    method = "none"
    confidence = 0.0

    name_match, name_method = _resolve_by_catalog_name(list_name, catalog)
    if name_match:
        matched = name_match
        method = name_method
        confidence = 1.0
        if list_url_norm and name_match.url_norm and list_url_norm != name_match.url_norm:
            base.notes.append(
                f"List URL {list_url!r} differs from catalog URL {name_match.url!r} — using event name"
            )
    elif list_url_norm and list_url_norm in url_index:
        candidate = url_index[list_url_norm]
        name_score = fuzzy_match_score(list_name, candidate.name)
        if name_score >= 0.5:
            matched = candidate
            method = "url"
            confidence = name_score if name_score >= 0.85 else 0.99
        else:
            base.notes.append(
                f"URL matches {candidate.name!r} but name similarity only {name_score:.2f} — skipped auto-link"
            )

    if not matched and list_name in EVENT_NAME_MAPPINGS:
        base.notes.append(
            f"Alias {list_name!r} → {EVENT_NAME_MAPPINGS[list_name]!r} but target not in catalog yet"
        )

    if not matched:
        best_name, score = find_best_match(list_name, name_list, threshold=REVIEW_SCORE)
        if best_name:
            for ev in catalog:
                if ev.name == best_name:
                    matched = ev
                    method = "fuzzy"
                    confidence = score
                    break
            # Reject fuzzy match when locations clearly disagree (different city/event)
            if matched and matched.typical_location and location_raw:
                loc_score = location_similarity(location_raw, matched.typical_location)
                if loc_score < 0.55:
                    base.notes.append(
                        f"Rejected fuzzy {confidence:.2f} → {matched.name!r}: location score {loc_score:.2f}"
                    )
                    matched = None
                    method = "none"
                    confidence = 0.0

    if not matched:
        base.match_status = "new"
        base.match_method = "none"
        base.notes.append("No catalog match — likely new or renamed brand")
        if status_event == "Trial Event":
            base.notes.append("Trial event on schedule")
        return base

    base.canonical_event_id = matched.event_id
    base.canonical_name = matched.name
    base.catalog_url = matched.url
    base.typical_location = matched.typical_location or None
    base.match_method = method
    base.confidence = confidence

    if confidence >= AUTO_CONFIRM_SCORE or method in ("url", "explicit", "exact_name"):
        base.match_status = "confirmed"
    else:
        base.match_status = "suggested"
        base.notes.append(f"Fuzzy name match {confidence:.2f} — confirm manually")

    if list_name != matched.name:
        base.notes.append(f"Name differs: list={list_name!r} catalog={matched.name!r}")

    if matched.typical_location:
        loc_score = location_similarity(location_raw, matched.typical_location)
        base.location_score = loc_score
        if loc_score >= LOCATION_DRIFT_THRESHOLD:
            base.location_flag = "ok"
        elif method in ("url", "explicit", "exact_name") or _names_equivalent(list_name, matched.name):
            # Site schedule wins for future editions; catalog typical is historical.
            base.location_flag = "site_differs_from_history"
            base.notes.append(
                f"Site location {location_raw!r} differs from catalog typical "
                f"{matched.typical_location!r} (venue may have moved)"
            )
        else:
            base.location_flag = "drift"
            base.notes.append(
                f"Location drift: list={location_raw!r} typical={matched.typical_location!r}"
            )
            if base.match_status == "confirmed":
                base.match_status = "review"
    else:
        base.location_flag = "unknown"
        base.notes.append("No historical location in catalog for comparison")

    return base


def analyze_mapping(
    scheduled: list[dict[str, Any]],
    catalog: list[CatalogEvent],
    *,
    active_only: bool = True,
) -> dict[str, Any]:
    rows = [r for r in scheduled if r.get("is_active")] if active_only else scheduled
    url_index = build_url_index(catalog)
    name_list = sorted({ev.name for ev in catalog})

    results = [map_scheduled_event(r, catalog, url_index, name_list) for r in rows]

    by_status: dict[str, list[dict]] = {
        "confirmed": [],
        "suggested": [],
        "review": [],
        "new": [],
    }
    location_drifts: list[dict] = []
    name_variants: list[dict] = []

    for r in results:
        d = r.to_dict()
        by_status[r.match_status].append(d)
        if r.location_flag in ("drift", "site_differs_from_history"):
            location_drifts.append(d)
        if r.canonical_name and r.list_name != r.canonical_name:
            name_variants.append(d)

    return {
        "summary": {
            "scheduled_active": len(rows),
            "confirmed": len(by_status["confirmed"]),
            "suggested": len(by_status["suggested"]),
            "review": len(by_status["review"]),
            "new_unmapped": len(by_status["new"]),
            "location_drifts": len(location_drifts),
            "name_variants": len(name_variants),
        },
        "confirmed": by_status["confirmed"],
        "suggested": by_status["suggested"],
        "manual_review_required": by_status["review"] + by_status["suggested"],
        "new_events": by_status["new"],
        "location_drifts": location_drifts,
        "name_variants": name_variants,
    }
