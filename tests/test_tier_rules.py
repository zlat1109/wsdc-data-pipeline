"""Tests for WSDC tier rules knowledge module."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from transform.knowledge.tier_rules import (
    RULES_EDITIONS,
    TIER_DEFINITIONS,
    TIER_POINTS,
    chart_vectors,
    edition_for_date,
    iter_year_coverage,
    resolve_chart_version,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_year_coverage_unique():
    coverage = list(iter_year_coverage(2002, 2026))
    assert len(coverage) == 25
    years = [y for y, _ in coverage]
    assert years == list(range(2002, 2027))


def test_edition_windows_non_overlapping():
    sorted_eds = sorted(RULES_EDITIONS, key=lambda e: e.valid_from)
    for prev, cur in zip(sorted_eds, sorted_eds[1:]):
        assert prev.valid_to is not None
        assert prev.valid_to < cur.valid_from


def test_competitor_ranges_contiguous_within_version():
    by_ver: dict[str, list] = {}
    for d in TIER_DEFINITIONS:
        by_ver.setdefault(d.rules_version, []).append(d)

    for version, rows in by_ver.items():
        rows = sorted(rows, key=lambda r: r.tier)
        if len(rows) == 1 and rows[0].tier == 0:
            continue
        for i, row in enumerate(rows):
            assert row.min_competitors >= 0
            if row.max_competitors is not None:
                assert row.max_competitors >= row.min_competitors
            if i + 1 < len(rows):
                nxt = rows[i + 1]
                assert row.max_competitors is not None, f"{version} tier {row.tier} open-ended but not last"
                assert nxt.min_competitors == row.max_competitors + 1, (
                    f"{version}: gap/overlap between tier {row.tier} and {nxt.tier}"
                )
        assert rows[-1].max_competitors is None, f"{version}: top tier must be open-ended"


def test_points_monotonic_by_placement_and_tier():
    by_ver_tier: dict[tuple[str, int], dict[int, int]] = {}
    for p in TIER_POINTS:
        if p.placement < 1:
            continue
        by_ver_tier.setdefault((p.rules_version, p.tier), {})[p.placement] = p.points

    for (version, tier), places in by_ver_tier.items():
        assert set(places) == {1, 2, 3, 4, 5}
        for pl in range(1, 5):
            assert places[pl] >= places[pl + 1], f"{version} T{tier} placement {pl}"

    by_ver: dict[str, list[int]] = {}
    for (version, tier), _places in by_ver_tier.items():
        by_ver.setdefault(version, []).append(tier)
    for version, tiers in by_ver.items():
        tiers = sorted(t for t in tiers if t > 0)
        for lo, hi in zip(tiers, tiers[1:]):
            for pl in range(1, 6):
                assert by_ver_tier[(version, hi)][pl] >= by_ver_tier[(version, lo)][pl]


def test_finalist_points_in_tier_points():
    from transform.knowledge.tier_rules import PLACEMENT_FINALIST, finalist_points_for

    assert finalist_points_for("2018", 6) == 2
    assert finalist_points_for("2018", 1) == 0
    assert finalist_points_for("2002", 0) == 1
    finals = [p for p in TIER_POINTS if p.placement == PLACEMENT_FINALIST]
    assert finals
    assert all(p.placement == 0 for p in finals)
    # Every definition has a matching finalist row
    for d in TIER_DEFINITIONS:
        assert finalist_points_for(d.rules_version, d.tier) == d.finalist_points
        assert d.finalist_max_place is None or d.finalist_max_place >= 6


def test_inherits_from_resolves():
    assert resolve_chart_version("2018") == "2018"
    assert resolve_chart_version("2026") == "2018"
    assert resolve_chart_version("2011") == "2009"
    assert resolve_chart_version("2004") == "2002"
    assert chart_vectors("2026")[6] == (25, 22, 18, 15, 12)
    assert chart_vectors("2011")[1] == (5, 4, 3, 2, 1)


def test_edition_for_date_boundaries():
    assert edition_for_date(date(2006, 12, 31)).rules_version == "2004"
    assert edition_for_date(date(2007, 1, 1)).rules_version == "2007"
    assert edition_for_date(date(2018, 6, 1)).rules_version == "2018"
    assert edition_for_date(date(2026, 3, 1)).rules_version == "2026"
    assert edition_for_date(date(1999, 1, 1)) is None


def test_expanded_definitions_cover_all_editions():
    versions = {e.rules_version for e in RULES_EDITIONS}
    def_versions = {d.rules_version for d in TIER_DEFINITIONS}
    pts_versions = {p.rules_version for p in TIER_POINTS}
    assert def_versions == versions
    assert pts_versions == versions


def test_load_dry_run_counts():
    from load_tier_rules import load_tier_rules

    counts = load_tier_rules(None, dry_run=True)
    assert counts["editions"] == len(RULES_EDITIONS)
    assert counts["definitions"] == len(TIER_DEFINITIONS)
    assert counts["points"] == len(TIER_POINTS)
