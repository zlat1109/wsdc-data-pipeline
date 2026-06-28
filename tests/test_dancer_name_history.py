"""Tests for dancer name normalization and legacy history split."""

from __future__ import annotations

import pandas as pd

from transform.history.legacy_role_split import build_division_intervals, build_name_intervals
from transform.normalize import normalize_dancer_name


def test_normalize_dancer_name_collapses_whitespace():
    assert normalize_dancer_name("  Jane   Doe  ") == "Jane Doe"
    assert normalize_dancer_name("\tJohn\tSmith") == "John Smith"
    assert normalize_dancer_name("") is None
    assert normalize_dancer_name(None) is None


def test_name_only_change_goes_to_name_intervals(tmp_path):
    csv_path = tmp_path / "changed.csv"
    pd.DataFrame(
        [
            {
                "dancer_id": "100",
                "dancer_name": "Alice Smith",
                "dominate_role": "Follower",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Leader",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-01-01",
            },
            {
                "dancer_id": "100",
                "dancer_name": "Alice Jones",
                "dominate_role": "Follower",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Leader",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-06-01",
            },
        ]
    ).to_csv(csv_path, index=False)

    divisions = build_division_intervals(csv_path)
    names = build_name_intervals(csv_path)

    assert len(divisions) == 1
    assert divisions.iloc[0]["valid_from"] == "2025-01-01"
    assert len(names) == 2
    assert names.iloc[0]["dancer_name"] == "Alice Smith"
    assert names.iloc[1]["dancer_name"] == "Alice Jones"


def test_division_change_without_name_change(tmp_path):
    csv_path = tmp_path / "changed.csv"
    pd.DataFrame(
        [
            {
                "dancer_id": "200",
                "dancer_name": "Bob Lee",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-01-01",
            },
            {
                "dancer_id": "200",
                "dancer_name": "Bob Lee",
                "dominate_role": "Leader",
                "dominate_required": "Intermediate",
                "dominate_allowed": "Intermediate",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-06-01",
            },
        ]
    ).to_csv(csv_path, index=False)

    divisions = build_division_intervals(csv_path)
    names = build_name_intervals(csv_path)

    assert len(divisions) == 2
    assert len(names) == 1
    assert names.iloc[0]["dancer_name"] == "Bob Lee"


def test_case_only_name_change_is_ignored(tmp_path):
    csv_path = tmp_path / "changed.csv"
    pd.DataFrame(
        [
            {
                "dancer_id": "300",
                "dancer_name": "Jane Doe",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-01-01",
            },
            {
                "dancer_id": "300",
                "dancer_name": "JANE DOE",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Newcomer",
                "non_dominate_allowed": "Newcomer",
                "non_dominate_recommended": "Newcomer",
                "non_dominate_role_highest_level_points": "",
                "non_dominate_role_highest_level": "",
                "update_date": "2025-06-01",
            },
        ]
    ).to_csv(csv_path, index=False)

    names = build_name_intervals(csv_path)

    assert len(names) == 1
    assert names.iloc[0]["dancer_name"] == "Jane Doe"
