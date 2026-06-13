"""Tests for WSDC Events List date parsing and normalization."""

from parser.events_list_dates import parse_date_range
from transform.events_list_normalize import clean_event_name, source_fingerprint


def test_parse_date_range_single_month():
    start, end = parse_date_range("Jun 11 - 15, 2026")
    assert start.isoformat() == "2026-06-11"
    assert end.isoformat() == "2026-06-15"


def test_parse_date_range_cross_year():
    start, end = parse_date_range("Dec 28 2023 - Jan 1 2024")
    assert start.isoformat() == "2023-12-28"
    assert end.isoformat() == "2024-01-01"


def test_clean_event_name_from_type_div():
    name, status, confirmed, hiatus = clean_event_name("Baltic Swing", "Registry Event")
    assert name == "Baltic Swing"
    assert status == "Registry Event"
    assert confirmed is True


def test_clean_event_name_trial():
    name, status, _, _ = clean_event_name("Milan Swing Vibes", "Trial Event")
    assert name == "Milan Swing Vibes"
    assert status == "Trial Event"


def test_clean_event_name_legacy_suffix():
    name, status, confirmed, _ = clean_event_name("Baltic Swing Registry Event (Unconfirmed)")
    assert name == "Baltic Swing"
    assert status == "Registry Event"
    assert confirmed is False


def test_clean_event_name_unconfirmed_from_type_div():
    name, status, confirmed, _ = clean_event_name(
        "Baltic Swing (Unconfirmed)", "Registry Event"
    )
    assert name == "Baltic Swing"
    assert status == "Registry Event"
    assert confirmed is False


def test_normalize_list_location():
    from transform.events_list_maps import clean_list_location

    assert clean_list_location("Milan,, Italy") == "Milan, Italy"
    assert "Fort Lauderdale" in clean_list_location("Ft. Lauderdale, FL, United States")


def test_site_location_not_overridden_by_event_name():
    from transform.events_list_normalize import normalize_event

    row = {
        "event_name": "Swing Fling",
        "event_type_raw": "Registry Event",
        "start_date": "2026-08-06",
        "end_date": "2026-08-09",
        "original_date": "Aug 6 - 9, 2026",
        "location_raw": "Washington, DC., VA, USA",
        "url": "http://www.swingfling.com/",
        "country_flag": "USA",
        "canceled": False,
        "on_hiatus": False,
    }
    ev = normalize_event(row)
    assert "Washington" in ev["location_raw"]
    assert "Herndon" not in ev["location_raw"]
    assert ev["location_raw_original"] == "Washington, DC., VA, USA"


def test_fingerprint_stable():
    fp1 = source_fingerprint("Test Event", "2026-06-01", "https://example.com/event/")
    fp2 = source_fingerprint("Test Event", "2026-06-01", "https://example.com/event")
    assert fp1 == fp2


def test_fingerprint_differs_by_date():
    fp1 = source_fingerprint("Annual Event", "2026-06-01", "https://example.com/event")
    fp2 = source_fingerprint("Annual Event", "2027-06-01", "https://example.com/event")
    assert fp1 != fp2
