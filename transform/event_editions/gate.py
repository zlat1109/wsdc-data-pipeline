"""Blocking reconciliation gate for Event Editions loads."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from transform.event_editions.decisions import case_for_key, class_rule_allows
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP


STATUS_HISTORY = frozenset({"cancelled", "hiatus", "no_results"})
FUTURE_SCHEDULED = "scheduled"
MATCH_RANK = {"exact": 0, "merge_map": 1, "month_shift": 2}


def _clean(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"", "nan", "none", "null"} else s


def _norm_city(v: Any) -> str:
    return _clean(v).lower()


def _issue_key_seen(seen: set[str], key: str) -> bool:
    """Return True if this issue key was already recorded (dedupe)."""
    if key in seen:
        return True
    seen.add(key)
    return False


def reconcile(
    *,
    todd_rows: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    core_keys: set[tuple[int, int, int]],
    decisions: dict[str, Any],
    core_by_key: dict[tuple[int, int, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return gate report. ``ok`` is False when unresolved blockers exist."""
    issues: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    seen_issue_keys: set[str] = set()

    match_by_id = {m["todd_edition_id"]: m for m in matches}
    core_by_key = core_by_key or {}

    # --- natural-key collisions among occurred Todd rows ---
    by_natural: dict[tuple[int, int, int], list[tuple[str, str]]] = defaultdict(list)
    for row in todd_rows:
        if _clean(row.get("edition_status")) != "occurred":
            continue
        tid = row["todd_edition_id"]
        m = match_by_id.get(tid)
        if not m or m["match_kind"] == "unmatched":
            continue
        key = (int(m["event_id"]), int(m["event_year"]), int(m["event_month"]))
        by_natural[key].append((tid, m["match_kind"]))

    for nat, items in sorted(by_natural.items()):
        if len(items) <= 1:
            continue
        kinds = {k for _, k in items}
        tids = [t for t, _ in items]
        # Prefer exact over merge_map (duplicate WSDC ids for same month).
        if kinds <= {"exact", "merge_map"} and "exact" in kinds:
            decision_key = f"collision:{nat[0]}:{nat[1]}-{nat[2]:02d}"
            case = case_for_key(decisions, decision_key)
            allowed.append(
                {
                    "class": "natural_key_collision_prefer_exact",
                    "key": decision_key,
                    "todd_ids": tids,
                    "decision": case,
                }
            )
            continue
        decision_key = f"collision:{nat[0]}:{nat[1]}-{nat[2]:02d}"
        case = case_for_key(decisions, decision_key)
        if case:
            allowed.append(
                {
                    "class": "natural_key_collision",
                    "key": decision_key,
                    "todd_ids": tids,
                    "decision": case,
                }
            )
        else:
            ik = f"natural_key_collision:{decision_key}"
            if not _issue_key_seen(seen_issue_keys, ik):
                issues.append(
                    {
                        "class": "natural_key_collision",
                        "key": decision_key,
                        "detail": (
                            f"multiple Todd occurred ids map to {nat}: {tids}; "
                            "add decisions.yaml case or ensure one is exact"
                        ),
                    }
                )

    # --- occurred Todd editions must match core ---
    for row in todd_rows:
        tid = row["todd_edition_id"]
        status = _clean(row.get("edition_status"))
        m = match_by_id.get(tid)
        if status == "occurred":
            if m is None or m["match_kind"] == "unmatched":
                ik = f"occurred_missing_from_core:{tid}"
                if not _issue_key_seen(seen_issue_keys, ik):
                    issues.append(
                        {
                            "class": "occurred_missing_from_core",
                            "key": tid,
                            "detail": "Todd occurred edition has no core.event_editions match",
                        }
                    )
            elif m["match_kind"] == "month_shift":
                case = case_for_key(decisions, tid)
                if case:
                    allowed.append({"class": "month_shift", "key": tid, "decision": case})
                else:
                    ik = f"month_shift:{tid}"
                    if not _issue_key_seen(seen_issue_keys, ik):
                        issues.append(
                            {
                                "class": "month_shift",
                                "key": tid,
                                "detail": "month_shift match requires a decisions.yaml case",
                            }
                        )
            continue

        if status in STATUS_HISTORY:
            if m and m["match_kind"] != "unmatched":
                allowed.append(
                    {
                        "class": "status_also_in_core",
                        "key": tid,
                        "match_kind": m["match_kind"],
                    }
                )
            else:
                rule = class_rule_allows(decisions, "status_history_absent_from_core")
                if rule:
                    allowed.append({"class": "status_history_absent_from_core", "key": tid})
                else:
                    ik = f"status_history_absent_from_core:{tid}"
                    if not _issue_key_seen(seen_issue_keys, ik):
                        issues.append(
                            {
                                "class": "status_history_absent_from_core",
                                "key": tid,
                                "detail": "missing class_rule status_history_absent_from_core",
                            }
                        )
            continue

        if status == FUTURE_SCHEDULED:
            rule = class_rule_allows(decisions, "future_scheduled_skip")
            if rule:
                allowed.append({"class": "future_scheduled_skip", "key": tid})
            else:
                ik = f"future_scheduled_skip:{tid}"
                if not _issue_key_seen(seen_issue_keys, ik):
                    issues.append(
                        {
                            "class": "future_scheduled_skip",
                            "key": tid,
                            "detail": "missing class_rule future_scheduled_skip",
                        }
                    )
            continue

        ik = f"unknown_edition_status:{tid}"
        if not _issue_key_seen(seen_issue_keys, ik):
            issues.append(
                {
                    "class": "unknown_edition_status",
                    "key": tid,
                    "detail": f"unexpected edition_status={status!r}",
                }
            )

    # --- value checks (core wins): city / dates on matched occurred ---
    for row in todd_rows:
        if _clean(row.get("edition_status")) != "occurred":
            continue
        tid = row["todd_edition_id"]
        m = match_by_id.get(tid)
        if not m or m["match_kind"] == "unmatched":
            continue
        # Only check the preferred row for a natural key (exact preferred).
        nat = (int(m["event_id"]), int(m["event_year"]), int(m["event_month"]))
        rivals = by_natural.get(nat) or [(tid, m["match_kind"])]
        preferred = min(rivals, key=lambda it: MATCH_RANK.get(it[1], 99))
        if preferred[0] != tid:
            continue
        core = core_by_key.get(nat)
        if not core:
            continue
        value_rule = class_rule_allows(decisions, "value_mismatch_core_wins")
        todd_city = _norm_city(row.get("city"))
        core_city = _norm_city(core.get("place_city"))
        if todd_city and core_city and todd_city != core_city:
            vkey = f"value_city:{nat[0]}:{nat[1]}-{nat[2]:02d}"
            case = case_for_key(decisions, vkey) or value_rule
            detail = (
                f"Todd city={row.get('city')!r} vs core "
                f"place_city={core.get('place_city')!r} (core wins)"
            )
            if case:
                if not _issue_key_seen(seen_issue_keys, f"allowed:{vkey}"):
                    allowed.append(
                        {
                            "class": "value_city_mismatch",
                            "key": vkey,
                            "detail": detail,
                            "decision": case,
                        }
                    )
            else:
                if not _issue_key_seen(seen_issue_keys, vkey):
                    issues.append(
                        {
                            "class": "value_city_mismatch",
                            "key": vkey,
                            "detail": detail + "; add class_rule value_mismatch_core_wins",
                        }
                    )
        todd_start = _clean(row.get("start_date"))
        core_start = _clean(core.get("start_date"))
        # core start_date may be date object
        if hasattr(core.get("start_date"), "isoformat"):
            core_start = core["start_date"].isoformat()[:10]
        if todd_start and core_start and todd_start[:10] != core_start[:10]:
            vkey = f"value_start_date:{nat[0]}:{nat[1]}-{nat[2]:02d}"
            case = case_for_key(decisions, vkey) or value_rule
            detail = (
                f"Todd start_date={todd_start!r} vs core start_date={core_start!r} "
                "(core wins)"
            )
            if case:
                if not _issue_key_seen(seen_issue_keys, f"allowed:{vkey}"):
                    allowed.append(
                        {
                            "class": "value_start_date_mismatch",
                            "key": vkey,
                            "detail": detail,
                            "decision": case,
                        }
                    )
            else:
                if not _issue_key_seen(seen_issue_keys, vkey):
                    issues.append(
                        {
                            "class": "value_start_date_mismatch",
                            "key": vkey,
                            "detail": detail + "; add class_rule value_mismatch_core_wins",
                        }
                    )

    # --- every core key must appear in Todd ---
    matched_core = {
        (m["event_id"], m["event_year"], m["event_month"])
        for m in matches
        if m["match_kind"] != "unmatched"
    }
    for key in sorted(core_keys):
        if key in matched_core:
            continue
        kstr = f"core:{key[0]}:{key[1]}-{key[2]:02d}"
        case = case_for_key(decisions, kstr)
        if case:
            allowed.append({"class": "core_missing_from_todd", "key": kstr, "decision": case})
        else:
            if not _issue_key_seen(seen_issue_keys, kstr):
                issues.append(
                    {
                        "class": "core_missing_from_todd",
                        "key": kstr,
                        "detail": "core.event_editions row has no Todd counterpart",
                    }
                )

    # --- MERGE_EVENT_ID_MAP vs Todd series (deduped per rid→sid) ---
    for row in todd_rows:
        raw = row.get("raw_wsdc_event_id") or row.get("wsdc_event_id")
        series = row.get("event_series_id")
        if raw is None or series is None or _clean(series) == "":
            continue
        try:
            rid = int(raw)
            sid = int(series)
        except (TypeError, ValueError):
            continue
        if rid == sid:
            continue
        mapped = MERGE_EVENT_ID_MAP.get(rid)
        if mapped is None:
            key = f"merge_map_missing:{rid}->{sid}"
            case = case_for_key(decisions, key)
            if case:
                if not _issue_key_seen(seen_issue_keys, f"allowed:{key}"):
                    allowed.append(
                        {"class": "merge_map_missing", "key": key, "decision": case}
                    )
            else:
                if not _issue_key_seen(seen_issue_keys, key):
                    issues.append(
                        {
                            "class": "merge_map_missing",
                            "key": key,
                            "detail": (
                                f"Todd series {sid} for event {rid} not in MERGE_EVENT_ID_MAP"
                            ),
                        }
                    )
        elif int(mapped) != sid:
            key = f"merge_map_conflict:{rid}"
            case = case_for_key(decisions, key)
            if case:
                if not _issue_key_seen(seen_issue_keys, f"allowed:{key}"):
                    allowed.append(
                        {"class": "merge_map_conflict", "key": key, "decision": case}
                    )
            else:
                if not _issue_key_seen(seen_issue_keys, key):
                    issues.append(
                        {
                            "class": "merge_map_conflict",
                            "key": key,
                            "detail": (
                                f"MERGE_EVENT_ID_MAP[{rid}]={mapped} vs Todd series {sid}"
                            ),
                        }
                    )

    return {
        "ok": len(issues) == 0,
        "blocker_count": len(issues),
        "allowed_count": len(allowed),
        "issues": issues,
        "allowed_sample": allowed[:50],
    }
