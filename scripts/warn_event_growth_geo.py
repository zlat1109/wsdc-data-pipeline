#!/usr/bin/env python3
"""Warn-only geo / JSON health checks for Event Trends (never fails the job).

Catches the class of bugs that broke Event Trends (bare NaN in event_growth.json)
and location_info cities that still lack centroids while appearing in growth.

Exit code is always 0. Writes a JSON report; prints GitHub ::warning:: lines.
Optional --telegram sends a non-blocking Telegram notice when warning_count > 0.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "data" / "quality_reports" / "event_growth_geo_warnings.json"

_COORD_KEYS = ("lat", "lon", "city_lat", "city_lon")
_NAN_TOKEN_RE = re.compile(r"\bNaN\b|\bInfinity\b|\b-Infinity\b")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _warn(code: str, message: str, examples: list[Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code,
        "severity": "warn",
        "message": message,
    }
    if examples:
        item["examples"] = examples[:8]
        item["count"] = len(examples)
    return item


def scan_growth_raw_tokens(raw: str) -> list[dict[str, Any]]:
    """Browser JSON.parse rejects bare NaN/Infinity; flag the raw file."""
    if not _NAN_TOKEN_RE.search(raw):
        return []
    examples: list[str] = []
    for match in _NAN_TOKEN_RE.finditer(raw):
        start = max(0, match.start() - 40)
        end = min(len(raw), match.end() + 40)
        examples.append(raw[start:end].replace("\n", " "))
        if len(examples) >= 5:
            break
    return [
        _warn(
            "GROWTH_JSON_NONFINITE_TOKEN",
            "event_growth.json contains bare NaN/Infinity (invalid for browsers)",
            examples,
        )
    ]


def scan_growth_edition_coords(editions: list[Any]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    missing_city: list[dict[str, Any]] = []
    for ed in editions:
        if not isinstance(ed, dict):
            continue
        label = {
            "event_id": ed.get("event_id"),
            "name": ed.get("name"),
            "year": ed.get("year"),
            "city": ed.get("city"),
        }
        for key in _COORD_KEYS:
            val = ed.get(key)
            if isinstance(val, float) and not math.isfinite(val):
                bad.append({**label, "field": key})
        # Venue pin present but city centroid absent — map city layer weak / prior bug class.
        has_venue = ed.get("lat") is not None and ed.get("lon") is not None
        city_lat = ed.get("city_lat")
        city_lon = ed.get("city_lon")
        city_missing = city_lat is None or city_lon is None
        if (
            has_venue
            and city_missing
            and ed.get("city")
            and ed.get("geo_source") == "wsdc_venue"
        ):
            missing_city.append(label)

    out: list[dict[str, Any]] = []
    if bad:
        out.append(
            _warn(
                "GROWTH_EDITION_NONFINITE_COORDS",
                "growth editions have non-finite lat/lon/city_lat/city_lon after parse",
                bad,
            )
        )
    if missing_city:
        out.append(
            _warn(
                "GROWTH_CITY_CENTROID_MISSING",
                "wsdc_venue editions missing city_lat/city_lon "
                "(location_info likely has no geocode for that city)",
                missing_city,
            )
        )
    return out


def scan_location_info(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return [
            _warn(
                "LOCATION_INFO_MISSING_FILE",
                f"location_info.csv not found at {path}",
            )
        ]
    df = pd.read_csv(path)
    if df.empty or "location_id" not in df.columns:
        return []
    lat = pd.to_numeric(df.get("latitude"), errors="coerce")
    lon = pd.to_numeric(df.get("longitude"), errors="coerce")
    mask = lat.isna() | lon.isna()
    if not mask.any():
        return []
    rows = df.loc[mask]
    examples = []
    for rec in rows.to_dict(orient="records"):
        examples.append(
            {
                "location_id": rec.get("location_id"),
                "city": rec.get("event_city"),
                "country": rec.get("event_country"),
                "coordinates_valid": rec.get("coordinates_valid"),
            }
        )
    return [
        _warn(
            "LOCATION_MISSING_COORDS",
            "location_info rows with empty/non-numeric latitude or longitude "
            "(Event Trends city centroids come from here, not the WSDC dump)",
            examples,
        )
    ]


def build_report(
    *,
    growth_path: Path | None,
    location_info_path: Path | None,
) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    growth_meta: dict[str, Any] = {"path": None, "present": False}

    if growth_path is not None and growth_path.is_file():
        growth_meta["path"] = str(growth_path)
        growth_meta["present"] = True
        raw = growth_path.read_text(encoding="utf-8")
        warnings.extend(scan_growth_raw_tokens(raw))
        # Python json.loads accepts NaN — still useful for structured field scans.
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            warnings.append(
                _warn(
                    "GROWTH_JSON_PARSE_ERROR",
                    f"event_growth.json failed to parse even for Python: {exc}",
                )
            )
            data = None
        if isinstance(data, dict):
            editions = data.get("editions") or []
            if isinstance(editions, list):
                growth_meta["n_editions"] = len(editions)
                warnings.extend(scan_growth_edition_coords(editions))
    elif growth_path is not None:
        growth_meta["path"] = str(growth_path)
        warnings.append(
            _warn(
                "GROWTH_JSON_MISSING",
                f"event_growth.json not found at {growth_path}",
            )
        )

    if location_info_path is not None:
        warnings.extend(scan_location_info(location_info_path))

    return {
        "generated_at": _utc_now(),
        "growth": growth_meta,
        "location_info": str(location_info_path) if location_info_path else None,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def emit_github_warnings(report: dict[str, Any]) -> None:
    for item in report.get("warnings") or []:
        code = item.get("code", "WARN")
        msg = item.get("message", "")
        count = item.get("count")
        suffix = f" (n={count})" if count is not None else ""
        print(f"::warning::{code}: {msg}{suffix}", flush=True)
        examples = item.get("examples") or []
        for ex in examples[:3]:
            print(f"  example: {ex}", flush=True)


def maybe_telegram(report_path: Path) -> None:
    """Best-effort notify; never raises into the caller as a hard failure."""
    script = PROJECT_ROOT / "scripts" / "telegram_notify.py"
    if not script.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(script), "growth-geo-warn", str(report_path)],
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"::warning::growth-geo telegram notify failed: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--growth",
        type=Path,
        default=None,
        help="Path to event_growth.json (site or quality_reports copy)",
    )
    parser.add_argument(
        "--location-info",
        type=Path,
        default=PROJECT_ROOT / "data" / "location_info.csv",
        help="Path to location_info.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Where to write the warnings JSON report",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Send Telegram when warning_count > 0 (non-blocking)",
    )
    parser.add_argument(
        "--skip-location-info",
        action="store_true",
        help="Only scan growth JSON",
    )
    args = parser.parse_args()

    loc_path = None if args.skip_location_info else args.location_info
    report = build_report(growth_path=args.growth, location_info_path=loc_path)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"event_growth geo warnings: {report['warning_count']} "
        f"(report → {args.report})",
        flush=True,
    )
    emit_github_warnings(report)
    if args.telegram and report["warning_count"] > 0:
        maybe_telegram(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
