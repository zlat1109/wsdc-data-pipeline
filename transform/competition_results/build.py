"""Build normalized CR enrichment tables from a filtered parquet DataFrame."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from transform.competition_results.divisions import (
    resolve_category,
    resolve_label,
    resolve_level,
)
from transform.competition_results.editions import (
    EditionKey,
    edition_lookup,
    match_cr_edition,
)
from transform.competition_results.rounds import (
    competitor_display_name,
    couple_key_from_row,
    couple_key_from_source_group,
    division_id,
    normalize_role,
    parse_judge_marks,
    resolve_dancer_id,
    resolve_place,
    round_id,
    source_couple_key,
)


@dataclass
class CrTables:
    editions: list[dict[str, Any]] = field(default_factory=list)
    divisions: list[dict[str, Any]] = field(default_factory=list)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    round_results: list[dict[str, Any]] = field(default_factory=list)
    final_couples: list[dict[str, Any]] = field(default_factory=list)
    judge_marks: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "cr_editions": len(self.editions),
            "cr_divisions": len(self.divisions),
            "cr_rounds": len(self.rounds),
            "cr_round_results": len(self.round_results),
            "cr_final_couples": len(self.final_couples),
            "cr_judge_marks": len(self.judge_marks),
        }


def _clean(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"", "nan", "none", "null"} else s


def filter_enrichment_frame(df: pd.DataFrame) -> pd.DataFrame:
    eid = df["event_edition_id"].astype(str)
    other = df["result_from_other_source"]
    if other.dtype == object or str(other.dtype) == "string":
        other = other.map(
            lambda v: str(v).strip().lower() in {"1", "t", "true", "yes"}
            if v is not None and not (isinstance(v, float) and pd.isna(v))
            else bool(v)
            if isinstance(v, bool)
            else False
        )
    else:
        other = other.fillna(False).astype(bool)
    return df.loc[eid.str.startswith("wsdc:") & other].copy()


def build_cr_tables(
    df: pd.DataFrame,
    *,
    editions: Sequence[EditionKey] | Iterable[Mapping[str, Any]],
    known_dancer_ids: set[int] | None = None,
) -> CrTables:
    """Normalize filtered CR rows into loadable table dicts.

    ``df`` should already be filtered, or will be filtered here.
    """
    if "result_from_other_source" in df.columns:
        df = filter_enrichment_frame(df)

    lookup = edition_lookup(editions)
    out = CrTables()

    if df.empty:
        out.stats = {
            "input_rows": 0,
            "matched_editions": 0,
            "unmatched_editions": 0,
        }
        return out

    # --- editions ---
    ed_rows = (
        df.groupby("event_edition_id", sort=False)
        .agg(
            wsdc_event_id=("wsdc_event_id", "first"),
            cr_name=("event_edition_name", "first"),
            cr_date=("event_edition_date", "min"),
            scoring_source=("source", "first"),
        )
        .reset_index()
    )
    edition_by_id: dict[str, dict[str, Any]] = {}
    matched = unmatched = 0
    for _, r in ed_rows.iterrows():
        m = match_cr_edition(
            cr_edition_id=str(r.event_edition_id),
            cr_name=_clean(r.cr_name),
            wsdc_event_id=r.wsdc_event_id,
            scoring_source=_clean(r.scoring_source),
            lookup=lookup,
        )
        if m.match_status == "matched":
            matched += 1
        else:
            unmatched += 1
        row = {
            "cr_edition_id": m.cr_edition_id,
            "wsdc_event_id": m.wsdc_event_id,
            "cr_name": m.cr_name,
            "cr_date": None
            if pd.isna(r.cr_date)
            else (r.cr_date.date() if hasattr(r.cr_date, "date") else r.cr_date),
            "edition_id": m.edition_id,
            "match_status": m.match_status,
            "scoring_source": m.scoring_source or None,
            "filing_year": m.filing_year,
            "filing_month": m.filing_month,
            "canonical_event_id": m.canonical_event_id,
        }
        edition_by_id[m.cr_edition_id] = row
        out.editions.append(row)

    # --- divisions ---
    div_keys = (
        df.groupby(["event_edition_id", "raw_division"], dropna=False, sort=False)
        .agg(
            wsdc_division=("wsdc_division", "first"),
            competition_bucket=("competition_bucket", "first"),
        )
        .reset_index()
    )
    for _, r in div_keys.iterrows():
        eid = str(r.event_edition_id)
        raw = _clean(r.raw_division) or _clean(r.wsdc_division) or "Unknown"
        bucket = _clean(r.competition_bucket)
        level = resolve_level(r.wsdc_division, raw)
        out.divisions.append(
            {
                "cr_division_id": division_id(eid, raw),
                "cr_edition_id": eid,
                "raw_division": raw,
                "level": level,
                "category": resolve_category(
                    competition_bucket=bucket,
                    wsdc_division=r.wsdc_division,
                    raw_division=raw,
                ),
                "label": resolve_label(
                    competition_bucket=bucket,
                    wsdc_division=r.wsdc_division,
                    raw_division=raw,
                ),
                "competition_bucket": bucket or None,
            }
        )

    # --- rounds ---
    round_keys = (
        df.groupby(
            ["event_edition_id", "raw_division", "round"], dropna=False, sort=False
        )
        .agg(
            source_url=("source_url", "first"),
            total_competitors=("total_competitors", "max"),
            wsdc_division=("wsdc_division", "first"),
        )
        .reset_index()
    )
    for _, r in round_keys.iterrows():
        eid = str(r["event_edition_id"])
        raw = _clean(r["raw_division"]) or _clean(r["wsdc_division"]) or "Unknown"
        # Avoid Series.round method clash — always use item access.
        rnd = _clean(r["round"]).lower()
        if rnd not in {"prelim", "quarter", "semi", "final"}:
            continue
        did = division_id(eid, raw)
        out.rounds.append(
            {
                "cr_round_id": round_id(did, rnd),
                "cr_division_id": did,
                "round": rnd,
                "source_url": _clean(r["source_url"]) or None,
                "total_competitors": None
                if pd.isna(r["total_competitors"])
                else int(r["total_competitors"]),
            }
        )

    # --- round results ---
    result_id_by_key: dict[tuple[str, str, str, str], int] = {}
    next_result_id = 1
    # result_pk → mutable row dict (for partner backfill via couple_key)
    result_rows_by_pk: dict[int, dict[str, Any]] = {}
    # (cr_round_id, source_couple_key) → members for partner + finals pairing
    source_couple_members: dict[tuple[str, str], list[dict[str, Any]]] = {}
    final_rows_for_couples: list[dict[str, Any]] = []

    for _, r in df.iterrows():
        eid = str(r["event_edition_id"])
        raw = _clean(r["raw_division"]) or _clean(r["wsdc_division"]) or "Unknown"
        rnd = _clean(r["round"]).lower()
        if rnd not in {"prelim", "quarter", "semi", "final"}:
            continue
        role = normalize_role(r["role"])
        if role is None:
            continue
        identity = _clean(r["identity"]) or "unknown"
        src_ck = source_couple_key(r)
        # Legacy partner columns (pre-Oct-2026); empty on new exports.
        partner = _clean(r["partner_identity"]) if "partner_identity" in r.index else ""
        place = resolve_place(r)
        rid = round_id(division_id(eid, raw), rnd)
        # Deduplicate identical competitor rows (leader/follower mirrored marks etc.)
        dedupe_key = (rid, role, identity, src_ck or partner or "", place)
        if dedupe_key in result_id_by_key:
            continue
        result_pk = next_result_id
        next_result_id += 1
        result_id_by_key[dedupe_key] = result_pk
        dancer_id = resolve_dancer_id(identity, known_dancer_ids)
        partner_dancer_id = (
            resolve_dancer_id(partner, known_dancer_ids) if partner else None
        )
        row = {
            "cr_round_result_id": result_pk,
            "cr_round_id": rid,
            "role": role,
            "cr_identity": identity,
            "dancer_id": dancer_id,
            "competitor_name": competitor_display_name(
                identity, r["competitor_name"]
            ),
            "place": place or None,
            "callback": _clean(r["callback"]) or None,
            "partner_cr_identity": partner or None,
            "partner_dancer_id": partner_dancer_id,
        }
        out.round_results.append(row)
        result_rows_by_pk[result_pk] = row

        if src_ck:
            source_couple_members.setdefault((rid, src_ck), []).append(
                {
                    "result_pk": result_pk,
                    "role": role,
                    "identity": identity,
                    "place": place or None,
                    "judge_marks": r["judge_marks"],
                    "round": rnd,
                }
            )

        if rnd == "final":
            final_rows_for_couples.append(
                {
                    **row,
                    "identity": identity,
                    "partner_identity": partner,
                    "source_couple_key": src_ck,
                    "judge_marks": r["judge_marks"],
                }
            )
        else:
            # prelim/quarter/semi: marks per competitor
            for judge, mark in parse_judge_marks(r["judge_marks"]):
                out.judge_marks.append(
                    {
                        "cr_round_result_id": result_pk,
                        "couple_id": None,
                        "judge_name": judge,
                        "mark": mark,
                    }
                )

    # Backfill partner_* from CR couple_key groups (any round).
    for members in source_couple_members.values():
        if len(members) < 2:
            continue
        by_ident = {m["identity"]: m for m in members}
        for m in members:
            others = [i for i in by_ident if i != m["identity"]]
            if len(others) != 1:
                continue
            partner_ident = others[0]
            dest = result_rows_by_pk.get(m["result_pk"])
            if dest is None:
                continue
            if not dest.get("partner_cr_identity"):
                dest["partner_cr_identity"] = partner_ident
                dest["partner_dancer_id"] = resolve_dancer_id(
                    partner_ident, known_dancer_ids
                )

    # --- final couples + deduped marks ---
    couple_id = 1
    # Map (round, leader_ident, follower_ident) → leader/follower result ids
    leaders: dict[tuple[str, str, str], int] = {}
    followers: dict[tuple[str, str, str], int] = {}
    places: dict[tuple[str, str, str], str | None] = {}
    marks_by_couple: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    seen_source_couples: set[tuple[str, str]] = set()

    # Prefer Oct-2026 couple_key grouping for finals.
    for (rid, src_ck), members in source_couple_members.items():
        finals = [m for m in members if m["round"] == "final"]
        if len(finals) < 2:
            continue
        lead = next((m for m in finals if m["role"] == "Leader"), None)
        follow = next((m for m in finals if m["role"] == "Follower"), None)
        if lead is None or follow is None:
            continue
        seen_source_couples.add((rid, src_ck))
        ck = couple_key_from_source_group(
            cr_round_id=rid,
            leader_identity=lead["identity"],
            follower_identity=follow["identity"],
        )
        key = (ck.cr_round_id, ck.leader_identity, ck.follower_identity)
        leaders[key] = lead["result_pk"]
        followers[key] = follow["result_pk"]
        places.setdefault(key, lead.get("place") or follow.get("place"))
        marks = parse_judge_marks(lead.get("judge_marks")) or parse_judge_marks(
            follow.get("judge_marks")
        )
        if marks:
            marks_by_couple[key] = marks

    # Legacy partner_identity path for finals without couple_key.
    for row in final_rows_for_couples:
        if row.get("source_couple_key"):
            continue
        role = row["role"]
        ck = couple_key_from_row(
            cr_round_id=row["cr_round_id"],
            role=role,
            identity=row["identity"],
            partner_identity=row.get("partner_identity") or "",
        )
        if ck is None:
            continue
        key = (ck.cr_round_id, ck.leader_identity, ck.follower_identity)
        places.setdefault(key, row.get("place"))
        if role == "Leader":
            leaders[key] = row["cr_round_result_id"]
        else:
            followers[key] = row["cr_round_result_id"]
        if key not in marks_by_couple:
            marks = parse_judge_marks(row.get("judge_marks"))
            if marks:
                marks_by_couple[key] = marks

    for key, leader_rid in leaders.items():
        follower_rid = followers.get(key)
        if follower_rid is None:
            continue
        cid = couple_id
        couple_id += 1
        out.final_couples.append(
            {
                "couple_id": cid,
                "cr_round_id": key[0],
                "leader_result_id": leader_rid,
                "follower_result_id": follower_rid,
                "place": places.get(key),
            }
        )
        for judge, mark in marks_by_couple.get(key, []):
            out.judge_marks.append(
                {
                    "cr_round_result_id": None,
                    "couple_id": cid,
                    "judge_name": judge,
                    "mark": mark,
                }
            )

    out.stats = {
        "input_rows": int(len(df)),
        "matched_editions": matched,
        "unmatched_editions": unmatched,
        "final_couples_incomplete": sum(
            1 for k in leaders if k not in followers
        )
        + sum(1 for k in followers if k not in leaders),
        "source_couple_groups": len(source_couple_members),
        "source_couple_finals_paired": len(seen_source_couples),
        **out.counts(),
    }
    return out


def tables_as_dataframes(tables: CrTables) -> dict[str, pd.DataFrame]:
    return {
        "cr_editions": pd.DataFrame(tables.editions),
        "cr_divisions": pd.DataFrame(tables.divisions),
        "cr_rounds": pd.DataFrame(tables.rounds),
        "cr_round_results": pd.DataFrame(tables.round_results),
        "cr_final_couples": pd.DataFrame(tables.final_couples),
        "cr_judge_marks": pd.DataFrame(tables.judge_marks),
    }


def tables_to_dict(tables: CrTables) -> dict[str, Any]:
    return {
        "counts": tables.counts(),
        "stats": tables.stats,
        "editions": [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in tables.editions],
    }
