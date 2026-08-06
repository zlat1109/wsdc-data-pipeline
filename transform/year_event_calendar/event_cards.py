"""Build event_l2_cards.json — series + last-edition stats for the L2 event card."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SKILL_ORDER = ("Novice", "Intermediate", "Advanced", "All-Star", "Champions")
SKILL_ALIASES = {
    "Novice": "Novice",
    "Intermediate": "Intermediate",
    "Advanced": "Advanced",
    "All-Star": "All-Star",
    "All Star": "All-Star",
    "Champion": "Champions",
    "Champions": "Champions",
}

# Divisions used for approximate competitive headcount (role×tier ranges).
# Age tracks (Master / Sophisticated / Juniors) omitted — same dancers often also dance skill.
DANCERS_ESTIMATE_ORDER = ("Newcomer",) + SKILL_ORDER
DANCERS_ESTIMATE_ALIASES = {
    **SKILL_ALIASES,
    "Newcomer": "Newcomer",
}

# Skill Level Jack & Jill points scope (same as event portraits Skill JJ).
SKILL_LEVEL_ALIASES = DANCERS_ESTIMATE_ALIASES

# Current Chart 5 competitor ranges per role. Tier 6 is open-ended (130+);
# soft upper 140 is used only for midpoint estimates when rule_max is absent.
TIER_COMPETITOR_RANGES: dict[int, tuple[int, int]] = {
    1: (5, 10),
    2: (11, 19),
    3: (20, 39),
    4: (40, 79),
    5: (80, 129),
    6: (130, 140),
}

# Last N scored editions for the series sparkline (oldest → newest).
# Annual events ≈ last N years; multi-edition/year series is a shorter calendar window.
HISTORY_LIMIT = 10

TIER_TIP = {
    "en": (
        "Tier reflects field size for that role under the WSDC points chart. "
        "Larger fields award higher placement points. "
        "Current ranges (per role, from 5 competitors): "
        "Tier 1: 5–10 · Tier 2: 11–19 · Tier 3: 20–39 · "
        "Tier 4: 40–79 · Tier 5: 80–129 · Tier 6: 130+."
    ),
    "ru": (
        "Тир отражает размер поля в роли по чарту очков WSDC. "
        "Чем больше поле, тем выше очки за места. "
        "Текущие диапазоны (на роль, от 5 участников): "
        "Тир 1: 5–10 · Тир 2: 11–19 · Тир 3: 20–39 · "
        "Тир 4: 40–79 · Тир 5: 80–129 · Тир 6: 130+."
    ),
    "es": (
        "El tier refleja el tamaño del campo por rol según la tabla de puntos WSDC. "
        "Campos más grandes dan más puntos por plaza. "
        "Rangos actuales (por rol, desde 5 competidores): "
        "Tier 1: 5–10 · Tier 2: 11–19 · Tier 3: 20–39 · "
        "Tier 4: 40–79 · Tier 5: 80–129 · Tier 6: 130+."
    ),
}


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _editions_with_results(data_dir: Path) -> pd.DataFrame:
    ed = _read_csv(data_dir / "event_editions.csv")
    if ed.empty:
        return ed
    ed["event_id"] = pd.to_numeric(ed["event_id"], errors="coerce")
    ed["event_year"] = pd.to_numeric(ed["event_year"], errors="coerce")
    ed["event_month"] = pd.to_numeric(ed["event_month"], errors="coerce")
    ed["result_rows"] = pd.to_numeric(ed.get("result_rows"), errors="coerce").fillna(0)
    ed["unique_dancers"] = pd.to_numeric(ed.get("unique_dancers"), errors="coerce")
    ed = ed.dropna(subset=["event_id", "event_year", "event_month"])
    ed["event_id"] = ed["event_id"].astype(int)
    ed["event_year"] = ed["event_year"].astype(int)
    ed["event_month"] = ed["event_month"].astype(int)
    ed = ed[ed["result_rows"] > 0].copy()
    ed["ym"] = ed["event_year"] * 100 + ed["event_month"]
    return ed


def _results_frame(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "dancers_results_info.csv"
    if not path.exists():
        return pd.DataFrame()
    header = pd.read_csv(path, nrows=0).columns.tolist()
    usecols = [
        "dancer_id",
        "event_points",
        "event_name",
        "event_year",
        "event_month",
        "event_competition",
        "event_dance",
    ]
    usecols = [c for c in usecols if c in header]
    res = _read_csv(path, usecols=usecols)
    if res.empty:
        return res
    res["dancer_id"] = pd.to_numeric(res["dancer_id"], errors="coerce")
    res["event_points"] = pd.to_numeric(res["event_points"], errors="coerce").fillna(0)
    res["event_year"] = pd.to_numeric(res["event_year"], errors="coerce")
    res["event_month"] = pd.to_numeric(res["event_month"], errors="coerce")
    res = res.dropna(subset=["dancer_id", "event_year", "event_month", "event_name"])
    res["dancer_id"] = res["dancer_id"].astype(int)
    res["event_year"] = res["event_year"].astype(int)
    res["event_month"] = res["event_month"].astype(int)
    res["ym"] = res["event_year"] * 100 + res["event_month"]
    if "event_competition" not in res.columns:
        res["event_competition"] = pd.NA
    if "event_dance" not in res.columns:
        res["event_dance"] = pd.NA
    return res


def _skill_level_mask(res: pd.DataFrame) -> pd.Series:
    """True for West Coast Swing Skill Level JJ rows (Newcomer…Champion)."""
    if res.empty:
        return pd.Series(dtype=bool)
    div = res["event_competition"].fillna("").astype(str).str.strip()
    is_skill = div.map(lambda d: d in SKILL_LEVEL_ALIASES)
    if "event_dance" not in res.columns:
        return is_skill
    dance = res["event_dance"].fillna("").astype(str)
    wcs = dance.str.contains("West Coast", case=False, na=False)
    # If any WCS rows exist in the slice, keep only those; else keep skill rows as-is.
    if wcs.any():
        return is_skill & (wcs | dance.eq("") | res["event_dance"].isna())
    return is_skill


def _tiers_frame(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "edition_division_tiers.csv"
    if not path.exists():
        return pd.DataFrame()
    header = pd.read_csv(path, nrows=0).columns.tolist()
    usecols = [
        "event_id",
        "event_year",
        "event_month",
        "division",
        "role",
        "tier",
        "status",
        "dance",
        "rule_min_competitors",
        "rule_max_competitors",
    ]
    usecols = [c for c in usecols if c in header]
    tiers = _read_csv(path, usecols=usecols)
    if tiers.empty:
        return tiers
    tiers["event_id"] = pd.to_numeric(tiers["event_id"], errors="coerce")
    tiers["event_year"] = pd.to_numeric(tiers["event_year"], errors="coerce")
    tiers["event_month"] = pd.to_numeric(tiers["event_month"], errors="coerce")
    tiers["tier"] = pd.to_numeric(tiers["tier"], errors="coerce")
    for col in ("rule_min_competitors", "rule_max_competitors"):
        if col in tiers.columns:
            tiers[col] = pd.to_numeric(tiers[col], errors="coerce")
        else:
            tiers[col] = pd.NA
    tiers = tiers.dropna(subset=["event_id", "event_year", "event_month"])
    tiers["event_id"] = tiers["event_id"].astype(int)
    tiers["event_year"] = tiers["event_year"].astype(int)
    tiers["event_month"] = tiers["event_month"].astype(int)
    # Prefer West Coast Swing rows when present.
    if "dance" in tiers.columns:
        wcs = tiers["dance"].fillna("").str.contains("West Coast", case=False)
        if wcs.any():
            tiers = tiers[wcs | tiers["dance"].isna()]
    return tiers


def _tier_competitor_range(tier: int, rule_min: Any = None, rule_max: Any = None) -> tuple[int, int] | None:
    """Return (min, max) competitors for a role given tier (+ optional rule bounds)."""
    fallback = TIER_COMPETITOR_RANGES.get(int(tier))
    if fallback is None and (rule_min is None or pd.isna(rule_min)):
        return None
    soft_min, soft_max = fallback if fallback is not None else (5, 10)

    try:
        rmin = int(rule_min) if rule_min is not None and not pd.isna(rule_min) else soft_min
    except (TypeError, ValueError):
        rmin = soft_min
    try:
        if rule_max is not None and not pd.isna(rule_max):
            rmax = int(rule_max)
        else:
            # Open-ended chart max (Tier 6 / legacy Tier 3+): keep soft upper for midpoint.
            rmax = soft_max if fallback is not None else rmin
    except (TypeError, ValueError):
        rmax = soft_max if fallback is not None else rmin

    if rmax < rmin:
        rmax = rmin
    return rmin, rmax


def _estimate_dancers_from_tiers(
    tiers: pd.DataFrame, event_id: int, year: int, month: int
) -> dict[str, int] | None:
    """Approximate competitive dancers from per-role tier competitor ranges.

    For each Newcomer + skill division × role with a matched tier, add that role's
    Chart 5 competitor min/max. Midpoint of the summed range is the point estimate.
    Switch dancers (lead+follow) cannot be de-duplicated from tiers alone.
    """
    if tiers.empty:
        return None
    sub = tiers[
        (tiers["event_id"] == event_id)
        & (tiers["event_year"] == year)
        & (tiers["event_month"] == month)
    ]
    if sub.empty:
        return None

    total_min = 0
    total_max = 0
    roles_used = 0
    for rec in sub.to_dict(orient="records"):
        canon = DANCERS_ESTIMATE_ALIASES.get(str(rec.get("division") or "").strip())
        if not canon:
            continue
        role = _normalize_role(rec.get("role"))
        if role is None:
            continue
        status = str(rec.get("status") or "")
        if status not in {"matched", "legacy_chart"}:
            continue
        tier = rec.get("tier")
        if pd.isna(tier):
            continue
        tier_i = int(tier)
        if tier_i < 1:
            continue
        bounds = _tier_competitor_range(
            tier_i,
            rec.get("rule_min_competitors"),
            rec.get("rule_max_competitors"),
        )
        if bounds is None:
            continue
        rmin, rmax = bounds
        total_min += rmin
        total_max += rmax
        roles_used += 1

    if roles_used == 0:
        return None
    midpoint = int(round((total_min + total_max) / 2))
    return {
        "unique_dancers": midpoint,
        "dancers_min": int(total_min),
        "dancers_max": int(total_max),
    }


def _normalize_role(raw: Any) -> str | None:
    text = str(raw or "").strip().lower()
    if text.startswith("lead"):
        return "Leader"
    if text.startswith("follow"):
        return "Follower"
    return None


def _tier_table_for_edition(
    tiers: pd.DataFrame, event_id: int, year: int, month: int
) -> dict[str, dict[str, int]]:
    if tiers.empty:
        return {}
    sub = tiers[
        (tiers["event_id"] == event_id)
        & (tiers["event_year"] == year)
        & (tiers["event_month"] == month)
    ]
    if sub.empty:
        return {}
    by_div: dict[str, dict[str, int]] = {}
    for rec in sub.to_dict(orient="records"):
        canon = SKILL_ALIASES.get(str(rec.get("division") or "").strip())
        if not canon:
            continue
        role = _normalize_role(rec.get("role"))
        if role is None:
            continue
        status = str(rec.get("status") or "")
        tier = rec.get("tier")
        if pd.isna(tier):
            continue
        tier_i = int(tier)
        if tier_i < 1:
            continue
        if status not in {"matched", "legacy_chart"}:
            continue
        by_div.setdefault(canon, {})[role] = tier_i

    out: dict[str, dict[str, int]] = {}
    for div in SKILL_ORDER:
        roles = by_div.get(div)
        if not roles:
            continue
        if "Leader" in roles and "Follower" in roles:
            out[div] = {"Leader": roles["Leader"], "Follower": roles["Follower"]}
    return out


def _edition_metrics(
    res: pd.DataFrame,
    first_ym: pd.Series,
    event_name: str,
    year: int,
    month: int,
    unique_dancers_fallback: Any,
    *,
    tiers: pd.DataFrame | None = None,
    event_id: int | None = None,
) -> dict[str, int]:
    ym = year * 100 + month
    sub = res[
        (res["event_name"] == event_name)
        & (res["event_year"] == year)
        & (res["event_month"] == month)
    ]
    points = 0
    new_count = 0
    scored_unique = 0
    if not sub.empty:
        dancers = sub["dancer_id"].drop_duplicates()
        skill_sub = sub.loc[_skill_level_mask(sub)]
        points = int(skill_sub["event_points"].sum()) if not skill_sub.empty else 0
        if not first_ym.empty:
            for did in dancers:
                if int(first_ym.get(did, ym)) == ym:
                    new_count += 1
        scored_unique = int(dancers.shape[0])

    try:
        ud_fallback = (
            int(unique_dancers_fallback)
            if unique_dancers_fallback is not None and not pd.isna(unique_dancers_fallback)
            else None
        )
    except (TypeError, ValueError):
        ud_fallback = None

    estimate = None
    if tiers is not None and event_id is not None:
        estimate = _estimate_dancers_from_tiers(tiers, int(event_id), year, month)

    if estimate is not None:
        return {
            "unique_dancers": estimate["unique_dancers"],
            "dancers_min": estimate["dancers_min"],
            "dancers_max": estimate["dancers_max"],
            "dancers_approx": 1,
            "points": points,
            "new_dancers": new_count,
        }

    unique_dancers = scored_unique if scored_unique else (ud_fallback or 0)
    return {
        "unique_dancers": unique_dancers,
        "dancers_approx": 0,
        "points": points,
        "new_dancers": new_count,
    }


def build_event_l2_cards(
    data_dir: Path | str,
    *,
    as_of: date | None = None,
) -> dict:
    """Build L2 card payload keyed by event_id (string)."""
    data_dir = Path(data_dir)
    as_of = as_of or date.today()
    editions = _editions_with_results(data_dir)
    res = _results_frame(data_dir)
    tiers = _tiers_frame(data_dir)

    first_ym = (
        res.groupby("dancer_id")["ym"].min() if not res.empty else pd.Series(dtype="int64")
    )

    cards: dict[str, dict] = {}
    if editions.empty:
        return {
            "as_of": as_of.isoformat(),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tier_tip": TIER_TIP,
            "cards": cards,
        }

    as_of_ym = as_of.year * 100 + as_of.month
    for event_id, group in editions.groupby("event_id"):
        group = group.sort_values(["ym", "edition_id"], ascending=[True, True])
        first = group.iloc[0]
        # Last edition with points as of as_of month (data already omits future empty results).
        past = group[group["ym"] <= as_of_ym]
        if past.empty:
            past = group
        past_sorted = past.sort_values(["ym", "edition_id"], ascending=[False, False])
        last = past_sorted.iloc[0]

        metrics = _edition_metrics(
            res,
            first_ym,
            str(last.get("event_name") or ""),
            int(last["event_year"]),
            int(last["event_month"]),
            last.get("unique_dancers"),
            tiers=tiers,
            event_id=int(event_id),
        )
        tier_table = _tier_table_for_edition(
            tiers, int(event_id), int(last["event_year"]), int(last["event_month"])
        )

        # All scored editions ≤ as_of (oldest → newest) for right-panel lookup + spark.
        scored_asc = past_sorted.iloc[::-1]
        editions: list[dict[str, Any]] = []
        for rec in scored_asc.to_dict(orient="records"):
            hist_metrics = _edition_metrics(
                res,
                first_ym,
                str(rec.get("event_name") or ""),
                int(rec["event_year"]),
                int(rec["event_month"]),
                rec.get("unique_dancers"),
                tiers=tiers,
                event_id=int(event_id),
            )
            hist_tiers = _tier_table_for_edition(
                tiers, int(event_id), int(rec["event_year"]), int(rec["event_month"])
            )
            hist_row: dict[str, Any] = {
                "year": int(rec["event_year"]),
                "month": int(rec["event_month"]),
                "unique_dancers": hist_metrics["unique_dancers"],
                "points": hist_metrics["points"],
                "new_dancers": hist_metrics["new_dancers"],
                "dancers_approx": hist_metrics.get("dancers_approx", 0),
                "tiers": hist_tiers,
            }
            if hist_metrics.get("dancers_approx"):
                hist_row["dancers_min"] = hist_metrics["dancers_min"]
                hist_row["dancers_max"] = hist_metrics["dancers_max"]
            editions.append(hist_row)

        # Sparkline: last HISTORY_LIMIT scored editions only.
        history = editions[-HISTORY_LIMIT:] if editions else []

        last_edition: dict[str, Any] = {
            "year": int(last["event_year"]),
            "month": int(last["event_month"]),
            "unique_dancers": metrics["unique_dancers"],
            "points": metrics["points"],
            "new_dancers": metrics["new_dancers"],
            "dancers_approx": metrics.get("dancers_approx", 0),
            "tiers": tier_table,
        }
        if metrics.get("dancers_approx"):
            last_edition["dancers_min"] = metrics["dancers_min"]
            last_edition["dancers_max"] = metrics["dancers_max"]

        cards[str(int(event_id))] = {
            "event_id": int(event_id),
            "series": {
                "first_edition": {
                    "year": int(first["event_year"]),
                    "month": int(first["event_month"]),
                },
                "editions_with_results": int(len(group)),
            },
            "last_edition": last_edition,
            "history": history,
            "editions": editions,
        }

    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tier_tip": TIER_TIP,
        "cards": cards,
    }


def write_event_l2_cards(payload: dict, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
