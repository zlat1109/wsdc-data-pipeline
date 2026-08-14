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
from transform.points_summary.advancement import (
    clear_points_cache,
    editions_start_lookup,
    get_advancement_status,
    set_event_points_timeline,
)
from transform.points_summary.merge import merge_points_summaries
from transform.points_summary.report import (
    DIVISION_ORDER,
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


def test_division_order_skill_ladder_before_age_tracks():
    """Sophisticated/Masters/Juniors must not sit between Advanced and Intermediate."""
    assert DIVISION_ORDER == [
        "Champions",
        "All-Stars",
        "Advanced",
        "Intermediate",
        "Novices",
        "Newcomers",
        "Sophisticated",
        "Masters",
        "Juniors",
    ]
    skill_end = DIVISION_ORDER.index("Newcomers")
    for age in ("Sophisticated", "Masters", "Juniors"):
        assert DIVISION_ORDER.index(age) > skill_end
    assert DIVISION_ORDER.index("Advanced") < DIVISION_ORDER.index("Intermediate")
    assert DIVISION_ORDER.index("Sophisticated") > DIVISION_ORDER.index("Advanced")


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

    Registry totals in [] are as-of the edition start date (later results
    subtracted from the live CSV). Names and (+N) must still match.
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
    set_event_points_timeline(results_rows, editions_start_lookup(editions))

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


def test_enrich_meta_dates_from_schedule_fills_blank_edition_dates():
    from scripts.build_points_summary import enrich_meta_dates_from_schedule

    meta = {
        "name": "Infinite Swing",
        "event_id": "404",
        "event_year": "2026",
        "event_month": "7",
        "start_date": None,
        "end_date": None,
        "dates": "",
    }
    by_id = {("404", "2026", "7"): ("2026-07-23", "2026-07-26")}
    enriched = enrich_meta_dates_from_schedule(meta, by_name={}, by_id=by_id)
    assert enriched["start_date"] == "2026-07-23"
    assert enriched["end_date"] == "2026-07-26"
    assert "Jul" in enriched["dates"]
    # Existing start_date must win over schedule.
    meta2 = dict(meta, start_date="2026-07-01", end_date="2026-07-01")
    kept = enrich_meta_dates_from_schedule(meta2, by_name={}, by_id=by_id)
    assert kept["start_date"] == "2026-07-01"


def test_as_of_registry_total_excludes_later_events(tmp_path: Path):
    """Live CSV snapshot must not be copied onto an earlier edition card."""
    points_csv = tmp_path / "dancers_points_info.csv"
    points_csv.write_text(
        "dancer_id,role,dance,level,total_points,update_date\n"
        "14601,Leader,West Coast Swing,All-Star,153,2026-08-14\n",
        encoding="utf-8",
    )
    results_rows = [
        {
            "dancer_id": "14601",
            "event_dance": "West Coast Swing",
            "event_competition": "All-Star",
            "event_role": "leader",
            "event_points": "4",
            "event_name": "Florida Dance Magic",
            "event_year": "2026",
            "event_month": "7",
        },
        {
            "dancer_id": "14601",
            "event_dance": "West Coast Swing",
            "event_competition": "All-Star",
            "event_role": "leader",
            "event_points": "6",
            "event_name": "Swingtacular: The Galactic Open",
            "event_year": "2026",
            "event_month": "8",
        },
    ]
    lookup = {
        ("florida dance magic", "2026", "7"): date(2026, 7, 23),
        ("swingtacular: the galactic open", "2026", "8"): date(2026, 8, 6),
    }
    clear_points_cache()
    set_event_points_timeline(results_rows, lookup)

    _before, after_fdm, marker_fdm = get_advancement_status(
        "14601",
        "leader",
        "All-Stars",
        4,
        points_csv,
        as_of=date(2026, 7, 23),
    )
    assert after_fdm == 147
    assert marker_fdm == ""

    _before, after_swing, marker_swing = get_advancement_status(
        "14601",
        "leader",
        "All-Stars",
        6,
        points_csv,
        as_of=date(2026, 8, 6),
    )
    assert after_swing == 153
    assert marker_swing == "🟡"


def test_florida_dance_magic_jaden_not_current_snapshot():
    """Regression: FDM 2026 must keep [147], not Swingtacular's live [153]."""
    _required_csvs()
    import csv

    with (DATA_DIR / "event_editions.csv").open(encoding="utf-8") as fh:
        editions = list(csv.DictReader(fh))
    results_rows = load_results_rows(DATA_DIR / "dancers_results_info.csv")
    dancers_map = load_dancers_map(DATA_DIR / "dancer_role_info.csv")
    points_csv = DATA_DIR / "dancers_points_info.csv"
    clear_points_cache()
    set_event_points_timeline(results_rows, editions_start_lookup(editions))

    fdm = next(
        r
        for r in editions
        if r.get("event_name") == "Florida Dance Magic"
        and str(r.get("event_year")) == "2026"
    )
    rebuilt = build_full_event_report(
        edition_meta_from_row(fdm), results_rows, dancers_map, points_csv
    )
    assert rebuilt is not None
    als = next(d for d in rebuilt["divisions"] if d["division"] == "All-Stars")
    second = next(p for p in als["places"] if p["place"] == "2")
    assert "Jaden Pfeiffer (+4) [147]" in second["leader"]
    assert "🟡" not in second["leader"]

