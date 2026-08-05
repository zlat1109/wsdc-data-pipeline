"""Tests for forced EVENT_NAME_LOCATION_OVERRIDES location_id remaps."""

import pandas as pd

from transform.knowledge.apply import force_result_locations_from_event_name_overrides


def test_force_sweden_westie_gala_off_wailea():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "124",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
            {
                "location_id": "199",
                "event_city": "Stockholm",
                "event_state": "",
                "event_country": "Sweden",
                "event_location": "Stockholm, Sweden",
            },
            {
                "location_id": "355",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Sweden Westie Gala",
                "location_id": "124",
                "event_location": "Wailea, HI, United States",
            },
            {
                "event_name": "The Aloha Open",
                "location_id": "124",
                "event_location": "Wailea, HI, United States",
            },
            {
                "event_name": "Swedish Swing Summer Camp",
                "location_id": "124",
                "event_location": "",
            },
        ]
    )

    out, changed = force_result_locations_from_event_name_overrides(results, location_info)

    assert changed == 2
    sweden = out.loc[out["event_name"] == "Sweden Westie Gala"].iloc[0]
    assert str(sweden["location_id"]) == "199"
    assert sweden["event_location"] == "Stockholm, Sweden"

    camp = out.loc[out["event_name"] == "Swedish Swing Summer Camp"].iloc[0]
    assert str(camp["location_id"]) == "199"
    assert camp["event_location"] == "Stockholm, Sweden"

    # Aloha Open must keep Wailea — do not rewrite shared location_id geography.
    aloha = out.loc[out["event_name"] == "The Aloha Open"].iloc[0]
    assert str(aloha["location_id"]) == "124"


def test_force_french_connection_to_annecy():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "13",
                "event_city": "Washington",
                "event_state": "District of Columbia",
                "event_country": "United States",
                "event_location": "Washington, DC, United States",
            },
            {
                "location_id": "188",
                "event_city": "Annecy",
                "event_state": "",
                "event_country": "France",
                "event_location": "Annecy, France",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "FRENCH CONNECTION WCS",
                "location_id": "13",
                "event_location": "Washington, DC, United States",
            }
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    assert str(out.loc[0, "location_id"]) == "188"
    assert out.loc[0, "event_location"] == "Annecy, France"


def test_force_baltic_swing_off_phoenix():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "3",
                "event_city": "Phoenix",
                "event_state": "Arizona",
                "event_country": "United States",
                "event_location": "Phoenix, AZ, United States",
            },
            {
                "location_id": "186",
                "event_city": "Gdańsk",
                "event_state": "",
                "event_country": "Poland",
                "event_location": "Gdańsk, Poland",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Baltic Swing",
                "location_id": "3",
                "event_location": "Phoenix, AZ, United States",
            },
            {
                "event_name": "Desert City Swing",
                "location_id": "3",
                "event_location": "Phoenix, AZ, United States",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    baltic = out.loc[out["event_name"] == "Baltic Swing"].iloc[0]
    assert str(baltic["location_id"]) == "186"
    assert baltic["event_location"] == "Gdańsk, Poland"
    desert = out.loc[out["event_name"] == "Desert City Swing"].iloc[0]
    assert str(desert["location_id"]) == "3"


def test_force_freedom_swing_off_venray():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "227",
                "event_city": "Venray",
                "event_state": "",
                "event_country": "Netherlands",
                "event_location": "Venray, Netherlands",
            },
            {
                "location_id": "66",
                "event_city": "Wilmington",
                "event_state": "Delaware",
                "event_country": "United States",
                "event_location": "Wilmington, DE, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Freedom Swing Dance Challenge",
                "location_id": "227",
                "event_location": "Venray, Netherlands",
            },
            {
                "event_name": "Dutch Open West Coast Swing",
                "location_id": "227",
                "event_location": "Venray, Netherlands",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    freedom = out.loc[out["event_name"] == "Freedom Swing Dance Challenge"].iloc[0]
    assert str(freedom["location_id"]) == "66"
    assert freedom["event_location"] == "Wilmington, DE, United States"
    dutch = out.loc[out["event_name"] == "Dutch Open West Coast Swing"].iloc[0]
    assert str(dutch["location_id"]) == "227"


def test_force_west_in_lyon_and_aloha_open():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "222",
                "event_city": "St. Petersburg",
                "event_state": "",
                "event_country": "Russia",
                "event_location": "St. Petersburg, Russia",
            },
            {
                "location_id": "156",
                "event_city": "Lyon",
                "event_state": "",
                "event_country": "France",
                "event_location": "Lyon, France",
            },
            {
                "location_id": "213",
                "event_city": "Jeju",
                "event_state": "",
                "event_country": "Republic of Korea",
                "event_location": "Jeju, Republic of Korea",
            },
            {
                "location_id": "124",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "West in Lyon",
                "location_id": "222",
                "event_location": "St. Petersburg, Russia",
            },
            {
                "event_name": "The Aloha Open",
                "location_id": "213",
                "event_location": "Jeju, Republic of Korea",
            },
            {
                "event_name": "Swing & Snow",
                "location_id": "222",
                "event_location": "St. Petersburg, Russia",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 2
    assert str(out.loc[out.event_name == "West in Lyon", "location_id"].iloc[0]) == "156"
    assert str(out.loc[out.event_name == "The Aloha Open", "location_id"].iloc[0]) == "124"
    assert str(out.loc[out.event_name == "Swing & Snow", "location_id"].iloc[0]) == "222"


def test_force_sea_dance_fest_and_med_in_swing():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "127",
                "event_city": "Düsseldorf",
                "event_state": "",
                "event_country": "Germany",
                "event_location": "Düsseldorf, Germany",
            },
            {
                "location_id": "113",
                "event_city": "Moscow",
                "event_state": "",
                "event_country": "Russia",
                "event_location": "Moscow, Russia",
            },
            {
                "location_id": "3",
                "event_city": "Phoenix",
                "event_state": "Arizona",
                "event_country": "United States",
                "event_location": "Phoenix, AZ, United States",
            },
            {
                "location_id": "386",
                "event_city": "La Londe-les-Maures",
                "event_state": "",
                "event_country": "France",
                "event_location": "La Londe-les-Maures, France",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Sea Dance Fest",
                "location_id": "127",
                "event_location": "Düsseldorf, Germany",
            },
            {
                "event_name": "Med in Swing",
                "location_id": "3",
                "event_location": "Phoenix, AZ, United States",
            },
            {
                "event_name": "4TH of July Convention",
                "location_id": "3",
                "event_location": "Phoenix, AZ, United States",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 2
    assert str(out.loc[out.event_name == "Sea Dance Fest", "location_id"].iloc[0]) == "113"
    assert str(out.loc[out.event_name == "Med in Swing", "location_id"].iloc[0]) == "386"
    assert str(out.loc[out.event_name == "4TH of July Convention", "location_id"].iloc[0]) == "3"


def test_force_berlin_events_off_brno_and_saunaswing_off_wailea():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "266",
                "event_city": "Brno",
                "event_state": "",
                "event_country": "Czech Republic",
                "event_location": "Brno, Czech Republic",
            },
            {
                "location_id": "194",
                "event_city": "Berlin",
                "event_state": "",
                "event_country": "Germany",
                "event_location": "Berlin, Germany",
            },
            {
                "location_id": "124",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
            {
                "location_id": "268",
                "event_city": "Ikaalinen",
                "event_state": "",
                "event_country": "Finland",
                "event_location": "Ikaalinen, Finland",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "SwingLab Berlin",
                "location_id": "266",
                "event_location": "Brno, Czech Republic",
            },
            {
                "event_name": "Berlin Swing Revolution",
                "location_id": "266",
                "event_location": "Brno, Czech Republic",
            },
            {
                "event_name": "Swing Fiction",
                "location_id": "266",
                "event_location": "Brno, Czech Republic",
            },
            {
                "event_name": "SaunaSwing",
                "location_id": "124",
                "event_location": "Wailea, HI, United States",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 3
    assert str(out.loc[out.event_name == "SwingLab Berlin", "location_id"].iloc[0]) == "194"
    assert str(out.loc[out.event_name == "Berlin Swing Revolution", "location_id"].iloc[0]) == "194"
    assert str(out.loc[out.event_name == "Swing Fiction", "location_id"].iloc[0]) == "266"
    assert str(out.loc[out.event_name == "SaunaSwing", "location_id"].iloc[0]) == "268"
    assert out.loc[out.event_name == "SaunaSwing", "event_location"].iloc[0] == "Ikaalinen, Finland"


def test_force_swing_fling_and_dcsx_to_herndon():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "13",
                "event_city": "Washington",
                "event_state": "District of Columbia",
                "event_country": "United States",
                "event_location": "Washington, DC, United States",
            },
            {
                "location_id": "38",
                "event_city": "Herndon",
                "event_state": "Virginia",
                "event_country": "United States",
                "event_location": "Herndon, VA, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Swing Fling",
                "location_id": "13",
                "event_location": "Washington, DC, United States",
            },
            {
                "event_name": "DC Swing eXperience (DCSX)",
                "location_id": "13",
                "event_location": "Washington, DC, United States",
            },
            {
                "event_name": "Mid-Atlantic Dance Jam",
                "location_id": "13",
                "event_location": "Washington, DC, United States",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 2
    assert str(out.loc[out.event_name == "Swing Fling", "location_id"].iloc[0]) == "38"
    assert str(out.loc[out.event_name == "DC Swing eXperience (DCSX)", "location_id"].iloc[0]) == "38"
    # MADjam stays on Washington DC — no override.
    assert str(out.loc[out.event_name == "Mid-Atlantic Dance Jam", "location_id"].iloc[0]) == "13"


def test_force_philly_swing_classic_to_wilmington():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "7",
                "event_city": "New York",
                "event_state": "New York",
                "event_country": "United States",
                "event_location": "New York, NY, United States",
            },
            {
                "location_id": "66",
                "event_city": "Wilmington",
                "event_state": "Delaware",
                "event_country": "United States",
                "event_location": "Wilmington, DE, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Philly Swing Classic",
                "location_id": "7",
                "event_location": "New York, NY, United States",
            },
            {
                "event_name": "American Swing Dance Championships",
                "location_id": "7",
                "event_location": "New York, NY, United States",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    philly = out.loc[out["event_name"] == "Philly Swing Classic"].iloc[0]
    assert str(philly["location_id"]) == "66"
    assert philly["event_location"] == "Wilmington, DE, United States"
    # NY event on shared lid must stay New York.
    nyc = out.loc[out["event_name"] == "American Swing Dance Championships"].iloc[0]
    assert str(nyc["location_id"]) == "7"


def test_force_swingsation_off_st_petersburg_to_gold_coast():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "222",
                "event_city": "St. Petersburg",
                "event_state": "",
                "event_country": "Russia",
                "event_location": "St. Petersburg, Russia",
            },
            {
                "location_id": "169",
                "event_city": "Gold Coast",
                "event_state": "",
                "event_country": "Australia",
                "event_location": "Gold Coast, Australia",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Swingsation",
                "location_id": "222",
                "event_location": "St. Petersburg, Russia",
            },
            {
                "event_name": "Swing & Snow",
                "location_id": "222",
                "event_location": "St. Petersburg, Russia",
            },
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    swing = out.loc[out["event_name"] == "Swingsation"].iloc[0]
    assert str(swing["location_id"]) == "169"
    assert swing["event_location"] == "Gold Coast, Australia"
    snow = out.loc[out["event_name"] == "Swing & Snow"].iloc[0]
    assert str(snow["location_id"]) == "222"
