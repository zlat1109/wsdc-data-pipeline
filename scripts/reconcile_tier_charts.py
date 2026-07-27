#!/usr/bin/env python3
"""Reconcile Chart 5 vectors against observed placement-point vectors in CSV/DB.

Usage:
    python scripts/reconcile_tier_charts.py
    python scripts/reconcile_tier_charts.py --csv data/dancers_results_info.csv
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.knowledge.tier_rules import (  # noqa: E402
    RULES_EDITIONS,
    chart_vectors,
    edition_for_date,
)


def _vector_key(row: pd.Series) -> tuple[int | None, ...]:
    out: list[int | None] = []
    for place in (1, 2, 3, 4, 5):
        val = row.get(place)
        if pd.isna(val):
            out.append(None)
        else:
            out.append(int(val))
    return tuple(out)


def _exact_match(
    observed: tuple[int | None, ...],
    chart: dict[int, tuple[int, int, int, int, int]],
) -> list[int]:
    hits: list[int] = []
    for tier, pts in chart.items():
        ok = True
        for i, obs in enumerate(observed):
            if obs is None:
                continue
            if obs != pts[i]:
                ok = False
                break
        if ok and any(o is not None for o in observed):
            # Require at least placement 1 present for a confident match
            if observed[0] is None or observed[0] == pts[0]:
                hits.append(tier)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_ROOT / "data" / "dancers_results_info.csv",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv, low_memory=False)
    sub = df[df["event_result_standardized"].isin(["1", "2", "3", "4", "5"])].copy()
    sub["pl"] = sub["event_result_standardized"].astype(int)
    key = [
        "event_name",
        "event_year",
        "event_month",
        "event_competition",
        "event_role",
        "event_dance",
    ]
    piv = (
        sub.pivot_table(
            index=key,
            columns="pl",
            values="event_points",
            aggfunc="max",
        )
        .reset_index()
    )

    matched = Counter()
    unmatched: Counter = Counter()
    by_edition_tier: Counter = Counter()
    no_edition = 0

    for _, row in piv.iterrows():
        year = int(row["event_year"])
        month = int(row["event_month"])
        as_of = date(year, month, 15)
        ed = edition_for_date(as_of)
        if ed is None:
            no_edition += 1
            continue
        chart = chart_vectors(ed.rules_version)
        observed = _vector_key(row)
        if all(v is None or v == 0 for v in observed):
            matched["zero_or_empty"] += 1
            continue
        hits = _exact_match(observed, chart)
        if len(hits) == 1:
            matched["exact"] += 1
            by_edition_tier[(ed.rules_version, hits[0])] += 1
        elif len(hits) > 1:
            matched["ambiguous"] += 1
        else:
            # try any other edition's chart (legacy)
            legacy_hit = False
            for other in RULES_EDITIONS:
                if other.rules_version == ed.rules_version:
                    continue
                ohits = _exact_match(observed, chart_vectors(other.rules_version))
                if len(ohits) == 1:
                    matched["legacy"] += 1
                    by_edition_tier[(f"legacy→{other.rules_version}", ohits[0])] += 1
                    legacy_hit = True
                    break
            if not legacy_hit:
                unmatched[observed] += 1
                matched["unmatched"] += 1

    print("# Tier chart reconciliation\n")
    print(f"Groups (edition×division×role×dance with placements): {len(piv):,}")
    print(f"No rules edition for date: {no_edition}")
    print("\n## Match summary\n")
    for k, v in matched.most_common():
        print(f"- `{k}`: {v:,}")

    print("\n## Exact matches by (rules_version, tier)\n")
    print("| rules_version | tier | groups |")
    print("|---|---:|---:|")
    for (ver, tier), n in sorted(by_edition_tier.items(), key=lambda x: (-x[1], x[0])):
        print(f"| {ver} | {tier} | {n:,} |")

    print("\n## Top unmatched observed vectors\n")
    print("| vector | groups |")
    print("|---|---:|")
    for vec, n in unmatched.most_common(25):
        print(f"| `{vec}` | {n:,} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
