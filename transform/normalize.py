"""Canonical value normalization for WSDC data (Tableau-compatible full words)."""

from __future__ import annotations

# Parser abbreviations and variants -> canonical level name (matches core.levels).
LEVEL_ALIASES: dict[str, str] = {
    "NEW": "Newcomer",
    "NOV": "Novice",
    "INT": "Intermediate",
    "ADV": "Advanced",
    "ALS": "All-Star",
    "ALL": "All-Star",
    "CHMP": "Champion",
    "CH": "Champion",
    "CHAMP": "Champion",
    "CHAMPION": "Champion",
    "CHAMPIONS": "Champion",
    "MSTR": "Master",
    "MST": "Master",
    "MASTER": "Master",
    "INV": "Invitational",
    "PRO": "Professional",
    "TCH": "Teacher",
    "SPH": "Sophisticated",
    "JRS": "Juniors",
    # Full-word variants with inconsistent formatting
    "ALL STAR": "All-Star",
    "ALL-STAR": "All-Star",
    "All Star": "All-Star",
    "ALLSTAR": "All-Star",
    "Allstar": "All-Star",
    "All-Stars": "All-Star",
    "ALL-STARS": "All-Star",
    "Allstars": "All-Star",
    "Champions": "Champion",
    "Masters": "Master",
    "MASTERS": "Master",
}

CANONICAL_LEVELS = {
    "Newcomer",
    "Novice",
    "Intermediate",
    "Advanced",
    "All-Star",
    "Champion",
    "Master",
    "Invitational",
    "Professional",
    "Teacher",
    "Sophisticated",
    "Juniors",
}


def normalize_role(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    cleaned = str(value).strip().lower()
    if cleaned == "leader":
        return "Leader"
    if cleaned == "follower":
        return "Follower"
    return str(value).strip().title()


def normalize_level(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    if raw in CANONICAL_LEVELS:
        return raw
    upper = raw.upper()
    if upper in LEVEL_ALIASES:
        return LEVEL_ALIASES[upper]
    # Title-case fallback for already-full words ("Intermediate", "Master")
    titled = raw.title()
    if titled in CANONICAL_LEVELS:
        return titled
    if titled.replace("-", " ") == "All Star":
        return "All-Star"
    return raw


def normalize_division(value: str | None) -> str | None:
    """Normalize division/level fields in dancer_roles (same rules as levels)."""
    return normalize_level(value)
