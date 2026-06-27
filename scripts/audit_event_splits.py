#!/usr/bin/env python3
"""Audit event_name splits with geo-aware merge classification.

Usage:
    python scripts/audit_event_splits.py
    python scripts/audit_event_splits.py --output-dir data/quality_reports
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.geography.geo_event import (  # noqa: E402
    classify_event_id_pair,
    geo_key,
    metro_label,
)


SPLIT_SQL = """
WITH per_event AS (
    SELECT
        r.event_name_raw,
        r.event_id,
        c.canonical_name,
        mode() WITHIN GROUP (ORDER BY l.event_city) AS city,
        mode() WITHIN GROUP (ORDER BY l.event_state) AS state,
        mode() WITHIN GROUP (ORDER BY l.event_country) AS country,
        count(*)::int AS result_rows,
        min(r.event_year) AS first_year,
        max(r.event_year) AS last_year
    FROM core.results r
    JOIN core.event_catalog c ON c.event_id = r.event_id
    LEFT JOIN core.locations l ON l.location_id = r.location_id
    WHERE NULLIF(trim(r.event_name_raw), '') IS NOT NULL
    GROUP BY r.event_name_raw, r.event_id, c.canonical_name
),
split_names AS (
    SELECT event_name_raw
    FROM per_event
    GROUP BY event_name_raw
    HAVING count(DISTINCT event_id) > 1
)
SELECT p.*
FROM per_event p
JOIN split_names s ON s.event_name_raw = p.event_name_raw
ORDER BY p.event_name_raw, p.result_rows DESC
"""


def classify_splits(rows: list[dict]) -> list[dict]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_name[row["event_name_raw"]].append(row)

    reports: list[dict] = []
    for raw_name, events in sorted(by_name.items()):
        for ev in events:
            ev["geo_key"] = geo_key(ev.get("city"), ev.get("state"), ev.get("country"))
            cluster = ev["geo_key"].removeprefix("metro:") if ev["geo_key"].startswith("metro:") else None
            ev["metro_label"] = metro_label(cluster) if cluster else None

        actions: set[str] = set()
        pairs: list[dict] = []
        for i, a in enumerate(events):
            for b in events[i + 1 :]:
                action = classify_event_id_pair(
                    int(a["event_id"]),
                    int(b["event_id"]),
                    a["geo_key"],
                    b["geo_key"],
                )
                actions.add(action)
                pairs.append(
                    {
                        "event_id_a": int(a["event_id"]),
                        "event_id_b": int(b["event_id"]),
                        "geo_key_a": a["geo_key"],
                        "geo_key_b": b["geo_key"],
                        "action": action,
                    }
                )

        if "keep_separate" in actions:
            overall = "keep_separate"
        elif actions == {"merge_candidate"}:
            overall = "merge_candidate"
        elif "merge_candidate" in actions:
            overall = "manual_review"
        else:
            overall = "manual_review"

        reports.append(
            {
                "event_name_raw": raw_name,
                "event_count": len(events),
                "total_result_rows": sum(int(e["result_rows"]) for e in events),
                "overall_action": overall,
                "events": events,
                "pairs": pairs,
            }
        )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "quality_reports",
    )
    args = parser.parse_args()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SPLIT_SQL)
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    reports = classify_splits(rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split_name_count": len(reports),
        "merge_candidate": sum(1 for r in reports if r["overall_action"] == "merge_candidate"),
        "keep_separate": sum(1 for r in reports if r["overall_action"] == "keep_separate"),
        "manual_review": sum(1 for r in reports if r["overall_action"] == "manual_review"),
        "splits": reports,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.output_dir / f"event_splits_{stamp}.json"
    latest_path = args.output_dir / "event_splits_latest.json"
    payload = json.dumps(summary, ensure_ascii=False, indent=2, default=str)
    out_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")

    print(f"Split event names: {summary['split_name_count']}")
    print(f"  merge_candidate: {summary['merge_candidate']}")
    print(f"  keep_separate:   {summary['keep_separate']}")
    print(f"  manual_review:   {summary['manual_review']}")
    print(f"Report: {out_path}")


if __name__ == "__main__":
    main()
