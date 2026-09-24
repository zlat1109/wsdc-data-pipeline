"""Tests for Bavarian Open 2026 All-Star role swap correction."""

from __future__ import annotations

import pandas as pd

from transform.result_role_corrections import (
    correct_bavarian_allstar_roles_2026,
    plan_role_flips,
)


def test_plan_flips_only_dominate_mismatches():
    results = pd.DataFrame(
        [
            {
                "dancer_id": "14614",
                "event_name": "Bavarian Open",
                "event_year": "2026",
                "event_competition": "All-Star",
                "event_role": "leader",
                "event_points": "10",
                "event_result": "1",
            },
            {
                "dancer_id": "17339",
                "event_name": "Bavarian Open",
                "event_year": "2026",
                "event_competition": "All-Star",
                "event_role": "follower",
                "event_points": "10",
                "event_result": "1",
            },
            {
                "dancer_id": "7821",
                "event_name": "Bavarian Open",
                "event_year": "2026",
                "event_competition": "All-Star",
                "event_role": "leader",
                "event_points": "6",
                "event_result": "3",
            },
        ]
    )
    roles = pd.DataFrame(
        [
            {"dancer_id": "14614", "dominate_role": "Follower"},
            {"dancer_id": "17339", "dominate_role": "Leader"},
            {"dancer_id": "7821", "dominate_role": "Leader"},
        ]
    )
    plans = plan_role_flips(results, roles)
    assert {(p["dancer_id"], p["to_role"]) for p in plans} == {
        ("14614", "Follower"),
        ("17339", "Leader"),
    }


def test_correct_moves_points_between_role_buckets():
    data = {
        "dancers_results_info": pd.DataFrame(
            [
                {
                    "dancer_id": "14614",
                    "event_name": "Bavarian Open",
                    "event_year": 2026,
                    "event_competition": "All-Star",
                    "event_role": "leader",
                    "event_points": 10,
                    "event_result": "1",
                }
            ]
        ),
        "dancer_role_info": pd.DataFrame(
            [
                {
                    "dancer_id": "14614",
                    "dominate_role": "Follower",
                    "non_dominate_role": "Leader",
                    "non_dominate_role_highest_level": "All Star",
                    "non_dominate_role_highest_level_points": "10",
                }
            ]
        ),
        "dancers_points_info": pd.DataFrame(
            [
                {
                    "dancer_id": "14614",
                    "role": "Leader",
                    "dance": "West Coast Swing",
                    "level": "All-Star",
                    "total_points": "10",
                    "update_date": "2026-09-15",
                },
                {
                    "dancer_id": "14614",
                    "role": "Follower",
                    "dance": "West Coast Swing",
                    "level": "All-Star",
                    "total_points": "73",
                    "update_date": "2026-09-15",
                },
            ]
        ),
    }
    out, stats = correct_bavarian_allstar_roles_2026(data)
    assert stats["results_flipped"] == 1
    assert out["dancers_results_info"].iloc[0]["event_role"] == "follower"
    pts = out["dancers_points_info"]
    leader = pts[(pts["role"] == "Leader") & (pts["dancer_id"] == "14614")]
    follower = pts[(pts["role"] == "Follower") & (pts["dancer_id"] == "14614")]
    assert leader.empty
    assert int(follower.iloc[0]["total_points"]) == 83
    roles = out["dancer_role_info"]
    assert str(roles.iloc[0]["non_dominate_role_highest_level_points"] or "") == ""


def test_points_transfer_matches_als_abbr_without_duplicate_bucket():
    """Parser uses ALS; transfer target was All-Star and used to create a 2nd row."""
    from transform.result_role_corrections import apply_points_transfers

    points = pd.DataFrame(
        [
            {
                "dancer_id": "7821",
                "role": "leader",
                "dance": "West Coast Swing",
                "level": "ALS",
                "total_points": "151",
                "update_date": "2026-09-22",
            },
            {
                "dancer_id": "7821",
                "role": "follower",
                "dance": "West Coast Swing",
                "level": "ALS",
                "total_points": "42",
                "update_date": "2026-09-22",
            },
        ]
    )
    plans = [
        {
            "dancer_id": "7821",
            "from_role": "Follower",
            "to_role": "Leader",
            "points": 6,
        }
    ]
    touched = apply_points_transfers(points, plans)
    assert touched == 2
    als = points[points["level"].astype(str).str.upper().eq("ALS")]
    assert len(als) == 2
    leader = als[als["role"].map(str).str.lower().eq("leader")].iloc[0]
    follower = als[als["role"].map(str).str.lower().eq("follower")].iloc[0]
    assert int(leader["total_points"]) == 157
    assert int(follower["total_points"]) == 36
    assert not (points["level"].astype(str) == "All-Star").any()
