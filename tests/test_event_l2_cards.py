"""Tests for L2 event card payload builder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from transform.year_event_calendar.event_cards import (
    _tier_table_for_edition,
    build_event_l2_cards,
)


def test_tier_table_keeps_skill_rows_with_both_roles(tmp_path: Path):
    tiers = pd.DataFrame(
        [
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Novice",
                "role": "Leader",
                "tier": 2,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Novice",
                "role": "Follower",
                "tier": 2,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Master",
                "role": "Leader",
                "tier": 1,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Master",
                "role": "Follower",
                "tier": 1,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Champion",
                "role": "leader",
                "tier": 1,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 1,
                "event_year": 2025,
                "event_month": 6,
                "division": "Champion",
                "role": "follower",
                "tier": 1,
                "status": "matched",
                "dance": "West Coast Swing",
            },
        ]
    )
    table = _tier_table_for_edition(tiers, 1, 2025, 6)
    assert list(table.keys()) == ["Novice", "Champions"]
    assert table["Novice"] == {"Leader": 2, "Follower": 2}
    assert table["Champions"] == {"Leader": 1, "Follower": 1}


def test_build_event_l2_cards_picks_last_with_results(tmp_path: Path):
    data_dir = tmp_path
    pd.DataFrame(
        [
            {
                "edition_id": 10,
                "event_id": 42,
                "event_name": "Demo Swing",
                "event_year": 2024,
                "event_month": 5,
                "result_rows": 20,
                "unique_dancers": 15,
            },
            {
                "edition_id": 11,
                "event_id": 42,
                "event_name": "Demo Swing",
                "event_year": 2025,
                "event_month": 5,
                "result_rows": 30,
                "unique_dancers": 22,
            },
            {
                "edition_id": 12,
                "event_id": 42,
                "event_name": "Demo Swing",
                "event_year": 2026,
                "event_month": 5,
                "result_rows": 0,
                "unique_dancers": 0,
            },
        ]
    ).to_csv(data_dir / "event_editions.csv", index=False)

    pd.DataFrame(
        [
            {
                "dancer_id": 1,
                "event_points": 3,
                "event_name": "Demo Swing",
                "event_year": 2024,
                "event_month": 5,
            },
            {
                "dancer_id": 2,
                "event_points": 2,
                "event_name": "Demo Swing",
                "event_year": 2024,
                "event_month": 5,
            },
            {
                "dancer_id": 1,
                "event_points": 5,
                "event_name": "Demo Swing",
                "event_year": 2025,
                "event_month": 5,
            },
            {
                "dancer_id": 3,
                "event_points": 4,
                "event_name": "Demo Swing",
                "event_year": 2025,
                "event_month": 5,
            },
        ]
    ).to_csv(data_dir / "dancers_results_info.csv", index=False)

    pd.DataFrame(
        [
            {
                "event_id": 42,
                "event_year": 2025,
                "event_month": 5,
                "division": "Novice",
                "role": "Leader",
                "tier": 2,
                "status": "matched",
                "dance": "West Coast Swing",
            },
            {
                "event_id": 42,
                "event_year": 2025,
                "event_month": 5,
                "division": "Novice",
                "role": "Follower",
                "tier": 3,
                "status": "matched",
                "dance": "West Coast Swing",
            },
        ]
    ).to_csv(data_dir / "edition_division_tiers.csv", index=False)

    payload = build_event_l2_cards(data_dir, as_of=date(2026, 8, 5))
    card = payload["cards"]["42"]
    assert card["series"]["editions_with_results"] == 2
    assert card["series"]["first_edition"] == {"year": 2024, "month": 5}
    assert card["last_edition"]["year"] == 2025
    assert card["last_edition"]["month"] == 5
    assert card["last_edition"]["points"] == 9
    assert card["last_edition"]["unique_dancers"] == 2
    assert card["last_edition"]["new_dancers"] == 1  # dancer 3 first appears in 2025-05
    assert card["last_edition"]["tiers"]["Novice"] == {"Leader": 2, "Follower": 3}
