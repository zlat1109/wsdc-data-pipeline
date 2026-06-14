"""Tests for WSDC Events List date parsing and normalization."""

from parser.events_list_dates import parse_date_range
from transform.events_list_normalize import (
    REGISTRY_STATUS,
    TRIAL_STATUS,
    VALID_STATUS_EVENTS,
    canonical_status_event,
    clean_event_name,
    source_fingerprint,
)


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


def test_clean_list_location():
    from transform.events_list_maps import clean_list_location

    assert clean_list_location("Milan,, Italy") == "Milan, Italy"
    assert "Fort Lauderdale" in clean_list_location("Ft. Lauderdale, FL, United States")
    assert clean_list_location("Albany, NY, Albany") == "Albany, NY, United States"
    assert clean_list_location("San antonio, Texas, United states") == "San Antonio, TX, United States"


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
    assert ev["country"] == "United States"


def test_country_from_location_when_flag_missing():
    from transform.events_list_maps import country_from_location
    from transform.events_list_normalize import normalize_event

    assert country_from_location("Moscow, Russia") == "Russia"
    assert country_from_location("Sofia, Bulgaria") == "Bulgaria"
    assert country_from_location("Bucharest, Romania") == "Romania"

    ev = normalize_event(
        {
            "event_name": "Grand Party Sofia (GPS)",
            "event_type_raw": "Registry Event",
            "start_date": "2026-08-14",
            "end_date": "2026-08-17",
            "original_date": "Aug 14 - 17, 2026",
            "location_raw": "Sofia, Bulgaria",
            "url": "https://wcs-gps.com/",
            "country_flag": "",
            "canceled": False,
            "on_hiatus": False,
        }
    )
    assert ev["country"] == "Bulgaria"
    assert ev["country_flag"] == "BGR"


def test_transparent_flag_treated_as_missing():
    from transform.events_list_normalize import resolve_country_fields

    country, flag = resolve_country_fields("transparent", "Moscow, Russia")
    assert country == "Russia"
    assert flag == "RUS"


def test_country_flag_backfilled_from_location():
    from transform.events_list_normalize import normalize_event

    ev = normalize_event(
        {
            "event_name": "Sea Dance Fest",
            "event_type_raw": "Registry Event",
            "start_date": "2026-09-11",
            "end_date": "2026-09-13",
            "original_date": "Sep 11 - 13, 2026",
            "location_raw": "Moscow, Moscow region, Russia",
            "url": "https://vk.com/seadancefest",
            "country_flag": "",
            "canceled": False,
            "on_hiatus": False,
        }
    )
    assert ev["country"] == "Russia"
    assert ev["country_flag"] == "RUS"


def test_canonical_status_event():
    assert canonical_status_event("") == REGISTRY_STATUS
    assert canonical_status_event("Registry Event") == REGISTRY_STATUS
    assert canonical_status_event("Trial Event") == TRIAL_STATUS
    assert canonical_status_event("trial") == TRIAL_STATUS
    assert canonical_status_event("Some Event", "Trial Event") == TRIAL_STATUS


def test_clean_event_name_defaults_registry_when_type_missing():
    name, status, _, _ = clean_event_name("Warsaw Halloween Swing")
    assert name == "Warsaw Halloween Swing"
    assert status == REGISTRY_STATUS


def test_all_current_events_have_status_event():
    import json
    from pathlib import Path

    from transform.events_list_normalize import normalize_event

    raw = json.loads((Path(__file__).resolve().parents[1] / "data/events_list/current.json").read_text())
    missing = []
    for row in raw["events"]:
        ev = normalize_event(
            {
                **row,
                "event_type_raw": row.get("status_event") or "",
            }
        )
        if ev["status_event"] not in VALID_STATUS_EVENTS:
            missing.append((ev["event_name"], ev["status_event"]))
    assert missing == [], missing


def test_all_current_events_have_country_and_flag():
    import json
    from pathlib import Path

    from transform.events_list_normalize import normalize_event

    raw = json.loads((Path(__file__).resolve().parents[1] / "data/events_list/current.json").read_text())
    missing = []
    for row in raw["events"]:
        ev = normalize_event(
            {
                **row,
                "event_type_raw": row.get("status_event") or "",
            }
        )
        if not ev["country"] or not ev["country_flag"]:
            missing.append(ev["event_name"])
    assert missing == [], missing


def test_dedupe_same_event_prefers_valid_url():
    from transform.events_list_normalize import normalize_events

    raw = [
        {
            "event_name": "Sea Dance Fest",
            "event_type_raw": "Registry Event",
            "start_date": "2026-09-11",
            "end_date": "2026-09-13",
            "original_date": "Sep 11 - 13, 2026",
            "location_raw": "Istra, Moscow oblast, Russia",
            "url": "https://",
            "country_flag": "",
            "canceled": False,
            "on_hiatus": False,
        },
        {
            "event_name": "Sea Dance Fest",
            "event_type_raw": "Registry Event",
            "start_date": "2026-09-11",
            "end_date": "2026-09-13",
            "original_date": "Sep 11 - 13, 2026",
            "location_raw": "Moscow, Moscow region, Russia",
            "url": "https://vk.com/seadancefest",
            "country_flag": "",
            "canceled": False,
            "on_hiatus": False,
        },
    ]
    out = normalize_events(raw)
    assert len(out) == 1
    assert "vk.com" in out[0]["url"]
    assert out[0]["country"] == "Russia"
    assert out[0]["country_flag"] == "RUS"


def test_fingerprint_stable():
    fp1 = source_fingerprint("Test Event", "2026-06-01", "https://example.com/event/")
    fp2 = source_fingerprint("Test Event", "2026-06-01", "https://example.com/event")
    assert fp1 == fp2


def test_fingerprint_differs_by_date():
    fp1 = source_fingerprint("Annual Event", "2026-06-01", "https://example.com/event")
    fp2 = source_fingerprint("Annual Event", "2027-06-01", "https://example.com/event")
    assert fp1 != fp2
