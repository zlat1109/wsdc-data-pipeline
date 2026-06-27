#!/usr/bin/env python3
"""Merge duplicate WSDC event_id rows when geography matches.

Usage:
    python scripts/merge_event_ids.py --dry-run
    python scripts/merge_event_ids.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from connection import connect  # noqa: E402
from transform.geography.geo_event import classify_event_id_pair, geo_key  # noqa: E402
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP  # noqa: E402

EVENT_GEO_SQL = """
SELECT
    r.event_id,
    mode() WITHIN GROUP (ORDER BY l.event_city) AS city,
    mode() WITHIN GROUP (ORDER BY l.event_state) AS state,
    mode() WITHIN GROUP (ORDER BY l.event_country) AS country,
    count(*)::int AS result_rows
FROM core.results r
LEFT JOIN core.locations l ON l.location_id = r.location_id
WHERE r.event_id = ANY(%s)
GROUP BY r.event_id
"""


def fetch_event_geos(cur, event_ids: list[int]) -> dict[int, dict]:
    cur.execute(EVENT_GEO_SQL, (event_ids,))
    cols = [d.name for d in cur.description]
    out: dict[int, dict] = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row, strict=True))
        eid = int(rec["event_id"])
        rec["geo_key"] = geo_key(rec.get("city"), rec.get("state"), rec.get("country"))
        out[eid] = rec
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not MERGE_EVENT_ID_MAP:
        print("MERGE_EVENT_ID_MAP is empty — nothing to do.")
        return

    all_ids = sorted(set(MERGE_EVENT_ID_MAP.keys()) | set(MERGE_EVENT_ID_MAP.values()))
    plans: list[dict] = []

    with connect() as conn:
        with conn.cursor() as cur:
            geos = fetch_event_geos(cur, all_ids)

            for source_id, canonical_id in sorted(MERGE_EVENT_ID_MAP.items()):
                src = geos.get(source_id, {})
                can = geos.get(canonical_id, {})
                action = classify_event_id_pair(
                    source_id,
                    canonical_id,
                    src.get("geo_key", ""),
                    can.get("geo_key", ""),
                )
                cur.execute(
                    "SELECT count(*) FROM core.results WHERE event_id = %s",
                    (source_id,),
                )
                row_count = int(cur.fetchone()[0])
                plans.append(
                    {
                        "source_id": source_id,
                        "canonical_id": canonical_id,
                        "action": action,
                        "rows": row_count,
                        "source_geo": src.get("geo_key"),
                        "canonical_geo": can.get("geo_key"),
                    }
                )

            blocked = [p for p in plans if p["action"] != "merge_candidate"]
            if blocked:
                print("Blocked merges (geo gate):")
                for p in blocked:
                    print(
                        f"  {p['source_id']} -> {p['canonical_id']}: "
                        f"{p['action']} ({p['source_geo']} vs {p['canonical_geo']})"
                    )
                sys.exit(1)

            total_rows = sum(p["rows"] for p in plans)
            print(f"Merge plan: {len(plans)} pairs, {total_rows} result rows to remap")
            for p in plans:
                print(
                    f"  {p['source_id']} -> {p['canonical_id']}: "
                    f"{p['rows']} rows ({p['source_geo']})"
                )

            if args.dry_run:
                print("\nDry run — no changes applied.")
                return

            for p in plans:
                source_id = p["source_id"]
                canonical_id = p["canonical_id"]
                cur.execute(
                    """
                    UPDATE core.results
                    SET event_id = %s
                    WHERE event_id = %s
                    """,
                    (canonical_id, source_id),
                )
                cur.execute(
                    """
                    SELECT DISTINCT event_name_raw
                    FROM core.results
                    WHERE event_id = %s AND event_name_raw IS NOT NULL
                    """,
                    (canonical_id,),
                )
                for (alias,) in cur.fetchall():
                    if not alias or not str(alias).strip():
                        continue
                    cur.execute(
                        """
                        INSERT INTO core.event_aliases (alias, event_id)
                        VALUES (%s, %s)
                        ON CONFLICT (alias) DO UPDATE SET event_id = EXCLUDED.event_id
                        """,
                        (str(alias).strip(), canonical_id),
                    )
                cur.execute(
                    """
                    UPDATE core.event_catalog
                    SET registry_status = coalesce(registry_status, 'merged')
                    WHERE event_id = %s
                    """,
                    (source_id,),
                )

            rebuild_event_catalog(conn)
            cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")
        conn.commit()

    print("\nMerge complete. Run export.py to refresh CSVs.")


if __name__ == "__main__":
    main()
