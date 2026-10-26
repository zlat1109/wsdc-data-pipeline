"""Build rounds, competitor rows, final couples, and long-form judge marks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

_ROLE_NORM = {
    "leader": "Leader",
    "leaders": "Leader",
    "follower": "Follower",
    "followers": "Follower",
    "follow": "Follower",
}


def normalize_role(role: Any) -> str | None:
    if role is None:
        return None
    return _ROLE_NORM.get(str(role).strip().lower())


def parse_judge_marks(raw: Any) -> list[tuple[str, str]]:
    """Parse CR ``judge_marks`` JSON object → [(judge_name, mark), ...]."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [(str(k), str(v)) for k, v in raw.items() if k]
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "null", "{}"}:
        return []
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(obj, dict):
        return []
    return [(str(k), str(v)) for k, v in obj.items() if k]


def resolve_dancer_id(
    identity: Any,
    known_dancer_ids: set[int] | None = None,
) -> int | None:
    """FK to core.dancers only for known numeric WSDC ids."""
    if identity is None:
        return None
    s = str(identity).strip()
    if not s or s.lower() in {"redacted", "nan", "none", "null"}:
        return None
    if not re.fullmatch(r"\d+", s):
        return None
    did = int(s)
    if known_dancer_ids is not None and did not in known_dancer_ids:
        return None
    return did


def competitor_display_name(identity: Any, name: Any) -> str | None:
    """Never store a name for redacted competitors."""
    s = str(identity or "").strip().lower()
    if s == "redacted":
        return None
    n = str(name or "").strip()
    if not n or n.lower() in {"nan", "none", "null", "redacted"}:
        return None
    return n


@dataclass(frozen=True)
class CoupleKey:
    cr_round_id: str
    leader_identity: str
    follower_identity: str


def couple_key_from_row(
    *,
    cr_round_id: str,
    role: str,
    identity: str,
    partner_identity: str,
) -> CoupleKey | None:
    """Build a directed-independent couple key when both identities exist."""
    ident = (identity or "").strip()
    partner = (partner_identity or "").strip()
    if not ident or not partner:
        return None
    if ident.lower() == "redacted" or partner.lower() == "redacted":
        # Still allow pairing redacted↔known for marks attachment by place later
        pass
    if role == "Leader":
        return CoupleKey(cr_round_id, ident, partner)
    if role == "Follower":
        return CoupleKey(cr_round_id, partner, ident)
    return None


def division_id(cr_edition_id: str, raw_division: str) -> str:
    return f"{cr_edition_id}#{raw_division}"


def round_id(cr_division_id: str, round_name: str) -> str:
    return f"{cr_division_id}#{round_name}"


def iter_unique_marks(
    rows: Iterable[Mapping[str, Any]],
) -> dict[CoupleKey, list[tuple[str, str]]]:
    """For finals: first non-empty judge_marks per couple wins."""
    out: dict[CoupleKey, list[tuple[str, str]]] = {}
    for row in rows:
        role = normalize_role(row.get("role"))
        if role is None:
            continue
        ck = couple_key_from_row(
            cr_round_id=str(row["cr_round_id"]),
            role=role,
            identity=str(row.get("identity") or ""),
            partner_identity=str(row.get("partner_identity") or ""),
        )
        if ck is None:
            continue
        if ck in out:
            continue
        marks = parse_judge_marks(row.get("judge_marks"))
        if marks:
            out[ck] = marks
    return out
