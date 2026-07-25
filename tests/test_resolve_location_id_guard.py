"""Guards for stable location_id assignment in resolve_result_location_ids."""

import pandas as pd
import pytest

from transform.geography.resolve import resolve_result_location_ids


def test_next_id_uses_max_of_results_when_location_info_partial():
    """New places continue after max(results.location_id), not restart at 1."""
    locations = pd.DataFrame(
        [
            {
                "location_id": "10",
                "event_location": "Known City, CA, United States",
                "event_city": "Known City",
                "event_state": "CA",
                "event_country": "United States",
                "latitude": "",
                "longitude": "",
                "event_location_standardized": "",
                "coordinates_valid": "",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {
                "location_id": "500",
                "event_location": "Known City, CA, United States",
            },
            {
                "location_id": "",
                "event_location": "Brand New Town, TX, United States",
            },
        ]
    )
    out_results, out_locations = resolve_result_location_ids(results, locations)
    new_id = out_results.loc[1, "location_id"]
    assert int(new_id) == 501
    assert "501" in set(out_locations["location_id"].astype(str))


def test_refuse_empty_location_info_when_results_have_ids():
    locations = pd.DataFrame(
        columns=[
            "location_id",
            "event_location",
            "event_city",
            "event_state",
            "event_country",
            "latitude",
            "longitude",
            "event_location_standardized",
            "coordinates_valid",
        ]
    )
    results = pd.DataFrame(
        [
            {"location_id": "42", "event_location": "Somewhere, CA, United States"},
            {"location_id": "", "event_location": "Elsewhere, NY, United States"},
        ]
    )
    with pytest.raises(RuntimeError, match="refusing to invent location rows"):
        resolve_result_location_ids(results, locations)
