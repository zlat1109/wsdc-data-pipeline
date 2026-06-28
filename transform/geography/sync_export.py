"""Sync city/location columns in export CSVs from location_info."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from transform.geography.city import (
    apply_string_replacement,
    location_lookup,
    normalize_location_whitespace,
    sync_upcoming_location_string,
)

_EDITION_LOCATION_FIELDS = (
    ("event_city", "place_city"),
    ("event_state", "place_state"),
    ("event_country", "place_country"),
    ("event_location", "location_raw"),
)

_CATALOG_TYPICAL_FIELDS = (
    ("typical_city", "place_city"),
    ("typical_state", "place_state"),
    ("typical_country", "place_country"),
    ("typical_location", "location_raw"),
)


def sync_editions_from_location_info(
    editions: pd.DataFrame,
    lookup: dict[int, dict[str, str]],
) -> tuple[pd.DataFrame, int]:
    """Refresh edition place columns from location_info; never touch typical_location."""
    out = editions.copy()
    changed = 0
    for idx, row in out.iterrows():
        location_id = row.get("location_id")
        if pd.isna(location_id):
            continue
        loc = lookup.get(int(location_id))
        if not loc:
            continue
        for src, dst in _EDITION_LOCATION_FIELDS:
            if dst in out.columns and loc.get(src):
                if out.at[idx, dst] != loc[src]:
                    out.at[idx, dst] = loc[src]
                    changed += 1
    return out, changed


def sync_catalog_typical_from_editions(
    catalog: pd.DataFrame,
    editions: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Set catalog typical_* from the latest edition per event."""
    if not {"event_id", "event_year", "event_month"}.issubset(editions.columns):
        return catalog, 0

    out = catalog.copy()
    latest = (
        editions.sort_values(["event_id", "event_year", "event_month"], ascending=[True, False, False])
        .drop_duplicates(subset=["event_id"], keep="first")
        .set_index("event_id")
    )
    changed = 0
    for idx, row in out.iterrows():
        event_id = row.get("event_id")
        if pd.isna(event_id) or int(event_id) not in latest.index:
            continue
        src = latest.loc[int(event_id)]
        for dst, src_col in _CATALOG_TYPICAL_FIELDS:
            if dst in out.columns and pd.notna(src.get(src_col)):
                value = str(src[src_col]).strip()
                if out.at[idx, dst] != value:
                    out.at[idx, dst] = value
                    changed += 1
    return out, changed


def sync_catalog_upcoming_locations(
    catalog: pd.DataFrame,
    string_replacements: dict[str, str],
) -> tuple[pd.DataFrame, int]:
    """Normalize upcoming_location without overwriting a different venue."""
    if not {"typical_location", "upcoming_location"}.issubset(catalog.columns):
        return catalog, 0

    out = catalog.copy()
    changed = 0
    for idx, row in out.iterrows():
        typical = str(row.get("typical_location", "")).strip()
        upcoming = str(row.get("upcoming_location", "")).strip()
        new_upcoming = sync_upcoming_location_string(
            upcoming,
            typical,
            string_replacements=string_replacements,
        )
        if new_upcoming != upcoming:
            out.at[idx, "upcoming_location"] = new_upcoming
            changed += 1
    return out, changed


def normalize_export_location_columns(
    data_dir: Path,
    *,
    string_replacements: dict[str, str],
    editions: pd.DataFrame | None,
) -> dict[str, int]:
    """Apply known replacements and whitespace fixes to wsdc/schedule export columns."""
    updates: dict[str, int] = {}
    for filename, location_col in (
        ("events_wsdc.csv", "location"),
        ("scheduled_events.csv", "location_raw"),
    ):
        path = data_dir / filename
        if not path.exists() or location_col not in pd.read_csv(path, nrows=0).columns:
            continue
        frame = pd.read_csv(path, low_memory=False)
        changed = 0
        for idx, value in frame[location_col].items():
            if pd.isna(value):
                continue
            text = str(value).strip()
            new_text = normalize_location_whitespace(
                apply_string_replacement(text, string_replacements),
            )

            if new_text == text and editions is not None and filename == "events_wsdc.csv":
                event_id = frame.at[idx, "id"] if "id" in frame.columns else frame.at[idx, "event_id"]
                event_year = frame.at[idx, "event_year"]
                event_month = frame.at[idx, "event_month"]
                match = editions[
                    (editions["event_id"] == event_id)
                    & (editions["event_year"] == event_year)
                    & (editions["event_month"] == event_month)
                ]
                if not match.empty and pd.notna(match.iloc[0].get("location_raw")):
                    candidate = str(match.iloc[0]["location_raw"]).strip()
                    if candidate and candidate != text:
                        new_text = candidate

            if new_text != text:
                frame.at[idx, location_col] = new_text
                changed += 1
        if changed:
            frame.to_csv(path, index=False)
        updates[filename] = changed
    return updates


def sync_export_city_columns(
    data_dir: Path,
    *,
    replacements: dict[str, str] | None = None,
) -> dict[str, int]:
    """Refresh city columns in export CSVs from location_info."""
    location_path = data_dir / "location_info.csv"
    if not location_path.exists():
        return {}

    locations = pd.read_csv(location_path, low_memory=False)
    lookup = location_lookup(locations)
    string_replacements = {k.upper(): v for k, v in (replacements or {}).items()}
    updates: dict[str, int] = {}

    editions_path = data_dir / "event_editions.csv"
    editions = pd.read_csv(editions_path, low_memory=False) if editions_path.exists() else None

    if editions is not None:
        editions, changed = sync_editions_from_location_info(editions, lookup)
        if changed:
            editions.to_csv(editions_path, index=False)
        updates["event_editions.csv"] = changed

    catalog_path = data_dir / "event_catalog.csv"
    if catalog_path.exists():
        catalog = pd.read_csv(catalog_path, low_memory=False)
        catalog_changed = 0

        if editions is not None:
            catalog, typical_changed = sync_catalog_typical_from_editions(catalog, editions)
            catalog_changed += typical_changed

        catalog, upcoming_changed = sync_catalog_upcoming_locations(catalog, string_replacements)
        catalog_changed += upcoming_changed

        if catalog_changed:
            catalog.to_csv(catalog_path, index=False)
        updates["event_catalog.csv"] = catalog_changed

    updates.update(
        normalize_export_location_columns(
            data_dir,
            string_replacements=string_replacements,
            editions=editions,
        )
    )
    return updates
