"""Fuzzy event name matching (calendar/snapshot vs WSDC results)."""

from __future__ import annotations

from difflib import SequenceMatcher

EVENT_NAME_MAPPINGS: dict[str, str] = {
    "Paris Swing Classic": "Paris Westie Fest",
    "Charlotte WestieFest": "Charlotte Westie Fest",
    "New Years Swing Fling": "New Year's Swing Fling",
    "Westie Weekend": "Dance Jam Jack & Jill Weekend",
    "BaroqueSwing": "Barock Swing Ludwigsburg",
    'Scandinavian Open WCS "SNOW"': "Scandinavian Open",
    "Calgary Town Open": "BTO Open",
    "UpTown Swing": "Swedish Swing Summer Camp",
    "Jax Westie Fest": "River City Swing",
    "Bavarian Open West Coast Swing Championships": "Bavarian Open",
    "5280 Westival": "5280 Swing Dance Championships",
    "H-Town Throw Down 2027": "Novice Invitational",
    "UCWDC Country Dance World Championships": "Worlds UCWDC",
    "USA Grand National Dance Championships": "USA Grand Nationals",
    "USA Grand Nationals Dance Championships": "USA Grand Nationals",
    "USA Grand Nationals Dance Championship": "USA Grand Nationals",
    "USA Grand National Dance Championship": "USA Grand Nationals",
    "Jack & Jill O'Rama": "J&J O'Rama",
}


def normalize_event_name(name: str) -> str:
    return " ".join(name.lower().strip().split())


def fuzzy_match_score(name1: str, name2: str) -> float:
    norm1 = normalize_event_name(name1)
    norm2 = normalize_event_name(name2)
    if norm1 == norm2:
        return 1.0
    if norm1 in norm2 or norm2 in norm1:
        shorter, longer = (norm1, norm2) if len(norm1) <= len(norm2) else (norm2, norm1)
        # Avoid matching "Westie Weekend" → "Spooky Westie Weekend" as near-certain.
        if len(shorter) / len(longer) >= 0.88:
            return 0.95
    return SequenceMatcher(None, norm1, norm2).ratio()


def find_best_match(
    target_name: str,
    candidate_names: list[str],
    threshold: float = 0.75,
) -> tuple[str | None, float]:
    if target_name in EVENT_NAME_MAPPINGS:
        mapped = EVENT_NAME_MAPPINGS[target_name]
        if mapped in candidate_names:
            return mapped, 1.0

    best_match: str | None = None
    best_score = 0.0
    for candidate in candidate_names:
        score = fuzzy_match_score(target_name, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0
