"""Fuzzy event name matching (calendar/snapshot vs WSDC results)."""

from __future__ import annotations

from difflib import SequenceMatcher

# Schedule name (worldsdc.com/events/) → canonical name in points (core.events).
# Use when an event rebrands but WSDC results still use the historical catalog title.
# See data/events_list/README.md § Event renames.
EVENT_NAME_MAPPINGS: dict[str, str] = {
    "Rocket City Swing": "Westies on the Water",
    "Paris Swing Classic": "Paris Westie Fest",
    "Charlotte WestieFest": "Charlotte Westie Fest",
    "New Years Swing Fling": "New Year's Swing Fling",
    "Westie Weekend": "Dance Jam Jack & Jill Weekend",
    "BaroqueSwing": "Barock Swing Ludwigsburg",
    'Scandinavian Open WCS "SNOW"': "Scandinavian Open",
    "Calgary Town Open": "BTO Open",
    "Jax Westie Fest": "River City Swing",
    "Bavarian Open West Coast Swing Championships": "Bavarian Open",
    "5280 Swing Dance Championships": "5280 Westival",
    "H-Town Throw Down 2027": "Novice Invitational",
    # Dallas Championship series (id 75). Do NOT map to Worlds UCWDC (id 152, Orlando-only).
    "UCWDC Country Dance World Championships": "UCWDC Country Dance World Championship",
    "USA Grand National Dance Championships": "USA Grand Nationals",
    "USA Grand Nationals Dance Championships": "USA Grand Nationals",
    "USA Grand Nationals Dance Championship": "USA Grand Nationals",
    "USA Grand National Dance Championship": "USA Grand Nationals",
    "Jack & Jill O'Rama": "J&J O'Rama",
    "Moscow Westie Fest Gala Edition": "Moscow Westie Fest",
    # Results-side aliases (keep in sync with transform/knowledge/event_aliases.py)
    "Phoenix 4th of July": "4TH of July Convention",
    # Snapshot title variant (weekly bot) → WSDC catalog name
    "NeverlandSwing Dutch Swing Championships 2026": "Neverland Swing",
    "LoneStar Invitational": "Lone Star Invitational",
    "Lonestar Invitational": "Lone Star Invitational",
    "French Connection WCS": "FRENCH CONNECTION WCS",
}


def normalize_event_name(name: str) -> str:
    return " ".join(name.lower().strip().split())


_STOPWORDS = frozenset({"the", "a", "an", "and", "&", "wcs"})


def _significant_tokens(norm: str) -> list[str]:
    return [tok for tok in norm.split() if tok not in _STOPWORDS]


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
    score = SequenceMatcher(None, norm1, norm2).ratio()
    # Distinct city "X Westie Fest" brands must share the leading city token
    # (Lisbon Westie Fest must not match Midwest / Paris / Moscow Westie Fest).
    if norm1.endswith("westie fest") and norm2.endswith("westie fest"):
        tokens1 = _significant_tokens(norm1)
        tokens2 = _significant_tokens(norm2)
        if tokens1 and tokens2 and tokens1[0] != tokens2[0]:
            return 0.0
    return score


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
