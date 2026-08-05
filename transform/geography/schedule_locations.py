"""Assign location_id on events-list rows; seed results from schedule for trials."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from transform.geography.ensure_location import (
    SOURCE_UNRESOLVED,
    EnsureLocationResult,
    ensure_location,
)
from transform.geography.utils import norm_value
from transform.knowledge.events import EVENT_NAME_LOCATION_OVERRIDES

logger = logging.getLogger(__name__)


def is_trial_status(status_event: object) -> bool:
    text = str(status_event or "").strip().lower()
    return "trial" in text


def needs_list_geo(row: dict[str, Any]) -> bool:
    """Only fill gaps for Trial Event rows (do not rework Registry coverage)."""
    if not is_trial_status(row.get("status_event")):
        return False
    if str(row.get("location_id") or "").strip():
        return False
    return bool(str(row.get("location_raw") or "").strip())


def assign_schedule_locations(
    events: list[dict[str, Any]],
    location_df: pd.DataFrame,
    *,
    allow_geocode: bool = True,
    geocode_fn=None,
    id_floor: int = 0,
) -> tuple[list[dict[str, Any]], pd.DataFrame, list[dict[str, Any]]]:
    """Fill location_id/location_source on Trial list rows. Returns review items."""
    review: list[dict[str, Any]] = []
    out = list(events)
    for ev in out:
        if not needs_list_geo(ev):
            continue
        result, location_df = ensure_location(
            str(ev.get("location_raw") or ""),
            country=str(ev.get("country") or ""),
            location_df=location_df,
            geocode_fn=geocode_fn,
            allow_create=True,
            allow_geocode=allow_geocode,
            id_floor=id_floor,
        )
        _apply_result(ev, result)
        if result.review_reason:
            review.append(
                {
                    "event_name": ev.get("event_name"),
                    "start_date": ev.get("start_date"),
                    "location_raw": ev.get("location_raw"),
                    "country": ev.get("country"),
                    "reason": result.review_reason,
                    "location_id": result.location_id,
                    "location_source": result.source,
                }
            )
    return out, location_df, review


def _apply_result(ev: dict[str, Any], result: EnsureLocationResult) -> None:
    if result.location_id:
        ev["location_id"] = (
            int(result.location_id)
            if str(result.location_id).isdigit()
            else result.location_id
        )
        ev["location_source"] = result.source
    else:
        ev["location_id"] = None
        ev["location_source"] = result.source or SOURCE_UNRESOLVED


def schedule_location_by_event_name(
    scheduled: pd.DataFrame,
) -> dict[str, str]:
    """event_name → location_id (prefer Trial rows; first non-empty wins)."""
    if scheduled is None or scheduled.empty:
        return {}
    if "event_name" not in scheduled.columns or "location_id" not in scheduled.columns:
        return {}

    out: dict[str, str] = {}
    order = scheduled.copy()
    if "status_event" in order.columns:
        order["_trial"] = order["status_event"].map(is_trial_status)
        order = order.sort_values("_trial", ascending=False)
    for _, row in order.iterrows():
        name = str(row.get("event_name") or "").strip()
        lid = str(row.get("location_id") or "").strip()
        if not name or not lid or lid.lower() == "nan":
            continue
        out.setdefault(name, lid)
    return out


def seed_result_locations_from_schedule(
    results_df: pd.DataFrame,
    scheduled_df: pd.DataFrame,
    *,
    trial_force: bool = True,
) -> tuple[pd.DataFrame, int]:
    """Attach schedule location_id to results when safe.

    - Always fill empty location_id when schedule has one (and no override).
    - For Trial schedule names: also replace a non-empty (wrong) location_id
      unless EVENT_NAME_LOCATION_OVERRIDES covers the name.
    """
    if results_df is None or results_df.empty:
        return results_df, 0
    if "event_name" not in results_df.columns:
        return results_df, 0

    name_to_lid = schedule_location_by_event_name(scheduled_df)
    if not name_to_lid:
        return results_df, 0

    trial_names: set[str] = set()
    if trial_force and scheduled_df is not None and not scheduled_df.empty:
        if "status_event" in scheduled_df.columns and "event_name" in scheduled_df.columns:
            for _, row in scheduled_df.iterrows():
                if is_trial_status(row.get("status_event")):
                    n = str(row.get("event_name") or "").strip()
                    if n and n in name_to_lid:
                        trial_names.add(n)

    out = results_df.copy()
    if "location_id" not in out.columns:
        out["location_id"] = ""

    changed = 0
    for idx in out.index:
        name = str(out.at[idx, "event_name"] or "").strip()
        if not name or name in EVENT_NAME_LOCATION_OVERRIDES:
            continue
        want = name_to_lid.get(name)
        if not want:
            continue
        cur = str(out.at[idx, "location_id"] or "").strip()
        if cur == want:
            continue
        if cur and name not in trial_names:
            continue
        out.at[idx, "location_id"] = want
        changed += 1
    return out, changed


def db_max_location_id(cur: Any) -> int:
    cur.execute("SELECT COALESCE(MAX(location_id), 0) FROM core.locations")
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def lookup_location_id_by_event_location(cur: Any, event_location: str) -> int | None:
    text = norm_value(event_location)
    if not text:
        return None
    cur.execute(
        """
        SELECT location_id
        FROM core.locations
        WHERE event_location IS NOT NULL
          AND btrim(event_location) <> ''
          AND lower(btrim(event_location)) = lower(btrim(%s))
        ORDER BY location_id
        LIMIT 1
        """,
        (text,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def upsert_locations_to_db(
    cur: Any,
    location_df: pd.DataFrame,
    new_ids: set[str],
) -> tuple[int, dict[str, str]]:
    """Insert/update core.locations; reuse existing row on event_location unique hit.

    Returns (rows_touched, id_remaps) where id_remaps maps provisional CSV id →
    canonical DB id when the unique place string already existed.
    """
    if not new_ids or location_df is None or location_df.empty:
        return 0, {}

    remaps: dict[str, str] = {}
    n = 0
    for _, row in location_df.iterrows():
        lid = str(row.get("location_id") or "").strip()
        if lid not in new_ids:
            continue
        event_location = str(row.get("event_location") or "").strip() or None
        existing = (
            lookup_location_id_by_event_location(cur, event_location)
            if event_location
            else None
        )
        if existing is not None and str(existing) != lid:
            remaps[lid] = str(existing)
            lid = str(existing)

        lat = row.get("latitude")
        lon = row.get("longitude")
        lat_v = float(lat) if str(lat).strip() not in {"", "nan", "None"} else None
        lon_v = float(lon) if str(lon).strip() not in {"", "nan", "None"} else None
        valid = lat_v is not None and lon_v is not None
        try:
            cur.execute(
                """
                INSERT INTO core.locations (
                    location_id, event_city, event_state, event_country,
                    latitude, longitude, event_location, event_location_standardized,
                    coordinates_valid
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (location_id) DO UPDATE SET
                    event_city = COALESCE(
                        NULLIF(EXCLUDED.event_city, ''), core.locations.event_city
                    ),
                    event_state = COALESCE(
                        NULLIF(EXCLUDED.event_state, ''), core.locations.event_state
                    ),
                    event_country = COALESCE(
                        NULLIF(EXCLUDED.event_country, ''), core.locations.event_country
                    ),
                    event_location = COALESCE(
                        NULLIF(EXCLUDED.event_location, ''), core.locations.event_location
                    ),
                    event_location_standardized = COALESCE(
                        NULLIF(EXCLUDED.event_location_standardized, ''),
                        core.locations.event_location_standardized
                    ),
                    latitude = COALESCE(core.locations.latitude, EXCLUDED.latitude),
                    longitude = COALESCE(core.locations.longitude, EXCLUDED.longitude),
                    coordinates_valid = CASE
                        WHEN core.locations.coordinates_valid IS TRUE THEN true
                        ELSE EXCLUDED.coordinates_valid
                    END
                """,
                (
                    int(lid),
                    str(row.get("event_city") or "") or None,
                    str(row.get("event_state") or "") or None,
                    str(row.get("event_country") or "") or None,
                    lat_v,
                    lon_v,
                    event_location,
                    str(row.get("event_location_standardized") or "") or None,
                    valid,
                ),
            )
        except Exception as exc:
            unique = False
            try:
                from psycopg.errors import UniqueViolation

                unique = isinstance(exc, UniqueViolation)
            except ImportError:
                unique = "locations_event_location_norm_uidx" in str(exc)
            if not unique and "locations_event_location_norm_uidx" not in str(exc):
                raise
            owner = lookup_location_id_by_event_location(cur, event_location or "")
            if owner is None:
                raise
            remaps[str(row.get("location_id") or "").strip()] = str(owner)
            if lat_v is not None and lon_v is not None:
                cur.execute(
                    """
                    UPDATE core.locations
                    SET latitude = COALESCE(latitude, %s),
                        longitude = COALESCE(longitude, %s),
                        coordinates_valid = CASE
                            WHEN coordinates_valid IS TRUE THEN true
                            ELSE %s
                        END
                    WHERE location_id = %s
                    """,
                    (lat_v, lon_v, valid, owner),
                )
            n += 1
            continue
        n += 1
    return n, remaps


def apply_location_id_remaps(
    events: list[dict[str, Any]],
    location_df: pd.DataFrame,
    remaps: dict[str, str],
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Rewrite provisional ids to canonical DB owners; drop duplicate CSV rows."""
    if not remaps:
        return events, location_df
    for ev in events:
        lid = str(ev.get("location_id") or "").strip()
        if lid in remaps:
            canon = remaps[lid]
            ev["location_id"] = int(canon) if canon.isdigit() else canon
    if location_df is None or location_df.empty:
        return events, location_df
    out = location_df.copy()
    drop_ids = set()
    for provisional, canon in remaps.items():
        if provisional == canon:
            continue
        pmask = out["location_id"].astype(str).str.strip() == provisional
        cmask = out["location_id"].astype(str).str.strip() == canon
        if pmask.any() and cmask.any():
            # Prefer coords already on canonical; then drop provisional row.
            drop_ids.add(provisional)
        elif pmask.any() and not cmask.any():
            out.loc[pmask, "location_id"] = canon
    if drop_ids:
        out = out[~out["location_id"].astype(str).str.strip().isin(drop_ids)].copy()
    return events, out
