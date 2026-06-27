"""Tests for derived divisional analytics exports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from export import DERIVED_EXPORTS, OPTIONAL_EXPORTS, build_export_map
from transform.divisional_exports import (
    TRANSITION_COLUMNS,
    _merge_snapshot_aggregates,
    _merge_transitions,
    _previous_full_snapshot_frame,
    build_dancer_transitions_snapshot,
    build_derived_analytics_exports,
    build_divisional_structure,
    load_role_source,
)


def test_derived_export_filenames_are_unique() -> None:
    assert len(DERIVED_EXPORTS) == len(set(DERIVED_EXPORTS))


def test_all_export_filenames_are_unique() -> None:
    view_exports = set(build_export_map(include_results_by_event=True).values())
    optional = set(OPTIONAL_EXPORTS.values())
    derived = set(DERIVED_EXPORTS)
    all_names = view_exports | optional | derived
    assert len(all_names) == len(view_exports) + len(derived)


def test_build_divisional_structure_all_roles() -> None:
    df = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "update_date": "2025-01-03",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Intermediate",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Novice",
                "non_dominate_allowed": "Novice",
            },
            {
                "dancer_id": 2,
                "update_date": "2025-01-03",
                "dominate_role": "Follower",
                "dominate_required": "Advanced",
                "dominate_allowed": "Advanced",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
            },
        ]
    )

    result = build_divisional_structure(df, dominate_only=False)

    assert list(result.columns) == [
        "update_date",
        "division",
        "role",
        "type_options",
        "count_dancer",
    ]
    assert result["count_dancer"].sum() == 6
    assert set(result["type_options"]) == {"allowed", "required"}


def test_build_divisional_structure_dominate_only() -> None:
    df = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "update_date": "2025-01-03",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Intermediate",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Novice",
                "non_dominate_allowed": "Novice",
            }
        ]
    )

    result = build_divisional_structure(df, dominate_only=True)

    assert list(result.columns) == ["update_date", "division", "role", "type", "count_dancer"]
    assert len(result) == 2
    assert "type_options" not in result.columns


def test_previous_full_snapshot_picks_largest_prior_parse() -> None:
    changed = pd.DataFrame(
        [
            {"dancer_id": i, "update_date": "2025-01-01", "dominate_role": "Leader"}
            for i in range(100)
        ]
        + [
            {"dancer_id": i, "update_date": "2025-01-08", "dominate_role": "Leader"}
            for i in range(5)
        ]
        + [
            {"dancer_id": i, "update_date": "2025-01-15", "dominate_role": "Leader"}
            for i in range(100, 110)
        ]
    )

    previous = _previous_full_snapshot_frame(changed, "2025-01-15", current_count=10)

    assert len(previous) == 100
    assert previous["update_date"].nunique() == 1
    assert previous["update_date"].iloc[0] == "2025-01-01"


def test_build_dancer_transitions_snapshot_merges_on_dancer_id_only() -> None:
    current = pd.DataFrame(
        [
            {
                "dancer_id": 10,
                "dancer_name": "New Name",
                "dominate_role": "Leader",
                "dominate_required": "Intermediate",
                "dominate_allowed": "Intermediate",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
            }
        ]
    )
    previous = pd.DataFrame(
        [
            {
                "dancer_id": 10,
                "dancer_name": "Old Name",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
            }
        ]
    )

    result = build_dancer_transitions_snapshot(
        current,
        previous,
        update_date="2025-01-08",
    )

    assert len(result) == 2
    assert result.iloc[0]["Dancer Name"] == "New Name"


def test_merge_snapshot_aggregates_forward_only(tmp_path: Path) -> None:
    baseline = pd.DataFrame(
        [
            {
                "update_date": "2025-01-10",
                "division": "Novice",
                "role": "Leader",
                "type_options": "required",
                "count_dancer": 99,
            }
        ]
    )
    path = tmp_path / "divisional_structure.csv"
    baseline.to_csv(path, index=False)

    new_df = pd.DataFrame(
        [
            {
                "update_date": "2025-01-05",
                "division": "Novice",
                "role": "Leader",
                "type_options": "required",
                "count_dancer": 1,
            },
            {
                "update_date": "2025-01-15",
                "division": "Novice",
                "role": "Leader",
                "type_options": "required",
                "count_dancer": 2,
            },
        ]
    )

    merged, added = _merge_snapshot_aggregates(path, new_df, type_column="type_options")

    assert added == 1
    assert set(merged["update_date"]) == {"2025-01-10", "2025-01-15"}
    assert merged[merged["update_date"] == "2025-01-10"]["count_dancer"].iloc[0] == 99


def test_merge_transitions_deduplicates(tmp_path: Path) -> None:
    path = tmp_path / "dancer_transitions.csv"
    row = {
        "Update Date": "2025-01-08",
        "Previous Division": "Novice",
        "Currently Division": "Intermediate",
        "Transition Type": "required",
        "Dancer Role": "Leader",
        "Dancer ID": 10,
        "Dancer Name": "Test",
    }
    pd.DataFrame([row]).to_csv(path, index=False)

    merged, added = _merge_transitions(path, pd.DataFrame([row]))

    assert added == 0
    assert len(merged) == 1


def test_build_derived_analytics_exports_preserves_existing_baseline(tmp_path: Path) -> None:
    baseline = pd.DataFrame(
        [
            {
                "update_date": "2025-01-01",
                "division": "Novice",
                "role": "Leader",
                "type_options": "required",
                "count_dancer": 99,
            }
        ]
    )
    baseline.to_csv(tmp_path / "divisional_structure.csv", index=False)
    pd.DataFrame(columns=TRANSITION_COLUMNS).to_csv(tmp_path / "dancer_transitions.csv", index=False)

    changed = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "dancer_name": "A",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Novice",
                "non_dominate_allowed": "Novice",
                "update_date": "2025-01-03",
            }
        ]
    )
    changed.to_csv(tmp_path / "changed_dancer_role_info.csv", index=False)
    changed.drop(columns=["update_date"]).assign(update_date="2025-01-03").to_csv(
        tmp_path / "dancer_role_info.csv", index=False
    )

    counts = build_derived_analytics_exports(tmp_path)

    merged = pd.read_csv(tmp_path / "divisional_structure.csv")
    assert merged[merged["update_date"] == "2025-01-01"]["count_dancer"].iloc[0] == 99
    assert counts["divisional_structure.csv"] == len(merged)
    assert counts["divisional_structure.csv"] >= 2


def test_build_derived_analytics_exports_skips_existing_transition_date(tmp_path: Path) -> None:
    pd.DataFrame(
        [
            {
                "Update Date": "2025-01-03",
                "Previous Division": "Novice",
                "Currently Division": "Intermediate",
                "Transition Type": "required",
                "Dancer Role": "Leader",
                "Dancer ID": 1,
                "Dancer Name": "A",
            }
        ]
    ).to_csv(tmp_path / "dancer_transitions.csv", index=False)

    changed = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "dancer_name": "A",
                "dominate_role": "Leader",
                "dominate_required": "Intermediate",
                "dominate_allowed": "Intermediate",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
                "update_date": "2025-01-01",
            },
            {
                "dancer_id": 1,
                "dancer_name": "A",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
                "update_date": "2025-01-03",
            },
        ]
    )
    changed.to_csv(tmp_path / "changed_dancer_role_info.csv", index=False)
    changed[changed["update_date"] == "2025-01-03"].drop(columns=["update_date"]).assign(
        update_date="2025-01-03"
    ).to_csv(tmp_path / "dancer_role_info.csv", index=False)

    counts = build_derived_analytics_exports(tmp_path)

    transitions = pd.read_csv(tmp_path / "dancer_transitions.csv")
    assert len(transitions) == 1
    assert counts["dancer_transitions.csv"] == 1


def test_build_derived_analytics_exports_writes_files(tmp_path: Path) -> None:
    changed = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "dancer_name": "A",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": "Follower",
                "non_dominate_required": "Novice",
                "non_dominate_allowed": "Novice",
                "update_date": "2025-01-03",
            }
        ]
    )
    changed.to_csv(tmp_path / "changed_dancer_role_info.csv", index=False)

    counts = build_derived_analytics_exports(tmp_path)

    assert counts["divisional_structure.csv"] > 0
    assert counts["divisional_structure_only_dominate_role.csv"] > 0
    assert (tmp_path / "divisional_structure.csv").exists()
    assert (tmp_path / "divisional_structure_only_dominate_role.csv").exists()
    assert (tmp_path / "dancer_transitions.csv").exists()


def test_load_role_source_falls_back_to_current_snapshot(tmp_path: Path) -> None:
    current = pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "dancer_name": "A",
                "dominate_role": "Leader",
                "dominate_required": "Novice",
                "dominate_allowed": "Novice",
                "non_dominate_role": None,
                "non_dominate_required": None,
                "non_dominate_allowed": None,
            }
        ]
    )
    current.to_csv(tmp_path / "dancer_role_info.csv", index=False)

    loaded = load_role_source(tmp_path)

    assert len(loaded) == 1
    assert loaded.iloc[0]["update_date"]


def test_load_role_source_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_role_source(tmp_path)
