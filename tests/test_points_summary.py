"""Point Summary builder + golden comparison against live site JSON."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from transform.knowledge.geo_flags import (
    continent_for_country,
    flag_for_country,
    resolve_flag_and_continent,
)
from transform.points_summary.advancement import clear_points_cache
from transform.points_summary.merge import merge_points_summaries
from transform.points_summary.report import (
    build_full_event_report,
    canonicalize_division,
    edition_meta_from_row,
    load_dancers_map,
    load_results_rows,
    make_event_slug,
)

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PIPELINE_ROOT / "data"
SITE_SUMMARY = Path("/Users/ania/.cursor/wsdc-analytics-repo/static/data/points_summaries.json")
BOT_SUMMARY = PIPELINE_ROOT.parent / "telegram-news-bot" / "data" / "points_summaries.json"


def _summary_path() -> Path:
    if SITE_SUMMARY.exists():
        return SITE_SUMMARY
    if BOT_SUMMARY.exists():
        return BOT_SUMMARY
    pytest.skip("points_summaries.json not found locally")


def _required_csvs() -> None:
    for name in (
        "event_editions.csv",
        "dancers_results_info.csv",
        "dancer_role_info.csv",
        "dancers_points_info.csv",
    ):
        if not (DATA_DIR / name).exists():
            pytest.skip(f"missing {name}")


def test_geo_flags_from_normalized_country():
    assert continent_for_country("Sweden") == "Europe"
    assert flag_for_country("Sweden") == "🇸🇪"
    assert continent_for_country("United States") == "America"
    flag, continent = resolve_flag_and_continent(country="Malaysia")
    assert flag == "🇲🇾"
    assert continent == "Asia"


def test_make_event_slug_uses_start_date():
    assert make_event_slug("Rock The Barn", "2026-07-17") == "2026-07-17-rock-the-barn"
    assert make_event_slug("MY Swing", "2026-07-10") == "2026-07-10-my-swing"


def test_canonicalize_division_variants():
    assert canonicalize_division("All-Star") == "All-Stars"
    assert canonicalize_division("Champion") == "Champions"
    assert canonicalize_division("Novice") == "Novices"


def test_merge_preserves_telegraph_url_and_creates_after_cutoff():
    existing = {
        "summaries": [
            {
                "post_date": "22-07-2026",
                "events_count": 1,
                "events": [
                    {
                        "slug": "2026-07-17-rock-the-barn",
                        "name": "Rock The Barn",
                        "telegraph_url": "https://telegra.ph/existing",
                        "divisions": [{"division": "Advanced", "places": []}],
                        "start_date": "2026-07-17",
                        "end_date": "2026-07-20",
                    }
                ],
            }
        ]
    }
    candidates = [
        {
            "slug": "2026-07-17-rock-the-barn",
            "name": "Rock The Barn",
            "telegraph_url": None,
            "divisions": [
                {
                    "division": "Advanced",
                    "places": [
                        {
                            "place": "1",
                            "place_label": "🥇 1 place",
                            "leader": "A (+3) [1]",
                            "follower": "B (+3) [1]",
                        }
                    ],
                }
            ],
            "start_date": "2026-07-17",
            "end_date": "2026-07-20",
        },
        {
            "slug": "2026-07-25-new-event",
            "name": "New Event",
            "divisions": [
                {
                    "division": "Advanced",
                    "places": [
                        {
                            "place": "1",
                            "place_label": "🥇 1 place",
                            "leader": "C (+3) [1]",
                            "follower": "D (+3) [1]",
                        }
                    ],
                }
            ],
            "start_date": "2026-07-25",
            "end_date": "2026-07-27",
        },
    ]
    payload, report = merge_points_summaries(
        existing,
        candidates,
        cutoff=date(2026, 7, 24),
        update_window_days=30,
        today=date(2026, 7, 27),
    )
    assert report["updated_count"] == 1
    assert report["created_count"] == 1
    rock = next(
        e
        for b in payload["summaries"]
        for e in b["events"]
        if e["slug"] == "2026-07-17-rock-the-barn"
    )
    assert rock["telegraph_url"] == "https://telegra.ph/existing"
    assert rock["divisions"][0]["places"][0]["leader"].startswith("A")
    assert any(
        e["slug"] == "2026-07-25-new-event"
        for b in payload["summaries"]
        for e in b["events"]
    )


def _find_edition_row(editions: list[dict], event_name: str) -> dict | None:
    import re

    name = event_name.strip().lower()
    stripped = re.sub(r"\s+20\d{2}$", "", name).strip()
    aliases = {
        "neverlandswing dutch swing championships": "neverland swing",
        "phoenix 4th of july": "4th of july convention",
        "baroqueswing": "barock swing ludwigsburg",
        "d-townswing": "d-town swing",
        "midwest westie fest": "midwest westie fest",
    }
    targets = {name, stripped}
    for key, alias in aliases.items():
        if name == key or stripped == key or key in name or key in stripped:
            targets.add(alias)

    matches = []
    for r in editions:
        en = (r.get("event_name") or "").strip().lower()
        if en in targets:
            matches.append(r)
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda r: (
            int(r.get("event_year") or 0),
            int(r.get("event_month") or 0),
        ),
        reverse=True,
    )[0]


def _place_signature(place: dict) -> tuple:
    """Compare podium composition + points earned; ignore running totals/markers.

    Registry totals in [] advance after later events, so exact equality against an
    older points_summaries.json snapshot is not stable. Names and (+N) are.
    """
    import re

    def core(line: str | None) -> str:
        if not line:
            return ""
        return re.sub(r"\s*\[\d+\](?:\s*[🟢🟡])?\s*$", "", line).strip()

    return (
        place.get("place"),
        core(place.get("leader")),
        core(place.get("follower")),
        tuple(core(x) for x in (place.get("leaders") or [])),
        tuple(core(x) for x in (place.get("followers") or [])),
    )


def test_golden_recent_summary_blocks_match_pipeline_builder():
    """Compare divisions/places for recent site entities against CSV rebuild."""
    _required_csvs()
    summary_path = _summary_path()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    blocks = (payload.get("summaries") or [])[:6]
    assert blocks, "empty points_summaries.json"

    import csv

    with (DATA_DIR / "event_editions.csv").open(encoding="utf-8") as fh:
        editions = list(csv.DictReader(fh))
    results_rows = load_results_rows(DATA_DIR / "dancers_results_info.csv")
    dancers_map = load_dancers_map(DATA_DIR / "dancer_role_info.csv")
    points_csv = DATA_DIR / "dancers_points_info.csv"
    clear_points_cache()

    compared = 0
    mismatches: list[str] = []
    for block in blocks:
        for event in block.get("events") or []:
            name = event.get("name") or ""
            row = _find_edition_row(editions, name)
            if row is None:
                mismatches.append(f"no edition for {name!r}")
                continue
            meta = edition_meta_from_row(row)
            # Keep flag/continent from site for content focus; rebuild body.
            rebuilt = build_full_event_report(
                meta, results_rows, dancers_map, points_csv
            )
            if rebuilt is None:
                mismatches.append(f"rebuild empty for {name!r}")
                continue

            expected_divs = {
                canonicalize_division(d["division"]): d
                for d in event.get("divisions") or []
            }
            got_divs = {d["division"]: d for d in rebuilt.get("divisions") or []}

            # Compare top-tier divisions that both sides have (1st place lines).
            for div_name in ("Champions", "All-Stars", "Advanced", "Intermediate", "Novices"):
                if div_name not in expected_divs or div_name not in got_divs:
                    continue
                exp_places = {
                    p["place"]: p for p in expected_divs[div_name].get("places") or []
                }
                got_places = {
                    p["place"]: p for p in got_divs[div_name].get("places") or []
                }
                for place in ("1", "2", "3"):
                    if place not in exp_places or place not in got_places:
                        continue
                    if _place_signature(exp_places[place]) != _place_signature(
                        got_places[place]
                    ):
                        mismatches.append(
                            f"{name}/{div_name}/{place}: "
                            f"expected={exp_places[place]!r} got={got_places[place]!r}"
                        )
                    else:
                        compared += 1

    assert compared >= 8, f"too few comparable podium lines: {compared}"
    # A few historical name/CSV drifts are expected (renames, later results).
    assert len(mismatches) <= 5, "\n".join(mismatches[:20])
