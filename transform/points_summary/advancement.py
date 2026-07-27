"""WSDC Chart 3 advancement markers for Point Summary lines."""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

ADVANCEMENT_THRESHOLDS = {
    "NEW": {"allowed": 0, "required": 1, "next_div": "NOV"},
    "NOV": {"allowed": 16, "required": 30, "next_div": "INT"},
    "INT": {"allowed": 30, "required": 45, "next_div": "ADV"},
    "ADV": {"allowed": 60, "required": 90, "next_div": "ALS"},
    "ALS": {"allowed": 150, "required": 225, "next_div": "CHMP"},
    "CHMP": {"allowed": 1, "required": 10, "next_div": None},
    "SPH": {"allowed": 999999, "required": 999999, "next_div": None},
    "MSTR": {"allowed": 999999, "required": 999999, "next_div": None},
    "JRS": {"allowed": 999999, "required": 999999, "next_div": None},
}

DIVISION_TO_CODE = {
    "Newcomer": "NEW",
    "Newcomers": "NEW",
    "Novice": "NOV",
    "Novices": "NOV",
    "Intermediate": "INT",
    "Advanced": "ADV",
    "All-Star": "ALS",
    "All-Stars": "ALS",
    "Champion": "CHMP",
    "Champions": "CHMP",
    "Sophisticated": "SPH",
    "Masters": "MSTR",
    "Juniors": "JRS",
}

LEVEL_TO_CODE = {
    "NEW": "NEW",
    "NOV": "NOV",
    "INT": "INT",
    "ADV": "ADV",
    "ALS": "ALS",
    "CHMP": "CHMP",
    "SPH": "SPH",
    "MSTR": "MSTR",
    "JRS": "JRS",
    "NEWCOMER": "NEW",
    "NOVICE": "NOV",
    "INTERMEDIATE": "INT",
    "ADVANCED": "ADV",
    "ALL-STAR": "ALS",
    "ALL-STARS": "ALS",
    "CHAMPION": "CHMP",
    "CHAMPIONS": "CHMP",
    "SOPHISTICATED": "SPH",
    "MASTER": "MSTR",
    "MASTERS": "MSTR",
    "JUNIORS": "JRS",
}

_points_cache: Optional[Dict[Tuple[str, str], Dict[str, int]]] = None
_cache_lock = threading.Lock()
_cache_source: Optional[Path] = None


def clear_points_cache() -> None:
    global _points_cache, _cache_source
    with _cache_lock:
        _points_cache = None
        _cache_source = None


def load_all_dancer_points(
    points_csv: Path,
) -> Dict[Tuple[str, str], Dict[str, int]]:
    """Load all West Coast Swing points keyed by (dancer_id, role)."""
    global _points_cache, _cache_source

    path = Path(points_csv)
    if _points_cache is not None and _cache_source == path:
        return _points_cache

    with _cache_lock:
        if _points_cache is not None and _cache_source == path:
            return _points_cache

        cache: Dict[Tuple[str, str], Dict[str, int]] = {}
        with path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("dance") != "West Coast Swing":
                    continue
                dancer_id = (row.get("dancer_id") or "").strip()
                role = (row.get("role") or "").strip().lower()
                raw_level = (row.get("level") or "").strip()
                level = LEVEL_TO_CODE.get(raw_level.upper(), raw_level)
                try:
                    total_points = int(row.get("total_points") or 0)
                except ValueError:
                    continue
                if not dancer_id or not role:
                    continue
                key = (dancer_id, role)
                cache.setdefault(key, {})[level] = total_points

        _points_cache = cache
        _cache_source = path
        return cache


def load_dancer_points(
    dancer_id: str,
    role: str,
    points_csv: Path,
) -> Dict[str, int]:
    cache = load_all_dancer_points(points_csv)
    return cache.get((dancer_id, role.lower()), {})


def get_advancement_status(
    dancer_id: str,
    role: str,
    division: str,
    points_earned: int | str,
    points_csv: Path,
) -> Tuple[int, int, str]:
    """Return (points_before, points_current, status_emoji)."""
    division_code = DIVISION_TO_CODE.get(division)
    if not division_code or division_code not in ADVANCEMENT_THRESHOLDS:
        return (0, 0, "")

    all_points = load_dancer_points(dancer_id, role, points_csv)
    points_current = all_points.get(division_code, 0)
    try:
        earned = int(points_earned)
    except (TypeError, ValueError):
        earned = 0
    points_before = max(0, points_current - earned)

    thresholds = ADVANCEMENT_THRESHOLDS[division_code]
    allowed_threshold = thresholds["allowed"]
    required_threshold = thresholds["required"]

    if division_code == "CHMP":
        als_points = all_points.get("ALS", 0)
        if als_points >= 225:
            status = ""
        elif points_before < required_threshold and points_current >= required_threshold:
            status = "🟢"
        else:
            status = ""
    elif points_before < required_threshold and points_current >= required_threshold:
        status = "🟢"
    elif (
        division_code in {"INT", "ADV", "ALS"}
        and points_before == 0
        and points_current > 0
    ):
        previous_division_check = {
            "INT": ("NOV", 30),
            "ADV": ("INT", 45),
            "ALS": ("ADV", 90),
        }
        prev_div_code, prev_required = previous_division_check[division_code]
        prev_div_points = all_points.get(prev_div_code, 0)
        status = "🟢" if prev_div_points < prev_required else ""
    elif points_before < allowed_threshold and points_current >= allowed_threshold:
        status = "🟡"
    else:
        status = ""

    return (points_before, points_current, status)
