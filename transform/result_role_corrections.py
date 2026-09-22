"""One-off / durable corrections when WSDC publishes swapped leader/follower roles.

Bavarian Open 2026 All-Star: most podium/final rows list the dancer under the
opposite of their dominate_role (Helene Mickle as Leader, Ivan Katrunov as
Follower, etc.). Place 3 and two Final Followers already match dominate and are
left alone.

Until WSDC fixes upstream, preprocess flips mismatched result roles and moves
the same event points between Leader/Follower buckets in dancers_points_info so
the next full parse does not resurrect the bug.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Temporary hold — remove this rule once WSDC republishes correct All-Star roles.
BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026 = {
    "event_id": 233,
    "event_year": 2026,
    "division_keys": frozenset({"all-star", "all-stars", "allstar", "allstars", "als"}),
    "event_name_substrings": ("bavarian open",),
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _canon_role(value: Any) -> str | None:
    role = _norm(value)
    if role == "leader":
        return "Leader"
    if role == "follower":
        return "Follower"
    return None


# Parser CSVs use abbr (ALS); repair/Tableau paths often use full names (All-Star).
_LEVEL_CANON: dict[str, str] = {
    "als": "all star",
    "all-star": "all star",
    "allstar": "all star",
    "all-stars": "all star",
    "allstars": "all star",
    "all star": "all star",
    "adv": "advanced",
    "advanced": "advanced",
    "chmp": "champion",
    "champion": "champion",
    "champions": "champion",
    "int": "intermediate",
    "intermediate": "intermediate",
    "nov": "novice",
    "novice": "novice",
    "new": "newcomer",
    "newcomer": "newcomer",
}


def _canon_level(value: Any) -> str:
    raw = _norm(value).replace("_", " ")
    return _LEVEL_CANON.get(raw, raw)


def _preferred_level_token(
    points: pd.DataFrame,
    dancer_id: str,
    dance: str,
    level: str,
) -> str:
    """Reuse existing CSV spelling for this bucket (prefer ALS over All-Star)."""
    target = _canon_level(level)
    mask = (
        points["dancer_id"].astype(str).str.strip().eq(dancer_id)
        & points["dance"].astype(str).str.strip().eq(dance)
        & points["level"].map(_canon_level).eq(target)
    )
    existing = points.loc[mask, "level"].astype(str).str.strip()
    if not existing.empty:
        return str(existing.iloc[0])
    # Parser contract for All-Star buckets.
    if target == "all star":
        return "ALS"
    return level


def _opposite_role(value: Any) -> str | None:
    role = _canon_role(value)
    if role == "Leader":
        return "Follower"
    if role == "Follower":
        return "Leader"
    return None


def _is_all_star_division(value: Any) -> bool:
    return _norm(value) in BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026["division_keys"]


def _is_bavarian_open_name(value: Any) -> bool:
    name = _norm(value)
    return any(s in name for s in BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026["event_name_substrings"])


def _year_matches(series_value: Any, target: int) -> bool:
    raw = str(series_value or "").strip()
    if not raw:
        return False
    try:
        return int(float(raw)) == target
    except (TypeError, ValueError):
        return False


def select_bavarian_allstar_2026_mask(results: pd.DataFrame) -> pd.Series:
    """Rows belonging to Bavarian Open 2026 All-Star."""
    if results.empty:
        return pd.Series(dtype=bool)
    year = BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026["event_year"]
    name_ok = results.get("event_name", pd.Series(index=results.index)).map(
        _is_bavarian_open_name
    )
    year_ok = results.get("event_year", pd.Series(index=results.index)).map(
        lambda v: _year_matches(v, year)
    )
    div_ok = results.get("event_competition", pd.Series(index=results.index)).map(
        _is_all_star_division
    )
    return name_ok & year_ok & div_ok


def plan_role_flips(
    results: pd.DataFrame,
    roles: pd.DataFrame | None,
) -> list[dict[str, Any]]:
    """Return flip plans for All-Star rows whose listed role ≠ dominate_role."""
    mask = select_bavarian_allstar_2026_mask(results)
    if not mask.any():
        return []

    dominate: dict[str, str] = {}
    if roles is not None and not roles.empty and "dancer_id" in roles.columns:
        for _, row in roles.iterrows():
            did = str(row.get("dancer_id") or "").strip()
            dom = _canon_role(row.get("dominate_role"))
            if did and dom:
                dominate[did] = dom

    plans: list[dict[str, Any]] = []
    for idx in results.index[mask]:
        row = results.loc[idx]
        did = str(row.get("dancer_id") or "").strip()
        listed = _canon_role(row.get("event_role"))
        if not did or not listed:
            continue
        expected = dominate.get(did)
        if not expected or listed == expected:
            continue
        try:
            points = int(float(row.get("event_points") or 0))
        except (TypeError, ValueError):
            points = 0
        plans.append(
            {
                "index": idx,
                "dancer_id": did,
                "from_role": listed,
                "to_role": expected,
                "points": points,
                "place": str(row.get("event_result") or "").strip(),
            }
        )
    return plans


def apply_result_role_flips(
    results: pd.DataFrame,
    plans: list[dict[str, Any]],
    *,
    role_column: str = "event_role",
    lowercase: bool = True,
) -> int:
    """Apply planned role flips in place. Returns number of rows changed."""
    if not plans:
        return 0
    changed = 0
    for plan in plans:
        idx = plan["index"]
        new_role = plan["to_role"]
        if lowercase:
            new_role = new_role.lower()
        if str(results.at[idx, role_column]).strip() != str(new_role):
            results.at[idx, role_column] = new_role
            changed += 1
    return changed


def apply_points_transfers(
    points: pd.DataFrame,
    plans: list[dict[str, Any]],
    *,
    dance: str = "West Coast Swing",
    level: str = "All-Star",
) -> int:
    """Move event points from the wrong role bucket to the correct one.

    Returns number of point-bucket cells touched (decrements + increments).
    """
    if points.empty or not plans:
        return 0

    required = {"dancer_id", "role", "dance", "level", "total_points"}
    if not required.issubset(points.columns):
        return 0

    # Aggregate transfers per (dancer, from, to).
    deltas: dict[tuple[str, str, str], int] = {}
    for plan in plans:
        pts = int(plan.get("points") or 0)
        if pts == 0:
            continue
        key = (plan["dancer_id"], plan["from_role"], plan["to_role"])
        deltas[key] = deltas.get(key, 0) + pts

    touched = 0
    for (dancer_id, from_role, to_role), amount in deltas.items():
        touched += _adjust_bucket(points, dancer_id, from_role, dance, level, -amount)
        touched += _adjust_bucket(points, dancer_id, to_role, dance, level, amount)
    return touched


def _adjust_bucket(
    points: pd.DataFrame,
    dancer_id: str,
    role: str,
    dance: str,
    level: str,
    delta: int,
) -> int:
    if delta == 0:
        return 0

    role_norm = _canon_role(role)
    if not role_norm:
        return 0

    level_canon = _canon_level(level)
    mask = (
        points["dancer_id"].astype(str).str.strip().eq(dancer_id)
        & points["role"].map(_canon_role).eq(role_norm)
        & points["dance"].astype(str).str.strip().eq(dance)
        & points["level"].map(_canon_level).eq(level_canon)
    )
    idxs = points.index[mask].tolist()

    if not idxs:
        if delta < 0:
            return 0
        # Create missing destination bucket (match parser abbr when possible).
        new_row = {col: "" for col in points.columns}
        new_row.update(
            {
                "dancer_id": dancer_id,
                "role": role_norm,
                "dance": dance,
                "level": _preferred_level_token(points, dancer_id, dance, level),
                "total_points": str(delta),
            }
        )
        if "update_date" in points.columns:
            # Leave blank; promote tolerates empty update_date.
            new_row["update_date"] = ""
        points.loc[len(points)] = new_row
        return 1

    # If ALS and All-Star both exist, fold extras into the first row.
    idx = idxs[0]
    try:
        current = int(float(points.at[idx, "total_points"] or 0))
    except (TypeError, ValueError):
        current = 0
    for extra_idx in idxs[1:]:
        try:
            current += int(float(points.at[extra_idx, "total_points"] or 0))
        except (TypeError, ValueError):
            pass
    new_total = current + delta
    if len(idxs) > 1:
        points.drop(index=idxs[1:], inplace=True)
    if new_total <= 0:
        points.drop(index=idx, inplace=True)
        points.reset_index(drop=True, inplace=True)
    else:
        points.at[idx, "total_points"] = str(new_total)
        # Prefer Title-case role for Tableau contract.
        points.at[idx, "role"] = role_norm
        if len(idxs) > 1:
            points.reset_index(drop=True, inplace=True)
    return 1


def recompute_ndr_highest_from_points(
    roles: pd.DataFrame,
    points: pd.DataFrame,
    dancer_ids: list[str] | set[str] | None = None,
) -> int:
    """Align non_dominate highest level/points with dancers_points_info buckets.

    Returns number of role rows changed.
    """
    if roles.empty or points.empty:
        return 0
    required_role = {
        "dancer_id",
        "non_dominate_role",
        "non_dominate_role_highest_level",
        "non_dominate_role_highest_level_points",
    }
    required_pts = {"dancer_id", "role", "level", "total_points"}
    if not required_role.issubset(roles.columns) or not required_pts.issubset(
        points.columns
    ):
        return 0

    skill_rank = {
        "newcomer": 10,
        "novice": 20,
        "intermediate": 30,
        "advanced": 40,
        "all-star": 50,
        "all star": 50,
        "allstar": 50,
        "als": 50,
        "champion": 60,
        "champions": 60,
        "chmp": 60,
        "master": 70,
        "masters": 70,
    }

    target_ids = {str(x).strip() for x in (dancer_ids or [])}
    changed = 0
    for idx in roles.index:
        did = str(roles.at[idx, "dancer_id"] or "").strip()
        if target_ids and did not in target_ids:
            continue
        ndr = _canon_role(roles.at[idx, "non_dominate_role"])
        if not did or not ndr:
            continue

        buckets = points[
            points["dancer_id"].astype(str).str.strip().eq(did)
            & points["role"].map(_canon_role).eq(ndr)
        ]
        best_level = None
        best_points = None
        best_rank = -1
        for _, prow in buckets.iterrows():
            level_raw = str(prow.get("level") or "").strip()
            rank = skill_rank.get(level_raw.lower().replace("_", " "))
            if rank is None:
                continue
            try:
                pts = int(float(prow.get("total_points") or 0))
            except (TypeError, ValueError):
                pts = 0
            if rank > best_rank or (rank == best_rank and pts > int(best_points or 0)):
                best_rank = rank
                # Prefer canonical All-Star spelling for Tableau.
                best_level = "All-Star" if rank == 50 else level_raw
                best_points = str(pts)

        old_level = str(roles.at[idx, "non_dominate_role_highest_level"] or "").strip()
        old_points = str(
            roles.at[idx, "non_dominate_role_highest_level_points"] or ""
        ).strip()
        new_level = best_level or ""
        new_points = best_points or ""
        # Normalize All Star ↔ All-Star for comparison.
        old_key = old_level.lower().replace("-", " ")
        new_key = new_level.lower().replace("-", " ")
        if old_key == new_key and old_points == new_points:
            continue
        roles.at[idx, "non_dominate_role_highest_level"] = new_level
        roles.at[idx, "non_dominate_role_highest_level_points"] = new_points
        changed += 1
    return changed


def correct_bavarian_allstar_roles_2026(
    data: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    """Apply Bavarian Open 2026 All-Star role swap to a preprocess data dict."""
    result = dict(data)
    stats = {
        "results_flipped": 0,
        "points_buckets_touched": 0,
        "plans": 0,
        "roles_ndr_fixed": 0,
    }

    if "dancers_results_info" not in result:
        return result, stats

    results = result["dancers_results_info"].copy()
    roles = result.get("dancer_role_info")
    plans = plan_role_flips(results, roles)
    stats["plans"] = len(plans)
    if not plans:
        result["dancers_results_info"] = results
        return result, stats

    stats["results_flipped"] = apply_result_role_flips(results, plans)
    result["dancers_results_info"] = results

    if "dancers_points_info" in result:
        points = result["dancers_points_info"].copy()
        stats["points_buckets_touched"] = apply_points_transfers(points, plans)
        result["dancers_points_info"] = points
    else:
        points = None

    if roles is not None and points is not None:
        roles_df = roles.copy()
        touched_ids = {p["dancer_id"] for p in plans}
        stats["roles_ndr_fixed"] = recompute_ndr_highest_from_points(
            roles_df, points, touched_ids
        )
        result["dancer_role_info"] = roles_df

    return result, stats
