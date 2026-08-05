"""Tests for export CSV location sync pipeline."""

import pandas as pd

from transform.geography.city import sync_typical_location_from_edition
from transform.geography.sync_export import (
    backfill_wsdc_locations_from_editions,
    sync_catalog_typical_from_editions,
    sync_export_city_columns,
)


def test_sync_typical_location_preserves_different_venue():
    result = sync_typical_location_from_edition(
        "Madrid, Spain",
        "Madrid, Madrid, Spain",
        string_replacements={},
    )
    assert result == "Madrid, Spain"


def test_sync_typical_location_fills_empty_from_edition():
    result = sync_typical_location_from_edition(
        "",
        "Madrid, Spain",
        string_replacements={},
    )
    assert result == "Madrid, Spain"


def test_sync_catalog_typical_preserves_venue_metadata():
    catalog = pd.DataFrame(
        [
            {
                "event_id": 347,
                "typical_location": "Madrid, Spain",
                "typical_city": "Madrid",
            }
        ]
    )
    editions = pd.DataFrame(
        [
            {
                "event_id": 347,
                "event_year": 2025,
                "event_month": 3,
                "place_city": "Madrid",
                "location_raw": "Madrid, Madrid, Spain",
            }
        ]
    )
    out, changed = sync_catalog_typical_from_editions(
        catalog,
        editions,
        string_replacements={},
    )
    assert out.loc[0, "typical_location"] == "Madrid, Spain"
    assert changed == 0


def test_sync_export_preserves_catalog_typical_location(tmp_path):
    location_info = pd.DataFrame(
        [
            {
                "location_id": 170,
                "event_city": "Madrid",
                "event_state": "",
                "event_country": "Spain",
                "event_location": "Madrid, Madrid, Spain",
            }
        ]
    )
    location_info.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "event_id": 347,
                "event_year": 2025,
                "event_month": 3,
                "location_id": 170,
                "place_city": "Madrid",
                "location_raw": "Madrid, Madrid, Spain",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)
    catalog = pd.DataFrame(
        [
            {
                "event_id": 347,
                "typical_location": "Madrid, Spain",
                "upcoming_location": "Madrid, Spain",
            }
        ]
    )
    catalog.to_csv(tmp_path / "event_catalog.csv", index=False)

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "event_catalog.csv")
    assert out.loc[0, "typical_location"] == "Madrid, Spain"


def test_sync_export_preserves_scheduled_location_raw(tmp_path):
    catalog = pd.DataFrame(
        [
            {
                "event_id": 347,
                "typical_location": "Madrid, Madrid, Spain",
                "upcoming_location": "Madrid, Spain",
            }
        ]
    )
    catalog.to_csv(tmp_path / "event_catalog.csv", index=False)
    scheduled = pd.DataFrame(
        [
            {
                "canonical_event_id": 347,
                "location_raw": "Madrid, Spain",
            }
        ]
    )
    scheduled.to_csv(tmp_path / "scheduled_events.csv", index=False)
    (tmp_path / "location_info.csv").write_text("location_id,event_city\n", encoding="utf-8")

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "scheduled_events.csv")
    assert out.loc[0, "location_raw"] == "Madrid, Spain"


def test_sync_export_city_columns_updates_editions(tmp_path):
    location = pd.DataFrame(
        [
            {
                "location_id": 104,
                "event_city": "Chicago",
                "event_state": "Illinois",
                "event_country": "United States",
                "event_location": "Chicago, IL, United States",
                "event_location_standardized": "Chicago, IL",
            }
        ]
    )
    location.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "edition_id": 1,
                "event_id": 125,
                "location_id": 104,
                "place_city": "CHICAGO",
                "place_state": "Illinois",
                "place_country": "United States",
                "location_raw": "CHICAGO, IL, United States",
                "typical_location": "CHICAGO, IL, United States",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)

    updates = sync_export_city_columns(tmp_path)

    synced = pd.read_csv(tmp_path / "event_editions.csv")
    assert synced.loc[0, "place_city"] == "Chicago"
    assert synced.loc[0, "location_raw"] == "Chicago, IL, United States"
    assert updates["event_editions.csv"] > 0


def test_sync_editions_preserves_typical_location(tmp_path):
    """Edition-level typical_location is export metadata; not overwritten from location_info."""
    location_info = pd.DataFrame(
        [
            {
                "location_id": 170,
                "event_city": "Madrid",
                "event_state": "",
                "event_country": "Spain",
                "event_location": "Madrid, Madrid, Spain",
            }
        ]
    )
    location_info.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "event_id": 347,
                "event_year": 2025,
                "event_month": 3,
                "location_id": 170,
                "place_city": "Madrid",
                "location_raw": "Madrid, Spain",
                "typical_location": "Madrid, Spain",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "event_editions.csv")
    assert out.loc[0, "location_raw"] == "Madrid, Madrid, Spain"
    assert out.loc[0, "typical_location"] == "Madrid, Spain"


def test_backfill_wsdc_locations_from_editions():
    editions = pd.DataFrame(
        [
            {
                "event_id": 125,
                "event_year": 2025,
                "event_month": 3,
                "location_raw": "Chicago, IL, United States",
            }
        ]
    )
    frame = pd.DataFrame(
        [
            {
                "id": 125,
                "event_year": 2025,
                "event_month": 3,
                "location": "CHICAGO, IL, United States",
            }
        ]
    )
    out, changed = backfill_wsdc_locations_from_editions(frame, "location", editions)
    assert changed == 1
    assert out.loc[0, "location"] == "Chicago, IL, United States"


def test_backfill_skips_event_name_location_overrides():
    """Stale edition Jeju must not undo EVENT_NAME_LOCATION_OVERRIDES (Montreal)."""
    editions = pd.DataFrame(
        [
            {
                "event_id": 178,
                "event_year": 2011,
                "event_month": 10,
                "location_raw": "Jeju, Republic of Korea",
            }
        ]
    )
    frame = pd.DataFrame(
        [
            {
                "id": 178,
                "name": "Montreal Westie Fest",
                "event_year": 2011,
                "event_month": 10,
                "location": "Montreal, Canada",
            }
        ]
    )
    out, changed = backfill_wsdc_locations_from_editions(
        frame,
        "location",
        editions,
        skip_event_names=frozenset({"Montreal Westie Fest"}),
    )
    assert changed == 0
    assert out.loc[0, "location"] == "Montreal, Canada"


def test_backfill_empty_skip_set_is_honored():
    """Explicit empty frozenset must not fall back to default override skips."""
    editions = pd.DataFrame(
        [
            {
                "event_id": 178,
                "event_year": 2011,
                "event_month": 10,
                "location_raw": "Jeju, Republic of Korea",
            }
        ]
    )
    frame = pd.DataFrame(
        [
            {
                "id": 178,
                "name": "Montreal Westie Fest",
                "event_year": 2011,
                "event_month": 10,
                "location": "Montreal, Canada",
            }
        ]
    )
    out, changed = backfill_wsdc_locations_from_editions(
        frame,
        "location",
        editions,
        skip_event_names=frozenset(),
    )
    assert changed == 1
    assert out.loc[0, "location"] == "Jeju, Republic of Korea"


def test_backfill_default_skips_year_override_names():
    """Year-scoped override names are skipped by default (None)."""
    editions = pd.DataFrame(
        [
            {
                "event_id": 306,
                "event_year": 2019,
                "event_month": 1,
                "location_raw": "Wrong City, Somewhere",
            }
        ]
    )
    frame = pd.DataFrame(
        [
            {
                "id": 306,
                "name": "Go West SwingFest",
                "event_year": 2019,
                "event_month": 1,
                "location": "Fremantle, Australia",
            }
        ]
    )
    out, changed = backfill_wsdc_locations_from_editions(frame, "location", editions)
    assert changed == 0
    assert out.loc[0, "location"] == "Fremantle, Australia"


def test_sync_export_does_not_undo_override_on_events_wsdc(tmp_path):
    """normalize_export_location_columns must not restore Jeju from stale editions."""
    location_info = pd.DataFrame(
        [
            {
                "location_id": 86,
                "event_city": "Montreal",
                "event_state": "",
                "event_country": "Canada",
                "event_location": "Montreal, Canada",
            },
            {
                "location_id": 213,
                "event_city": "Jeju",
                "event_state": "",
                "event_country": "Republic of Korea",
                "event_location": "Jeju, Republic of Korea",
            },
        ]
    )
    location_info.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "event_id": 178,
                "event_year": 2011,
                "event_month": 10,
                "location_id": 213,
                "place_city": "Jeju",
                "location_raw": "Jeju, Republic of Korea",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)
    events_wsdc = pd.DataFrame(
        [
            {
                "id": 178,
                "name": "Montreal Westie Fest",
                "event_year": 2011,
                "event_month": 10,
                "location": "Montreal, Canada",
            }
        ]
    )
    events_wsdc.to_csv(tmp_path / "events_wsdc.csv", index=False)

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "events_wsdc.csv")
    assert out.loc[0, "location"] == "Montreal, Canada"
