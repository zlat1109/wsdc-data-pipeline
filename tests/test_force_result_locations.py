"""Tests for force_result_locations_from_event_name_overrides."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from transform.knowledge.apply import force_result_locations_from_event_name_overrides


def _make_location_df(location_id: str, city: str, country: str, raw: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "location_id": location_id,
                "event_city": city,
                "event_state": "",
                "event_country": country,
                "event_location": raw,
                "event_location_standardized": "",
                "latitude": "",
                "longitude": "",
                "coordinates_valid": "",
            }
        ]
    )


def _make_results_df(event_name: str, location_id: str, event_location: str) -> pd.DataFrame:
    return pd.DataFrame(
        [{"event_name": event_name, "location_id": location_id, "event_location": event_location}]
    )


class TestForceResultLocations:
    def test_applies_override_when_location_exists(self, monkeypatch):
        """When target location is in location_df, rows get corrected ids."""
        overrides = {"Sydney Open": "Sydney, Australia"}
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
        )
        location_df = _make_location_df("117", "Sydney", "Australia", "Sydney, Australia")
        results_df = _make_results_df("Sydney Open", "999", "Amsterdam, Netherlands")

        out, changed = force_result_locations_from_event_name_overrides(results_df, location_df)

        assert changed == 1
        assert out.loc[0, "location_id"] == "117"
        assert out.loc[0, "event_location"] == "Sydney, Australia"

    def test_silent_skip_emits_warning_when_location_missing(self, monkeypatch, caplog):
        """When target location is NOT in location_df, override is skipped with a warning."""
        overrides = {"Nonexistent Open": "Brand New City, Fantasyland"}
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
        )
        location_df = _make_location_df("1", "Sydney", "Australia", "Sydney, Australia")
        results_df = _make_results_df("Nonexistent Open", "999", "Sydney, Australia")

        with caplog.at_level(logging.WARNING, logger="transform.knowledge.apply"):
            out, changed = force_result_locations_from_event_name_overrides(results_df, location_df)

        assert changed == 0
        assert out.loc[0, "location_id"] == "999", "location_id must not change on skip"
        assert any("override skipped" in r.message for r in caplog.records), (
            "Expected a warning about skipped override, got: "
            + str([r.message for r in caplog.records])
        )

    def test_no_change_when_already_correct(self, monkeypatch):
        """Rows already at the correct location_id are counted as unchanged."""
        overrides = {"Sydney Open": "Sydney, Australia"}
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
        )
        location_df = _make_location_df("117", "Sydney", "Australia", "Sydney, Australia")
        results_df = _make_results_df("Sydney Open", "117", "Sydney, Australia")

        _, changed = force_result_locations_from_event_name_overrides(results_df, location_df)

        assert changed == 0

    def test_empty_results_returns_zero(self, monkeypatch):
        overrides = {"Sydney Open": "Sydney, Australia"}
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
        )
        location_df = _make_location_df("117", "Sydney", "Australia", "Sydney, Australia")
        results_df = pd.DataFrame(columns=["event_name", "location_id", "event_location"])

        _, changed = force_result_locations_from_event_name_overrides(results_df, location_df)
        assert changed == 0

    def test_empty_location_df_returns_unchanged(self, monkeypatch):
        overrides = {"Sydney Open": "Sydney, Australia"}
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
        )
        location_df = pd.DataFrame(
            columns=["location_id", "event_city", "event_state", "event_country",
                     "event_location", "event_location_standardized",
                     "latitude", "longitude", "coordinates_valid"]
        )
        results_df = _make_results_df("Sydney Open", "999", "Amsterdam, Netherlands")

        _, changed = force_result_locations_from_event_name_overrides(results_df, location_df)
        assert changed == 0
