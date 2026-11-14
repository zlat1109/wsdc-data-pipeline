"""Build ``core.metros`` and location→metro links from Todd rows."""

from __future__ import annotations

import re
from typing import Any


def _norm_place(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def build_metros(
    todd_rows: list[dict[str, Any]],
    *,
    locations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (metros, location_metro_links).

    ``location_metro_links`` is ``[{location_id, metro_id}]`` for backfill.
    Metro ids are stable hashes of normalized metro name (positive int).
    """
    buckets: dict[str, dict[str, Any]] = {}
    for row in todd_rows:
        metro = row.get("metro")
        if not metro:
            continue
        key = _norm_place(metro)
        b = buckets.setdefault(
            key,
            {
                "name": metro,
                "country": row.get("country"),
                "lats": [],
                "lons": [],
                "cities": set(),
            },
        )
        if row.get("country") and not b["country"]:
            b["country"] = row["country"]
        if row.get("latitude") is not None and row.get("longitude") is not None:
            b["lats"].append(float(row["latitude"]))
            b["lons"].append(float(row["longitude"]))
        city = row.get("city")
        if city:
            b["cities"].add(
                (
                    _norm_place(city),
                    _norm_place(row.get("region")),
                    _norm_place(row.get("country")),
                )
            )

    metros: list[dict[str, Any]] = []
    name_to_id: dict[str, int] = {}
    for i, (key, b) in enumerate(sorted(buckets.items()), start=1):
        metro_id = i
        name_to_id[key] = metro_id
        lat = sum(b["lats"]) / len(b["lats"]) if b["lats"] else None
        lon = sum(b["lons"]) / len(b["lons"]) if b["lons"] else None
        metros.append(
            {
                "metro_id": metro_id,
                "name": b["name"],
                "country": b["country"],
                "latitude": round(lat, 6) if lat is not None else None,
                "longitude": round(lon, 6) if lon is not None else None,
            }
        )

    # Map location → metro via city/state/country overlap with Todd places in that metro
    city_to_metro: dict[tuple[str, str, str], int] = {}
    for key, b in buckets.items():
        mid = name_to_id[key]
        for city_key in b["cities"]:
            city_to_metro[city_key] = mid

    links: list[dict[str, Any]] = []
    seen: set[int] = set()
    for loc in locations:
        lid = int(loc["location_id"])
        if lid in seen:
            continue
        ck = (
            _norm_place(loc.get("event_city")),
            _norm_place(loc.get("event_state")),
            _norm_place(loc.get("event_country")),
        )
        mid = city_to_metro.get(ck)
        if mid is None:
            # try city+country only
            for (c, _s, co), m in city_to_metro.items():
                if c == ck[0] and co == ck[2] and c:
                    mid = m
                    break
        if mid is None:
            continue
        seen.add(lid)
        links.append({"location_id": lid, "metro_id": mid})

    return metros, links
