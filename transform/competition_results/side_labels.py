"""Normalize Competition Results raw_division into short age/fun labels."""

from __future__ import annotations

import re

SIDE_LABEL_ORDER = [
    "Masters",
    "Sophisticated",
    "Strictly Newcomer",
    "Strictly Newcomer/Novice",
    "Strictly Novice",
    "Strictly Intermediate",
    "Strictly Advanced",
    "Strictly All-Stars",
    "Strictly Champions",
    "Strictly Masters",
    "Strictly Sophisticated",
    "Strictly Generational",
    "Strictly Open",
    "Strictly",
    "Switch J&J",
    "All American",
    "All European",
    "Rising Star",
    "Hi-Low J&J",
    "Crossover J&J",
    "Invitational J&J",
    "Pro-Am Strictly",
    "Pro-Am",
    "Routine/Showcase",
    "Solo",
]

_SIDE_ROUND_TAIL = re.compile(
    r"(?is)[\s\-_/|]*"
    r"(?:prelim(?:inary)?s?|semis?|finals?|finalists?|round\s*\d+|r\d+)\b.*$"
)
_SIDE_SKIP = {
    "wsdc_pointed_leveled",
    "wsdc_pointed_other",
    "wsdc_event_other",
    "non_wsdc_event",
    "jack & jill",
    "jack&jill",
    "j&j",
    "jack & jill wcs",
    "jack & jill wsdc",
}


def _clean(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"", "nan", "none", "null"} else s


def normalize_side_label(raw: str) -> str:
    """Collapse messy CR raw_division into a short age/fun label."""
    t = re.sub(r"\s+", " ", _clean(raw))
    if not t:
        return ""
    core = _SIDE_ROUND_TAIL.sub("", t).strip(" -_/|")
    core = re.sub(
        r"(?i)\b(round\s*\d+|leaders?|followers?|follows?)\b", "", core
    )
    core = re.sub(r"\s+", " ", core).strip(" -_/|")
    cl = core.lower()
    if not cl or cl in _SIDE_SKIP:
        return ""

    if "all american" in cl or "all-american" in cl:
        return "All American"
    if "all european" in cl or "all-european" in cl:
        return "All European"
    if "rising star" in cl:
        return "Rising Star"
    if "switch" in cl:
        return "Switch J&J"
    if re.search(r"\bhi(gh)?[-/ ]?lo(w)?\b", cl):
        return "Hi-Low J&J"
    if "crossover" in cl:
        return "Crossover J&J"
    if "invitational" in cl and "jack" in cl:
        return "Invitational J&J"
    if "sophisticated" in cl and "strictly" not in cl:
        return "Sophisticated"
    if re.search(r"\bmasters?\b", cl) and "strictly" not in cl and "pro" not in cl:
        return "Masters"
    if "pro am" in cl or "pro-am" in cl or "proam" in cl:
        return "Pro-Am Strictly" if "strictly" in cl else "Pro-Am"
    if "strictly" in cl:
        for token, label in (
            ("new/nov", "Newcomer/Novice"),
            ("newcomer", "Newcomer"),
            ("novice", "Novice"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("all star", "All-Stars"),
            ("all-star", "All-Stars"),
            ("allstar", "All-Stars"),
            ("champion", "Champions"),
            ("masters", "Masters"),
            ("master", "Masters"),
            ("sophisticated", "Sophisticated"),
            ("generational", "Generational"),
            ("open", "Open"),
        ):
            if token in cl:
                return f"Strictly {label}"
        return "Strictly"
    if any(x in cl for x in ("routine", "showcase", "cabaret", "team")):
        return "Routine/Showcase"
    if "solo" in cl:
        return "Solo"
    if re.search(
        r"(?i)\b(newcomer|novice|intermediate|advanced|all[-\s]?stars?|champions?)\b",
        cl,
    ) and re.search(r"(?i)jack|j&j|jill", cl):
        if not any(
            x in cl
            for x in (
                "strictly",
                "switch",
                "american",
                "european",
                "rising",
                "hi-low",
                "crossover",
                "invitational",
                "masters",
                "sophisticated",
                "junior",
                "lindy",
                "rat race",
                "wild",
                "mixed",
                "take the lead",
            )
        ):
            return ""
    if cl in {
        "newcomer",
        "novice",
        "intermediate",
        "advanced",
        "all-star",
        "all-stars",
        "champion",
        "champions",
    }:
        return ""
    if cl.startswith("wsdc "):
        return ""
    return core.replace(",", " /")


def format_side_labels(raw_blob: str) -> str:
    """Normalize a |||-joined raw_division blob → sorted ' · ' list."""
    labels: set[str] = set()
    for part in str(raw_blob or "").split("|||"):
        lab = normalize_side_label(part)
        if lab:
            labels.add(lab)
    if not labels:
        return ""
    if "Strictly" in labels and any(x.startswith("Strictly ") for x in labels):
        labels.discard("Strictly")
    ranked = [x for x in SIDE_LABEL_ORDER if x in labels]
    ranked.extend(sorted(labels - set(SIDE_LABEL_ORDER)))
    return " · ".join(ranked)
