"""Tests for events list mapping."""

from transform.events_list_mapping import CatalogEvent, map_scheduled_event, build_url_index


def test_url_match_rejected_when_name_differs():
    catalog = [
        CatalogEvent(
            event_id=1,
            name="Swedish Swing Summer Camp",
            url="http://www.uptownswing.se",
            url_norm="uptownswing.se",
            typical_location="Stockholm, Sweden",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "Totally Different Brand",
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


def test_westie_weekend_maps_to_dance_jam_catalog():
    catalog = [
        CatalogEvent(
            event_id=372,
            name="Dance Jam Jack & Jill Weekend",
            url="http://www.dancejamproductions.com",
            url_norm="dancejamproductions.com",
            typical_location="Washington DC, MD, USA",
        ),
        CatalogEvent(
            event_id=340,
            name="Spooky Westie Weekend",
            url="https://spookywestieweekend.com/",
            url_norm="spookywestieweekend.com",
            typical_location="Singapore, Singapore, Singapore",
        ),
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
    assert result.match_status == "confirmed"
    assert result.match_method == "explicit"
    assert result.canonical_name == "Dance Jam Jack & Jill Weekend"
    assert result.canonical_event_id == 372


def test_rolling_swing_exact_name_wins_over_wrong_url():
    catalog = [
        CatalogEvent(
            event_id=313,
            name="Rolling Swing",
            url="http://www.rollingswing.com",
            url_norm="rollingswing.com",
            typical_location="LYON, Rhone, France",
        ),
        CatalogEvent(
            event_id=270,
            name="Westie's Angels",
            url="http://www.frenchywesty.com",
            url_norm="frenchywesty.com",
            typical_location="LYON, Rhone, France",
        ),
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "Rolling Swing",
        "start_date": "2026-08-27",
        "location_raw": "LYON, Rhone, France",
        "url": "http://www.frenchywesty.com/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.match_method == "exact_name"
    assert result.canonical_event_id == 313


def test_baroqueswing_maps_to_barock_ludwigsburg():
    catalog = [
        CatalogEvent(
            event_id=374,
            name="Barock Swing Ludwigsburg",
            url="https://lb-barockswing.com/index.php",
            url_norm="lb-barockswing.com/index.php",
            typical_location="Ludwigsburg, Baden-Württemberg, Deutschland",
        )
    ]
    row = {
        "source_fingerprint": "x",
        "event_name": "BaroqueSwing",
        "start_date": "2026-06-25",
        "location_raw": "Ludwigsburg, Baden-Württemberg, Deutschland",
        "url": "https://baroqueswing.com/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.match_method == "explicit"
    assert result.canonical_name == "Barock Swing Ludwigsburg"
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


def test_scandinavian_open_maps_by_url_when_catalog_supplemented():
    from transform.events_list_catalog import _supplement_catalog
    from transform.events_list_normalize import normalize_url

    events = _supplement_catalog([])
    catalog = [
        CatalogEvent(
            event_id=eid,
            name=name,
            url=url,
            url_norm=normalize_url(url),
            typical_location="Stockholm, Sweden",
        )
        for eid, name, url in events
    ]
    row = {
        "source_fingerprint": "snow",
        "event_name": 'Scandinavian Open WCS "SNOW"',
        "start_date": "2026-10-28",
        "location_raw": "Stockholm, Sweden, Sweden",
        "url": "http://www.snowcs.se/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.canonical_event_id == 229
    assert result.canonical_name == "Scandinavian Open"


def test_calgary_town_open_maps_to_bto_open():
    catalog = [
        CatalogEvent(
            event_id=324,
            name="BTO Open",
            url="https://ctodance.ca/",
            url_norm="ctodance.ca",
            typical_location="Calgary, Alberta, Canada",
        ),
    ]
    row = {
        "source_fingerprint": "cto",
        "event_name": "Calgary Town Open",
        "start_date": "2026-09-24",
        "location_raw": "Calgary, Alberta, Canada",
        "url": "https://ctodance.ca/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.canonical_event_id == 324
    assert result.canonical_name == "BTO Open"


def test_rocket_city_maps_to_westies_on_the_water_rebrand():
    catalog = [
        CatalogEvent(
            event_id=323,
            name="Westies on the Water",
            url="http://westiesonthewater.com/",
            url_norm="westiesonthewater.com",
            typical_location="Huntsville, AL",
        ),
    ]
    row = {
        "source_fingerprint": "rocket",
        "event_name": "Rocket City Swing",
        "start_date": "2026-11-19",
        "location_raw": "Huntsville, Alabama, United States",
        "url": "http://rocketcityswing.com/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "confirmed"
    assert result.match_method == "explicit"
    assert result.canonical_event_id == 323
    assert result.canonical_name == "Westies on the Water"


def test_rocket_city_not_fuzzy_matched_to_rose_city():
    """Different US events — similar names must not link when cities differ."""
    catalog = [
        CatalogEvent(
            event_id=244,
            name="Rose City Swing",
            url="https://rosecityswing.com",
            url_norm="rosecityswing.com",
            typical_location="Portland, OR, United States",
        ),
    ]
    row = {
        "source_fingerprint": "rocket",
        "event_name": "Rocket City Swing",
        "start_date": "2026-11-19",
        "location_raw": "Huntsville, Alabama, United States",
        "url": "http://rocketcityswing.com/",
        "status_event": "Registry Event",
        "is_active": True,
    }
    result = map_scheduled_event(row, catalog, build_url_index(catalog), [c.name for c in catalog])
    assert result.match_status == "new"
    assert result.canonical_event_id is None

