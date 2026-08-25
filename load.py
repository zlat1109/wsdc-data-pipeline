#!/usr/bin/env python3
"""Weekly load: CSV -> staging -> history diff -> core refresh.

Usage:
    python load.py --data-dir "/path/to/WSDC Points"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from build_event_catalog import rebuild_event_catalog  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402
from seed_event_aliases import prepare_event_resolution  # noqa: E402
from staging_loader import load_staging_from_dir  # noqa: E402
from watermark import refresh_watermark  # noqa: E402


def read_sql(name: str) -> str:
    return (PROJECT_ROOT / "db" / "sql" / name).read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--source",
        default="local",
        choices=["local", "github-actions"],
    )
    args = parser.parse_args()

    run_id: int | None = None
    alias_count = 0
    orphan_event_count = 0
    catalog_count = 0
    edition_count = 0

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '30min'")

        staging_counts = load_staging_from_dir(conn, args.data_dir)

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO history.parse_runs (source, status)
                    VALUES (%s, 'running')
                    RETURNING run_id
                    """,
                    (args.source,),
                )
                run_id = cur.fetchone()[0]

                cur.execute(
                    read_sql("record_weekly_points_history.sql"),
                    {"run_id": run_id},
                )
                cur.execute(
                    read_sql("record_weekly_roles_history.sql"),
                    {"run_id": run_id},
                )
                cur.execute(
                    read_sql("record_weekly_names_history.sql"),
                    {"run_id": run_id},
                )
                cur.execute(read_sql("promote_core.sql"))
                from refresh_events_list_current import ensure_events_list_after_load

                list_report = ensure_events_list_after_load(conn)
                print(
                    "Events list: "
                    f"action={list_report.get('action')} "
                    f"current={list_report.get('current_after', list_report.get('current_before'))}"
                )
                alias_count, orphan_event_count = prepare_event_resolution(conn)
                cur.execute(read_sql("promote_core_results.sql"))
                enrich_core_known_events(conn)
                catalog_count, edition_count = rebuild_event_catalog(conn)
                from edition_calendar import ensure_edition_calendar_after_load

                cal_report = ensure_edition_calendar_after_load(conn)
                print(
                    f"Edition calendar: action={cal_report.get('action')} "
                    f"durable={cal_report.get('durable_after', cal_report.get('durable_before'))}"
                )
                from build_edition_tiers import rebuild_edition_tiers

                tier_rows, tier_status = rebuild_edition_tiers(conn)
                print(
                    f"Edition tiers: {tier_rows:,} rows "
                    f"(matched={tier_status.get('matched', 0):,}, "
                    f"legacy={tier_status.get('legacy_chart', 0):,}, "
                    f"unmatched={tier_status.get('unmatched', 0):,})"
                )

                from edition_location_baseline import (
                    refresh_completed_event_editions_mv,
                    sync_edition_location_baseline_after_load,
                )

                baseline_report = sync_edition_location_baseline_after_load(conn)
                refresh_completed_event_editions_mv(conn)
                drift_n = int(baseline_report.get("drift_count", 0))
                added_n = int(baseline_report.get("auto_added", 0))
                print(
                    f"Edition location baseline: drifts={drift_n}, auto_added={added_n}"
                )
                report_path = PROJECT_ROOT / "data" / "quality_reports"
                report_path.mkdir(parents=True, exist_ok=True)
                out = report_path / "edition_location_baseline_drift.json"
                payload = {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "drift_count": drift_n,
                    "auto_added": added_n,
                    "drifts": baseline_report.get("drifts", []),
                }
                out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                if drift_n:
                    print(f"Baseline drift report: {out}")

                cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")

                cur.execute(
                    """
                    UPDATE history.parse_runs
                    SET finished_at = %s, status = 'success',
                        rows_results = %s, rows_points = %s
                    WHERE run_id = %s
                    """,
                    (
                        datetime.now(timezone.utc),
                        staging_counts.get("dancers_results_info.csv"),
                        staging_counts.get("dancers_points_info.csv"),
                        run_id,
                    ),
                )
            conn.commit()
            wm = refresh_watermark(conn, run_id)
            print(f"Watermark updated to {wm}")
        except Exception:
            conn.rollback()
            if run_id is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE history.parse_runs
                        SET finished_at = %s, status = 'failed'
                        WHERE run_id = %s AND status = 'running'
                        """,
                        (datetime.now(timezone.utc), run_id),
                    )
                conn.commit()
            raise

    print(f"Load complete (run_id={run_id}).")
    print(f"Event aliases seeded: {alias_count}; result-only events: {orphan_event_count}.")
    print(f"Event catalog: {catalog_count} events, {edition_count} editions.")


if __name__ == "__main__":
    main()
