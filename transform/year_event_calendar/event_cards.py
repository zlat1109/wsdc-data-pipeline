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

# Last N scored editions for the Metrics sparkline (oldest → newest).
HISTORY_LIMIT = 5

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
    res = _read_csv(
        data_dir / "dancers_results_info.csv",
        usecols=[
            "dancer_id",
            "event_points",
            "event_name",
            "event_year",
            "event_month",
        ],
    )
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
    return res


def _tiers_frame(data_dir: Path) -> pd.DataFrame:
    tiers = _read_csv(
        data_dir / "edition_division_tiers.csv",
        usecols=[
            "event_id",
            "event_year",
            "event_month",
            "division",
            "role",
            "tier",
            "status",
            "dance",
        ],
    )
    if tiers.empty:
        return tiers
    tiers["event_id"] = pd.to_numeric(tiers["event_id"], errors="coerce")
    tiers["event_year"] = pd.to_numeric(tiers["event_year"], errors="coerce")
    tiers["event_month"] = pd.to_numeric(tiers["event_month"], errors="coerce")
    tiers["tier"] = pd.to_numeric(tiers["tier"], errors="coerce")
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
) -> dict[str, int]:
    ym = year * 100 + month
    sub = res[
        (res["event_name"] == event_name)
        & (res["event_year"] == year)
        & (res["event_month"] == month)
    ]
    if sub.empty:
        ud = unique_dancers_fallback
        try:
            ud_i = int(ud) if ud is not None and not pd.isna(ud) else 0
        except (TypeError, ValueError):
            ud_i = 0
        return {"unique_dancers": ud_i, "points": 0, "new_dancers": 0}

    dancers = sub["dancer_id"].drop_duplicates()
    points = int(sub["event_points"].sum())
    new_count = 0
    if not first_ym.empty:
        for did in dancers:
            if int(first_ym.get(did, ym)) == ym:
                new_count += 1
    try:
        ud_fallback = (
            int(unique_dancers_fallback)
            if unique_dancers_fallback is not None and not pd.isna(unique_dancers_fallback)
            else None
        )
    except (TypeError, ValueError):
        ud_fallback = None
    unique_dancers = int(dancers.shape[0]) if dancers.shape[0] else (ud_fallback or 0)
    return {
        "unique_dancers": unique_dancers,
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
        )
        tier_table = _tier_table_for_edition(
            tiers, int(event_id), int(last["event_year"]), int(last["event_month"])
        )

        # Sparkline history: up to HISTORY_LIMIT scored editions ending at last, oldest first.
        history_rows = past_sorted.head(HISTORY_LIMIT).iloc[::-1]
        history: list[dict[str, int]] = []
        for rec in history_rows.to_dict(orient="records"):
            hist_metrics = _edition_metrics(
                res,
                first_ym,
                str(rec.get("event_name") or ""),
                int(rec["event_year"]),
                int(rec["event_month"]),
                rec.get("unique_dancers"),
            )
            history.append(
                {
                    "year": int(rec["event_year"]),
                    "month": int(rec["event_month"]),
                    "unique_dancers": hist_metrics["unique_dancers"],
                    "points": hist_metrics["points"],
                    "new_dancers": hist_metrics["new_dancers"],
                }
            )

        cards[str(int(event_id))] = {
            "event_id": int(event_id),
            "series": {
                "first_edition": {
                    "year": int(first["event_year"]),
                    "month": int(first["event_month"]),
                },
                "editions_with_results": int(len(group)),
            },
            "last_edition": {
                "year": int(last["event_year"]),
                "month": int(last["event_month"]),
                "unique_dancers": metrics["unique_dancers"],
                "points": metrics["points"],
                "new_dancers": metrics["new_dancers"],
                "tiers": tier_table,
            },
            "history": history,
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
