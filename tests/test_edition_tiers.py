"""Unit tests for edition Tier inference (no DB)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))

from build_edition_tiers import (  # noqa: E402
    STATUS_LEGACY,
    STATUS_MATCHED,
    STATUS_NO_POINTS,
    STATUS_NO_TIER,
    infer_row,
    match_vector,
    tighten_range,
    vector_l1_distance,
)


def test_exact_match_2018_tier3():
    m = match_vector((10, 8, 6, 4, 2), date(2019, 6, 15), scored_dancers=25)
    assert m.status == STATUS_MATCHED
    assert m.tier == 3
    assert m.vector_distance == 0
    assert m.rule_min == 20
    assert m.rule_max == 39


def test_noisy_vector_nearest():
    # 15/12/10/8/4 is close to Tier 4 (15/12/10/8/6)
    m = match_vector((15, 12, 10, 8, 4), date(2016, 3, 1), scored_dancers=45)
    assert m.status == STATUS_MATCHED
    assert m.tier == 3  # 2009 chart Tier 3 = 15/12/10/8/6
    assert m.vector_distance == 2


def test_legacy_chart_in_2018():
    # Old 2009 Tier 1 vector appearing after 2018
    m = match_vector((5, 4, 3, 2, 1), date(2018, 8, 1), scored_dancers=12)
    assert m.status == STATUS_LEGACY
    assert m.tier == 1
    assert m.rules_version in {"2009", "2011", "2015"}  # same chart owner family


def test_no_points():
    m = match_vector((0, 0, 0, 0, 0), date(2020, 1, 1), scored_dancers=0)
    assert m.status == STATUS_NO_POINTS


def test_pre_tier_flat_scale():
    m = match_vector((10, 6, 4, 3, 2), date(2005, 7, 1), scored_dancers=10)
    assert m.status == STATUS_NO_TIER
    assert m.tier == 0


def test_lindy_separate_key_in_infer_row():
    row = {
        "event_id": 1,
        "event_year": 2007,
        "event_month": 6,
        "division": "Novice",
        "role": "Leader",
        "dance": "Lindy",
        "edition_id": 99,
        "observed_points_1": 8,
        "observed_points_2": 6,
        "observed_points_3": 4,
        "observed_points_4": 2,
        "observed_points_5": 1,
        "finalists": 0,
        "scored_dancers": 10,
    }
    out = infer_row(row)
    assert out["dance"] == "Lindy"
    assert out["tier"] == 1
    assert out["status"] == STATUS_MATCHED


def test_tighten_range_conflict():
    est_min, est_max, conflict = tighten_range(5, 10, scored_dancers=14)
    assert est_min == 14
    assert est_max == 10
    assert conflict is True


def test_vector_distance_partial():
    assert vector_l1_distance((10, None, 6, 4, 2), (10, 8, 6, 4, 2)) == 0
    assert vector_l1_distance((10, 8, 6, 4, 1), (10, 8, 6, 4, 2)) == 1
