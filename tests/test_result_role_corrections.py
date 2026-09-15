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
            [{"dancer_id": "14614", "dominate_role": "Follower"}]
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
