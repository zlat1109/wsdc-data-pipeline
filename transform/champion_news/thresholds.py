"""Champion News milestone thresholds (All-Stars → Champions track)."""

from __future__ import annotations

ALS_ALLOWED = 150
ALS_REQUIRED = 225
CHMP_REQUIRED = 10

STATUS_ALLOWED = "allowed"
STATUS_REQUIRED = "required"

PATHWAY_ALS_225 = "als_225"
PATHWAY_CHMP_10 = "chmp_10"

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


def division_code(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if text.upper() in {"NEW", "NOV", "INT", "ADV", "ALS", "CHMP", "SPH", "MSTR", "JRS"}:
        return text.upper()
    return DIVISION_TO_CODE.get(text, text)
