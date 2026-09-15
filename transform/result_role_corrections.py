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

    mask = (
        points["dancer_id"].astype(str).str.strip().eq(dancer_id)
        & points["role"].map(_canon_role).eq(role_norm)
        & points["dance"].astype(str).str.strip().eq(dance)
        & points["level"].astype(str).str.strip().eq(level)
    )
    idxs = points.index[mask].tolist()

    if not idxs:
        if delta < 0:
            return 0
        # Create missing destination bucket.
        new_row = {col: "" for col in points.columns}
        new_row.update(
            {
                "dancer_id": dancer_id,
                "role": role_norm,
                "dance": dance,
                "level": level,
                "total_points": str(delta),
            }
        )
        if "update_date" in points.columns:
            # Leave blank; promote tolerates empty update_date.
            new_row["update_date"] = ""
        points.loc[len(points)] = new_row
        return 1

    idx = idxs[0]
    try:
        current = int(float(points.at[idx, "total_points"] or 0))
    except (TypeError, ValueError):
        current = 0
    new_total = current + delta
    if new_total <= 0:
        points.drop(index=idx, inplace=True)
        points.reset_index(drop=True, inplace=True)
    else:
        points.at[idx, "total_points"] = str(new_total)
        # Prefer Title-case role for Tableau contract.
        points.at[idx, "role"] = role_norm
    return 1


def correct_bavarian_allstar_roles_2026(
    data: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    """Apply Bavarian Open 2026 All-Star role swap to a preprocess data dict."""
    result = dict(data)
    stats = {"results_flipped": 0, "points_buckets_touched": 0, "plans": 0}

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

    return result, stats
