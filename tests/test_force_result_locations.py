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

    def test_year_scoped_override_beats_wrong_shared_city(self, monkeypatch):
        """Relocating series: early years keep origin city after flat collapse."""
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", {}
        )
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_YEAR_LOCATION_OVERRIDES",
            {
                ("Sunny Side Dance Camp", 2012, 2013): "Crimea, Ukraine",
                ("Sunny Side Dance Camp", 2014, 2099): "Torrevieja, Spain",
            },
        )
        location_df = pd.concat(
            [
                _make_location_df("249", "Crimea", "Ukraine", "Crimea, Ukraine"),
                _make_location_df("248", "Torrevieja", "Spain", "Torrevieja, Spain"),
            ],
            ignore_index=True,
        )
        results_df = pd.DataFrame(
            [
                {
                    "event_name": "Sunny Side Dance Camp",
                    "event_year": 2012,
                    "location_id": "248",
                    "event_location": "Torrevieja, Spain",
                },
                {
                    "event_name": "Sunny Side Dance Camp",
                    "event_year": 2015,
                    "location_id": "248",
                    "event_location": "Torrevieja, Spain",
                },
            ]
        )

        out, changed = force_result_locations_from_event_name_overrides(
            results_df, location_df
        )

        assert changed == 1
        assert out.loc[0, "location_id"] == "249"
        assert out.loc[0, "event_location"] == "Crimea, Ukraine"
        assert out.loc[1, "location_id"] == "248"

    def test_go_west_year_scoped_fremantle_vs_perth(self, monkeypatch):
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", {}
        )
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_YEAR_LOCATION_OVERRIDES",
            {
                ("Go West SwingFest", 2019, 2019): "Fremantle, Australia",
                ("Go West SwingFest", 2024, 2099): "Perth, Australia",
            },
        )
        location_df = pd.concat(
            [
                _make_location_df("240", "Fremantle", "Australia", "Fremantle, Australia"),
                _make_location_df("253", "Perth", "Australia", "Perth, Australia"),
            ],
            ignore_index=True,
        )
        results_df = pd.DataFrame(
            [
                {
                    "event_name": "Go West SwingFest",
                    "event_year": 2019,
                    "location_id": "253",
                    "event_location": "Perth, Australia",
                },
                {
                    "event_name": "Go West SwingFest",
                    "event_year": 2024,
                    "location_id": "253",
                    "event_location": "Perth, Australia",
                },
            ]
        )

        out, changed = force_result_locations_from_event_name_overrides(
            results_df, location_df
        )

        assert changed == 1
        assert out.loc[0, "location_id"] == "240"
        assert out.loc[0, "event_location"] == "Fremantle, Australia"
        assert out.loc[1, "location_id"] == "253"

    def test_warns_when_year_override_name_missing_event_year(
        self, monkeypatch, caplog
    ):
        import logging

        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", {}
        )
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_YEAR_LOCATION_OVERRIDES",
            {("Sunny Side Dance Camp", 2012, 2013): "Crimea, Ukraine"},
        )
        location_df = _make_location_df("249", "Crimea", "Ukraine", "Crimea, Ukraine")
        results_df = pd.DataFrame(
            [
                {
                    "event_name": "Sunny Side Dance Camp",
                    "event_year": None,
                    "location_id": "248",
                    "event_location": "Torrevieja, Spain",
                }
            ]
        )

        with caplog.at_level(logging.WARNING):
            out, changed = force_result_locations_from_event_name_overrides(
                results_df, location_df
            )

        assert changed == 0
        assert out.loc[0, "location_id"] == "248"
        assert "null event_year" in caplog.text

    def test_ggp_year_scoped_paris_from_2026_keeps_toulouse(self, monkeypatch):
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", {}
        )
        monkeypatch.setattr(
            "transform.knowledge.apply.EVENT_NAME_YEAR_LOCATION_OVERRIDES",
            {
                ("Global Grand Prix - West Coast Swing Reunion", 2026, 2099): "Paris, France",
            },
        )
        location_df = pd.concat(
            [
                _make_location_df("208", "Toulouse", "France", "Toulouse, France"),
                _make_location_df("109", "Paris", "France", "Paris, France"),
            ],
            ignore_index=True,
        )
        results_df = pd.DataFrame(
            [
                {
                    "event_name": "Global Grand Prix - West Coast Swing Reunion",
                    "event_year": 2025,
                    "location_id": "208",
                    "event_location": "Toulouse, France",
                },
                {
                    "event_name": "Global Grand Prix - West Coast Swing Reunion",
                    "event_year": 2026,
                    "location_id": "208",
                    "event_location": "Toulouse, France",
                },
            ]
        )

        out, changed = force_result_locations_from_event_name_overrides(
            results_df, location_df
        )

        assert changed == 1
        assert out.loc[0, "location_id"] == "208"
        assert out.loc[1, "location_id"] == "109"
        assert out.loc[1, "event_location"] == "Paris, France"
