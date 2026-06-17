"""Tests for pre-load CSV validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_pipeline_inputs import validate_pipeline_inputs  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "pipeline"


def _write_minimal_pipeline(tmp_path: Path, *, empty_name_id: str | None = None) -> None:
    role_rows = [
        {
            "dancer_id": "1",
            "dancer_name": "Alice",
            "dominate_role": "Leader",
            "dominate_required": "Novice",
            "dominate_allowed": "Advanced",
            "non_dominate_role": "Follower",
            "non_dominate_required": "",
            "non_dominate_allowed": "",
            "non_dominate_recommended": "",
            "non_dominate_role_highest_level_points": "",
            "non_dominate_role_highest_level": "",
            "update_date": "2026-06-17",
        },
    ]
    if empty_name_id:
        role_rows.append(
            {
                "dancer_id": empty_name_id,
                "dancer_name": "",
                "dominate_role": "Follower",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Leader",
                "non_dominate_required": "",
                "non_dominate_allowed": "",
                "non_dominate_recommended": "",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2026-06-17",
            }
        )

    pd.DataFrame(role_rows).to_csv(tmp_path / "dancer_role_info.csv", index=False)
    pd.DataFrame(
        [
            {
                "dancer_id": "1",
                "role": "leader",
                "dance": "West Coast Swing",
                "level": "Novice",
                "total_points": "10",
                "update_date": "2026-06-17",
            }
        ]
    ).to_csv(tmp_path / "dancers_points_info.csv", index=False)
    pd.DataFrame(
        [
            {
                "dancer_id": "1",
                "event_dance": "West Coast Swing",
                "event_competition": "Novice",
                "event_role": "leader",
                "event_result": "1",
                "event_points": "5",
                "event_name": "Test Event",
                "location_id": "1",
                "event_year": "2026",
                "event_month": "6",
                "event_year_and_month": "2026-06-01",
            }
        ]
    ).to_csv(tmp_path / "dancers_results_info.csv", index=False)
    pd.DataFrame(
        [
            {
                "location_id": "1",
                "event_city": "City",
                "event_state": "ST",
                "event_country": "Country",
                "latitude": "0",
                "longitude": "0",
                "event_location": "City, ST",
                "event_location_standardized": "City, ST",
                "coordinates_valid": "true",
            }
        ]
    ).to_csv(tmp_path / "location_info.csv", index=False)
    pd.DataFrame(
        [
            {
                "id": "1",
                "name": "Test Event",
                "location": "City, ST",
                "url": "http://example.com",
                "date": "June 2026",
                "event_instance_id": "1",
                "parsed_date": "2026-06-01",
                "event_year": "2026",
                "event_month": "6",
            }
        ]
    ).to_csv(tmp_path / "events_wsdc.csv", index=False)


def test_validate_passes_on_minimal_fixture(tmp_path):
    _write_minimal_pipeline(tmp_path)
    report = validate_pipeline_inputs(tmp_path)
    assert report.ok


def test_validate_warns_on_empty_dancer_name(tmp_path):
    _write_minimal_pipeline(tmp_path, empty_name_id="24207")
    report = validate_pipeline_inputs(tmp_path)
    assert report.ok
    assert any("empty name" in w for w in report.warnings)


def test_validate_fails_on_missing_required_csv(tmp_path):
    report = validate_pipeline_inputs(tmp_path)
    assert not report.ok
    assert any("Missing required CSV" in e for e in report.errors)


def test_validate_fails_on_invalid_event_role(tmp_path):
    _write_minimal_pipeline(tmp_path)
    results = pd.read_csv(tmp_path / "dancers_results_info.csv", dtype=str)
    results.loc[0, "event_role"] = "dancer"
    results.to_csv(tmp_path / "dancers_results_info.csv", index=False)
    report = validate_pipeline_inputs(tmp_path)
    assert not report.ok
    assert any("invalid event_role" in e for e in report.errors)
