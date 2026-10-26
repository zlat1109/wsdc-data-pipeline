"""Map CR raw_division / wsdc_division → level, category, label."""

from __future__ import annotations

import re
from typing import Any

from transform.competition_results.side_labels import normalize_side_label

# CR / WSDC public names → core.levels.level
WSDC_DIVISION_TO_LEVEL: dict[str, str] = {
    "Newcomer": "Newcomer",
    "Novice": "Novice",
    "Intermediate": "Intermediate",
    "Advanced": "Advanced",
    "All-Stars": "All-Star",
    "All-Star": "All-Star",
    "Champions": "Champion",
    "Champion": "Champion",
    "Masters": "Master",
    "Master": "Master",
    "Sophisticated": "Sophisticated",
}

_SKILL_IN_RAW = re.compile(
    r"(?i)\b(newcomer|novice|intermediate|advanced|all[-\s]?stars?|champions?)\b"
)


def resolve_level(wsdc_division: Any, raw_division: Any = "") -> str | None:
    """Return ``core.levels.level`` or None when not a leveled / age J&J."""
    wd = str(wsdc_division or "").strip()
    if wd in WSDC_DIVISION_TO_LEVEL:
        return WSDC_DIVISION_TO_LEVEL[wd]
    raw = str(raw_division or "")
    label = normalize_side_label(raw)
    if label == "Masters":
        return "Master"
    if label == "Sophisticated":
        return "Sophisticated"
    return None


def resolve_category(
    *,
    competition_bucket: str,
    wsdc_division: Any,
    raw_division: Any,
) -> str:
    """skill / age / strictly / fun / pro-am."""
    bucket = str(competition_bucket or "")
    raw = str(raw_division or "")
    label = normalize_side_label(raw)
    cl = raw.lower()

    if label in {"Pro-Am", "Pro-Am Strictly"} or "pro-am" in cl or "pro am" in cl:
        return "pro-am"
    if label and label.startswith("Strictly"):
        return "strictly"
    if label in {"Masters", "Sophisticated"}:
        return "age"
    if bucket == "wsdc_pointed_leveled" or (
        str(wsdc_division or "").strip() in WSDC_DIVISION_TO_LEVEL
        and str(wsdc_division or "").strip()
        not in {"Masters", "Master", "Sophisticated"}
    ):
        return "skill"
    if label in {
        "Switch J&J",
        "All American",
        "All European",
        "Rising Star",
        "Hi-Low J&J",
        "Crossover J&J",
        "Invitational J&J",
        "Routine/Showcase",
        "Solo",
    }:
        return "fun"
    if bucket in {"wsdc_pointed_other", "wsdc_event_other"}:
        if _SKILL_IN_RAW.search(cl) and "strictly" not in cl:
            # misbucketed skill leftover
            return "skill"
        return "fun"
    return "fun"


def resolve_label(
    *,
    competition_bucket: str,
    wsdc_division: Any,
    raw_division: Any,
) -> str:
    """Display label: skill uses wsdc_division; else normalized side label / raw."""
    wd = str(wsdc_division or "").strip()
    if competition_bucket == "wsdc_pointed_leveled" and wd:
        return wd
    if wd in {"Masters", "Sophisticated", "Master"}:
        return "Masters" if "Master" in wd else wd
    lab = normalize_side_label(str(raw_division or ""))
    if lab:
        return lab
    raw = str(raw_division or "").strip()
    return raw or wd or "Unknown"
