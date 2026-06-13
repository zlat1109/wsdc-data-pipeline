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
            url_norm="swingfling.com",
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
    assert result.location_flag in ("ok", "site_differs_from_history")


def test_fuzzy_rejects_different_event_same_substring_name():
    catalog = [
        CatalogEvent(
            event_id=340,
            name="Spooky Westie Weekend",
            url="https://spookywestieweekend.com/",
            url_norm="spookywestieweekend.com",
            typical_location="Singapore, Singapore, Singapore",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "Westie Weekend",
        "start_date": "2027-05-07",
        "location_raw": "Washington DC, MD, United States",
        "url": "https://dancejamproductions.com/westieweekend/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "new"
    assert result.canonical_event_id is None


def test_exact_name_fuzzy_allows_venue_move():
    catalog = [
        CatalogEvent(
            event_id=338,
            name="Sea Dance Fest",
            url="https://vk.com/seadancefest",
            url_norm="vk.com/seadancefest",
            typical_location="Moscow, Moscow region, Russia",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "Sea Dance Fest",
        "start_date": "2026-09-11",
        "location_raw": "Istra, Moscow oblast, Russia",
        "url": "",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.location_flag == "site_differs_from_history"


def test_santa_swing_url_match_with_www():
    from transform.events_list_normalize import normalize_url

    assert normalize_url("https://www.santaswing.pl/") == normalize_url("http://santaswing.pl")
