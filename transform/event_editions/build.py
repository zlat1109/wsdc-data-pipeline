"""Build edition_attributes / edition_status_history row sets from Todd parquet."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from transform.event_editions.gate import STATUS_HISTORY, FUTURE_SCHEDULED, reconcile
from transform.event_editions.keys import parse_todd_edition_id
from transform.event_editions.match import build_core_key_set, match_edition


def _clean(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s.lower() in {"", "nan", "none", "null"}:
        return None
    return s


def _bool(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"t", "true", "1", "yes"}:
        return True
    if s in {"f", "false", "0", "no"}:
        return False
    return None


def _date(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    # pandas NaT / NaT string from CSV round-trips
    if v is pd.NaT:
        return None
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()[:10]
        except (ValueError, OverflowError):
            return None
    s = str(v).strip()
    if not s or s.lower() in {"nat", "nan", "none", "null"}:
        return None
    return s[:10]


def _jsonb(v: Any) -> str | None:
    s = _clean(v)
    if s is None:
        return None
    # row_info is already JSON text in the parquet
    try:
        json.loads(s)
        return s
    except (TypeError, ValueError, json.JSONDecodeError):
        return json.dumps({"raw": s})


@dataclass
class EeTables:
    attributes: list[dict[str, Any]] = field(default_factory=list)
    status_history: list[dict[str, Any]] = field(default_factory=list)
    metros: list[dict[str, Any]] = field(default_factory=list)
    venues: list[dict[str, Any]] = field(default_factory=list)
    location_metro_links: list[dict[str, Any]] = field(default_factory=list)
    officials: list[dict[str, Any]] = field(default_factory=list)
    edition_officials: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    gate: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "edition_attributes": len(self.attributes),
            "edition_status_history": len(self.status_history),
            "metros": len(self.metros),
            "venues": len(self.venues),
            "location_metro_links": len(self.location_metro_links),
            "officials": len(self.officials),
            "edition_officials": len(self.edition_officials),
        }


def normalize_todd_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Keep WSDC Todd rows only; attach parsed key fields."""
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        tid = _clean(r.get("event_edition_id"))
        if not tid:
            continue
        parsed = parse_todd_edition_id(tid)
        if parsed is None:
            continue
        rows.append(
            {
                "todd_edition_id": parsed.todd_edition_id,
                "wsdc_event_id": parsed.wsdc_event_id,
                "filing_year": parsed.event_year,
                "filing_month": parsed.event_month,
                "event_series_id": _clean(r.get("event_series_id")),
                "edition_status": _clean(r.get("edition_status")) or "",
                "cancelled_covid": _bool(r.get("cancelled_covid")),
                "event_edition_name": _clean(r.get("event_edition_name")),
                "wsdc_event_name": _clean(r.get("wsdc_event_name")),
                "start_date": _date(r.get("start_date")),
                "end_date": _date(r.get("end_date")),
                "registry_status": _clean(r.get("registry_status")),
                "scoring_software": _clean(r.get("scoring_software")),
                "coordinates_precision": _clean(r.get("coordinates_precision")),
                "date_precision": _clean(r.get("date_precision")),
                "accommodation_hotel": _clean(r.get("accommodation_hotel")),
                "row_info": _jsonb(r.get("row_info")),
                "city": _clean(r.get("city")),
                "region": _clean(r.get("region")),
                "country": _clean(r.get("country")),
                "metro": _clean(r.get("metro")),
                "latitude": r.get("latitude") if pd.notna(r.get("latitude")) else None,
                "longitude": r.get("longitude") if pd.notna(r.get("longitude")) else None,
                "venue_name": _clean(r.get("venue_name")),
                "venue_address": _clean(r.get("venue_address")),
                "venue_type": _clean(r.get("venue_type")),
                "venue_url": _clean(r.get("venue_url")),
                "chief_judge": _clean(r.get("chief_judge")),
                "scoreperson": _clean(r.get("scoreperson")),
                "judges": r.get("judges"),
                "judge_rounds": r.get("judge_rounds"),
            }
        )
    return rows


def build_ee_tables(
    df: pd.DataFrame,
    *,
    core_editions: list[dict[str, Any]],
    decisions: dict[str, Any],
    locations: list[dict[str, Any]] | None = None,
    dancers: list[dict[str, Any]] | None = None,
    include_metros_venues: bool = False,
    include_officials: bool = False,
) -> EeTables:
    todd_rows = normalize_todd_frame(df)
    core_keys = build_core_key_set(core_editions)
    core_by_key = {
        (int(e["event_id"]), int(e["event_year"]), int(e["event_month"])): e
        for e in core_editions
    }
    matches = [
        match_edition(r["todd_edition_id"], core_keys=core_keys) for r in todd_rows
    ]
    matches = [m for m in matches if m is not None]

    gate = reconcile(
        todd_rows=todd_rows,
        matches=matches,
        core_keys=core_keys,
        decisions=decisions,
        core_by_key=core_by_key,
    )

    match_by_id = {m["todd_edition_id"]: m for m in matches}
    tables = EeTables(gate=gate)
    attrs: dict[tuple[int, int, int], dict[str, Any]] = {}
    status: dict[tuple[int, int, int], dict[str, Any]] = {}
    # exact preferred over merge_map / month_shift when several Todd ids collide
    match_rank = {"exact": 0, "merge_map": 1, "month_shift": 2}

    for row in todd_rows:
        tid = row["todd_edition_id"]
        m = match_by_id[tid]
        status_name = row["edition_status"]

        if status_name == "occurred" and m["match_kind"] != "unmatched":
            key = (m["event_id"], m["event_year"], m["event_month"])
            candidate = {
                "event_id": m["event_id"],
                "event_year": m["event_year"],
                "event_month": m["event_month"],
                "todd_edition_id": tid,
                "match_kind": m["match_kind"],
                "venue_id": None,
                "registry_status": row["registry_status"],
                "scoring_software": row["scoring_software"],
                "coordinates_precision": row["coordinates_precision"],
                "date_precision": row["date_precision"],
                "accommodation_hotel": row["accommodation_hotel"],
                "wsdc_event_name": row["wsdc_event_name"],
                "row_info": row["row_info"],
            }
            existing = attrs.get(key)
            if existing is None:
                attrs[key] = candidate
            else:
                old_r = match_rank.get(existing["match_kind"], 99)
                new_r = match_rank.get(m["match_kind"], 99)
                if new_r < old_r:
                    attrs[key] = candidate
                # else keep preferred (exact) row; collision handled by gate
        elif status_name in STATUS_HISTORY:
            # Prefer canonical filing key (raw Todd month), not month_shift target
            event_id = int(m.get("raw_wsdc_event_id") or m["event_id"])
            # Use MERGE canonical for storage consistency with core
            from transform.event_editions.match import canonical_event_id

            event_id = canonical_event_id(event_id)
            y = int(row["filing_year"])
            mo = int(row["filing_month"])
            key = (event_id, y, mo)
            status[key] = {
                "event_id": event_id,
                "event_year": y,
                "event_month": mo,
                "todd_edition_id": tid,
                "edition_status": status_name,
                "cancelled_covid": row["cancelled_covid"],
                "event_edition_name": row["event_edition_name"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "registry_status": row["registry_status"],
                "city": row["city"],
                "region": row["region"],
                "country": row["country"],
            }
        elif status_name == FUTURE_SCHEDULED:
            continue

    tables.attributes = list(attrs.values())
    tables.status_history = list(status.values())
    tables.stats = {
        "todd_wsdc_rows": len(todd_rows),
        "matched_occurred": sum(
            1
            for r in todd_rows
            if r["edition_status"] == "occurred"
            and match_by_id[r["todd_edition_id"]]["match_kind"] != "unmatched"
        ),
        "status_history": len(tables.status_history),
        "skipped_scheduled": sum(
            1 for r in todd_rows if r["edition_status"] == FUTURE_SCHEDULED
        ),
        "match_kinds": {
            k: sum(1 for m in matches if m["match_kind"] == k)
            for k in ("exact", "merge_map", "month_shift", "unmatched")
        },
    }

    if include_metros_venues:
        from transform.event_editions.metros import build_metros
        from transform.event_editions.venues import build_venues

        tables.metros, tables.location_metro_links = build_metros(
            todd_rows, locations=locations or []
        )
        tables.venues, venue_by_todd = build_venues(todd_rows, locations=locations or [])
        for row in tables.attributes:
            tid = row["todd_edition_id"]
            row["venue_id"] = venue_by_todd.get(tid)

    if include_officials:
        from transform.event_editions.officials import build_officials

        tables.officials, tables.edition_officials = build_officials(
            todd_rows,
            attributes=tables.attributes,
            dancers=dancers or [],
        )

    return tables
