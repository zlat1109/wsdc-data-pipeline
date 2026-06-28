"""Geo-aware event identity helpers for dedup and Tableau analytics."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

SplitAction = Literal["merge_candidate", "keep_separate", "manual_review"]

# Metro clusters: cities treated as one geo for merge decisions (same raw event name).
# Key -> set of city names; all must share state/country context when resolved.
METRO_CLUSTERS: dict[str, dict[str, object]] = {
    "greater_boston_ma": {
        "cities": {"Boston", "Framingham"},
        "state": "Massachusetts",
        "country": "United States",
        "label": "Boston / Framingham, MA",
    },
}

# Pairs of event_id that must never merge (same marketing name, different geography).
KEEP_SEPARATE_EVENT_PAIRS: frozenset[frozenset[int]] = frozenset(
    {
        frozenset({75, 152}),   # Worlds UCWDC: Dallas vs Orlando
        frozenset({191, 230}),  # Sunny Side Dance Camp: Crimea vs Spain
        frozenset({83, 204}),   # Spring Swing: Detroit vs Stockholm
    }
)

KEEP_SEPARATE_EVENT_IDS: frozenset[int] = frozenset().union(*KEEP_SEPARATE_EVENT_PAIRS)


def _norm_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def _norm_key_part(value: object) -> str:
    text = _norm_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def geo_key(city: object, state: object, country: object) -> str:
    """Stable geography fingerprint for merge gating."""
    city_s = _norm_text(city)
    state_s = _norm_text(state)
    country_s = _norm_text(country)
    metro = metro_cluster_for(city_s, state_s, country_s)
    if metro:
        return f"metro:{metro}"
    return "|".join(
        part for part in (_norm_key_part(city_s), _norm_key_part(state_s), _norm_key_part(country_s)) if part
    )


def _geo_field_match(actual: str, expected: str) -> bool:
    if not expected:
        return True
    if not actual:
        return False
    return _norm_text(actual).lower() == _norm_text(expected).lower()


def metro_cluster_for(city: str, state: str, country: str) -> str | None:
    if not city:
        return None
    city_fold = city.strip().title()
    for cluster_id, meta in METRO_CLUSTERS.items():
        cities = meta.get("cities") or set()
        if city not in cities and city_fold not in cities:
            continue
        expected_state = _norm_text(meta.get("state"))
        expected_country = _norm_text(meta.get("country"))
        if not _geo_field_match(state, expected_state):
            continue
        if not _geo_field_match(country, expected_country):
            continue
        return cluster_id
    return None


def metro_label(cluster_id: str | None) -> str | None:
    if not cluster_id:
        return None
    meta = METRO_CLUSTERS.get(cluster_id)
    if not meta:
        return None
    return str(meta.get("label") or cluster_id)


def geo_event_key(canonical_name: object, city: object, state: object, country: object) -> str:
    """Analytical event identity: brand name + geography."""
    name_part = _norm_key_part(canonical_name) or "unknown_event"
    return f"{name_part}::{geo_key(city, state, country)}"


def geo_keys_mergeable(key_a: str, key_b: str) -> bool:
    if not key_a or not key_b:
        return False
    return key_a == key_b


def classify_event_id_pair(event_id_a: int, event_id_b: int, geo_key_a: str, geo_key_b: str) -> SplitAction:
    pair = frozenset({event_id_a, event_id_b})
    if pair in KEEP_SEPARATE_EVENT_PAIRS:
        return "keep_separate"
    if geo_keys_mergeable(geo_key_a, geo_key_b):
        return "merge_candidate"
    if geo_key_a and geo_key_b and geo_key_a != geo_key_b:
        return "keep_separate"
    return "manual_review"


def resolve_result_geo(
    results_row: dict[str, object],
    location_lookup: dict[str, dict[str, str]],
) -> tuple[str, str, str]:
    """Resolve city/state/country for a results row using location_id or event_location."""
    loc_id = _norm_text(results_row.get("location_id"))
    if loc_id and loc_id in location_lookup:
        loc = location_lookup[loc_id]
        return loc.get("event_city", ""), loc.get("event_state", ""), loc.get("event_country", "")

    raw = _norm_text(results_row.get("event_location"))
    if not raw:
        return "", "", ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "", "", ""
    city = parts[0]
    country = parts[-1] if len(parts) > 1 else ""
    state = parts[1] if len(parts) > 2 else ""
    return city, state, country


def build_location_lookup(location_df) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    if location_df is None or getattr(location_df, "empty", True):
        return lookup
    for _, row in location_df.iterrows():
        loc_id = _norm_text(row.get("location_id"))
        if not loc_id:
            continue
        lookup[loc_id] = {
            "event_city": _norm_text(row.get("event_city")),
            "event_state": _norm_text(row.get("event_state")),
            "event_country": _norm_text(row.get("event_country")),
        }
    return lookup
