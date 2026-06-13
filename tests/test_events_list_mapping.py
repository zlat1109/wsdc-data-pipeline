"""Tests for events list mapping."""

from transform.events_list_mapping import CatalogEvent, map_scheduled_event, build_url_index


def test_url_match_rejected_when_name_differs():
    catalog = [
        CatalogEvent(
            event_id=1,
            name="Swedish Swing Summer Camp",
            url="http://www.uptownswing.se",
            url_norm="www.uptownswing.se",
            typical_location="Stockholm, Sweden",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "UpTown Swing",
        "start_date": "2026-08-14",
        "location_raw": "Stockholm, Sweden",
        "url": "http://www.uptownswing.se/",
        "status_event": "",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "new"
    assert result.canonical_event_id is None


def test_url_match_stays_confirmed_when_site_location_differs_from_catalog():
    catalog = [
        CatalogEvent(
            event_id=59,
            name="Swing Fling",
            url="http://www.swingfling.com",
            url_norm="www.swingfling.com",
            typical_location="Washington DC, USA",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "Swing Fling",
        "start_date": "2026-08-06",
        "location_raw": "Washington, DC., VA, United States",
        "url": "http://www.swingfling.com/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.match_method == "url"
    assert result.location_flag == "site_differs_from_history"
