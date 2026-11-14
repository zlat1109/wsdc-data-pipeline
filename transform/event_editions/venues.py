"""Deduplicate Todd venues into ``core.venues``."""

from __future__ import annotations

import re
from typing import Any


def normalize_venue_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    for suffix in (
        " hotel",
        " resort",
        " conference center",
        " conference centre",
        " casino",
        " & spa",
        " and spa",
    ):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _norm_addr(addr: str | None) -> str:
    if not addr:
        return ""
    return re.sub(r"\s+", " ", addr.strip().lower())


def build_venues(
    todd_rows: list[dict[str, Any]],
    *,
    locations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return (venues, todd_edition_id → venue_id)."""
    loc_by_city: dict[tuple[str, str, str], int] = {}
    for loc in locations:
        key = (
            (loc.get("event_city") or "").strip().lower(),
            (loc.get("event_state") or "").strip().lower(),
            (loc.get("event_country") or "").strip().lower(),
        )
        if key[0]:
            loc_by_city.setdefault(key, int(loc["location_id"]))

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    todd_to_key: dict[str, tuple[str, str]] = {}

    for row in todd_rows:
        name = row.get("venue_name")
        if not name:
            continue
        nname = normalize_venue_name(name)
        naddr = _norm_addr(row.get("venue_address"))
        key = (nname, naddr)
        if key not in buckets:
            buckets[key] = {
                "name": name,
                "address": row.get("venue_address"),
                "venue_type": row.get("venue_type"),
                "venue_url": row.get("venue_url"),
                "latitude": row.get("latitude")
                if row.get("coordinates_precision") == "venue"
                else None,
                "longitude": row.get("longitude")
                if row.get("coordinates_precision") == "venue"
                else None,
                "city": row.get("city"),
                "region": row.get("region"),
                "country": row.get("country"),
            }
            order.append(key)
        else:
            b = buckets[key]
            if not b["venue_type"] and row.get("venue_type"):
                b["venue_type"] = row["venue_type"]
            if not b["venue_url"] and row.get("venue_url"):
                b["venue_url"] = row["venue_url"]
            if b["latitude"] is None and row.get("coordinates_precision") == "venue":
                b["latitude"] = row.get("latitude")
                b["longitude"] = row.get("longitude")
        todd_to_key[row["todd_edition_id"]] = key

    venues: list[dict[str, Any]] = []
    key_to_id: dict[tuple[str, str], int] = {}
    for i, key in enumerate(order, start=1):
        b = buckets[key]
        ck = (
            (b.get("city") or "").strip().lower(),
            (b.get("region") or "").strip().lower(),
            (b.get("country") or "").strip().lower(),
        )
        location_id = loc_by_city.get(ck)
        venues.append(
            {
                "venue_id": i,
                "name": b["name"],
                "name_normalized": key[0],
                "address": b["address"],
                "venue_type": b["venue_type"],
                "venue_url": b["venue_url"],
                "latitude": b["latitude"],
                "longitude": b["longitude"],
                "location_id": location_id,
            }
        )
        key_to_id[key] = i

    todd_to_venue = {
        tid: key_to_id[k] for tid, k in todd_to_key.items() if k in key_to_id
    }
    return venues, todd_to_venue
