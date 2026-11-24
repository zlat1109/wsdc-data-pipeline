"""Warn-only Event Trends geo / NaN scanners never fail the job."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_notify import format_growth_geo_warn_message  # noqa: E402
from warn_event_growth_geo import (  # noqa: E402
    build_report,
    scan_growth_edition_coords,
    scan_growth_raw_tokens,
    scan_location_info,
)


def test_scan_raw_nan_token():
    raw = '{\n  "city_lat": NaN,\n  "city_lon": NaN\n}\n'
    warns = scan_growth_raw_tokens(raw)
    assert len(warns) == 1
    assert warns[0]["code"] == "GROWTH_JSON_NONFINITE_TOKEN"


def test_scan_raw_clean():
    assert scan_growth_raw_tokens('{"city_lat": null}') == []


def test_scan_edition_nonfinite_coords():
    editions = [
        {
            "event_id": 400,
            "name": "Manneken Swing",
            "year": 2026,
            "city": "Brussels",
            "lat": 50.84,
            "lon": 4.37,
            "city_lat": float("nan"),
            "city_lon": float("nan"),
            "geo_source": "wsdc_venue",
        },
        {
            "event_id": 1,
            "name": "Ok",
            "year": 2026,
            "city": "Paris",
            "lat": 48.8,
            "lon": 2.3,
            "city_lat": 48.8,
            "city_lon": 2.3,
            "geo_source": "wsdc_venue",
        },
    ]
    warns = scan_growth_edition_coords(editions)
    codes = {w["code"] for w in warns}
    assert "GROWTH_EDITION_NONFINITE_COORDS" in codes


def test_scan_location_info_missing(tmp_path: Path):
    path = tmp_path / "location_info.csv"
    path.write_text(
        "location_id,event_city,event_country,latitude,longitude,coordinates_valid\n"
        "1,Paris,France,48.8,2.3,t\n"
        "406,Brussels,Belgium,,,f\n",
        encoding="utf-8",
    )
    warns = scan_location_info(path)
    assert len(warns) == 1
    assert warns[0]["code"] == "LOCATION_MISSING_COORDS"
    assert warns[0]["count"] == 1


def test_build_report_warns_without_failing(tmp_path: Path):
    growth = tmp_path / "event_growth.json"
    growth.write_text(
        json.dumps(
            {
                "editions": [
                    {
                        "event_id": 400,
                        "name": "Manneken Swing",
                        "year": 2026,
                        "city": "Brussels",
                        "lat": 50.84,
                        "lon": 4.37,
                        "city_lat": None,
                        "city_lon": None,
                        "geo_source": "wsdc_venue",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loc = tmp_path / "location_info.csv"
    loc.write_text(
        "location_id,event_city,event_country,latitude,longitude,coordinates_valid\n"
        "406,Brussels,Belgium,,,f\n",
        encoding="utf-8",
    )
    report = build_report(growth_path=growth, location_info_path=loc)
    assert report["warning_count"] >= 2
    codes = {w["code"] for w in report["warnings"]}
    assert "LOCATION_MISSING_COORDS" in codes
    assert "GROWTH_CITY_CENTROID_MISSING" in codes


def test_telegram_format_includes_tag():
    report = {
        "warning_count": 1,
        "warnings": [
            {
                "code": "LOCATION_MISSING_COORDS",
                "message": "missing coords",
                "count": 1,
                "examples": [
                    {"location_id": 406, "city": "Brussels", "country": "Belgium"}
                ],
            }
        ],
    }
    text = format_growth_geo_warn_message(
        report, {"workflow": "Force rebuild", "run_url": ""}
    )
    assert "#WSDC_Event_Trends_Geo_Warn" in text
    assert "publish not blocked" in text
    assert "Brussels" in text
    assert "LOCATION_MISSING_COORDS" in text
