#!/usr/bin/env python3
"""Initial load: CSV files -> staging -> core + points history from changed_*.csv.

Usage:
    python backfill.py
    python backfill.py --data-dir "/path/to/WSDC Points"
    python backfill.py --skip-points-history
    python backfill.py --roles-only --run-id 40
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from connection import connect  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402
from seed_event_aliases import prepare_event_resolution  # noqa: E402
from staging_loader import load_staging_from_dir  # noqa: E402
from watermark import refresh_watermark  # noqa: E402


def read_sql(name: str) -> str:
    return (PROJECT_ROOT / "db" / "sql" / name).read_text(encoding="utf-8")


def start_run(cur, source: str) -> int:
    cur.execute(
        """
        INSERT INTO history.parse_runs (source, status)
        VALUES (%s, 'running')
        RETURNING run_id
        """,
        (source,),
    )
    return cur.fetchone()[0]


def finish_run(cur, run_id: int, counts: dict[str, int], conn) -> None:
    cur.execute(
        """
        UPDATE history.parse_runs
        SET finished_at = %s,
            status = 'success',
            rows_results = %s,
            rows_points = %s
        WHERE run_id = %s
        """,
        (
            datetime.now(timezone.utc),
            counts.get("dancers_results_info.csv"),
            counts.get("dancers_points_info.csv"),
            run_id,
        ),
    )
    conn.commit()
    wm = refresh_watermark(conn, run_id)
    print(f"Watermark updated to {wm}")


def mark_run_success(cur, run_id: int, conn) -> None:
    cur.execute(
        """
        UPDATE history.parse_runs
        SET finished_at = %s, status = 'success'
        WHERE run_id = %s AND status = 'running'
        """,
        (datetime.now(timezone.utc), run_id),
    )
    conn.commit()


def resolve_backfill_run_id(cur, explicit: int | None) -> int:
    if explicit is not None and explicit > 0:
        return explicit
    cur.execute(
        """
        SELECT run_id FROM history.parse_runs
        WHERE source = 'backfill' AND status = 'running'
        ORDER BY run_id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute("SELECT COALESCE(MAX(run_id), 0) FROM history.parse_runs")
    run_id = int(cur.fetchone()[0])
    if run_id <= 0:
        sys.exit("No parse_runs row — run full backfill first")
    return run_id


def promote_staging_to_core(conn, cur) -> tuple[int, int, int, int]:
    """Mirror load.py promote path (core snapshot + results + catalog)."""
    cur.execute(read_sql("promote_core.sql"))
    alias_count, orphan_event_count = prepare_event_resolution(conn)
    cur.execute(read_sql("promote_core_results.sql"))
    enrich_core_known_events(conn)
    catalog_count, edition_count = rebuild_event_catalog(conn)
    cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")
    return alias_count, orphan_event_count, catalog_count, edition_count


def backfill_points_history(cur, data_dir: Path, run_id: int) -> None:
    changed_path = data_dir / "changed_dancers_points_info.csv"
    if not changed_path.exists():
        changed_path = data_dir / "changed_dancer_points_info.csv"
    if not changed_path.exists():
        print("No changed_* points CSV found — skipping points history")
        return
    print(f"Building points history from {changed_path.name} ...")
    cur.execute("TRUNCATE history.dancer_points_history")
    cur.execute(read_sql("backfill_points_history.sql"), {"run_id": run_id})


def backfill_legacy_history_subprocess(data_dir: Path, run_id: int, conn) -> None:
    roles_changed = data_dir / "changed_dancer_role_info.csv"
    if not roles_changed.exists():
        print("No changed_dancer_role_info.csv found — skipping role/name history")
        return
    print(
        f"Building role + name history from {roles_changed.name} "
        "(pandas — SQL times out on 3M+ rows) ..."
    )
    conn.commit()
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "split_legacy_role_history.py"),
            "--csv",
            str(roles_changed),
            "--run-id",
            str(run_id),
            "--apply",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM history.dancer_roles_history")
        role_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM history.dancer_names_history")
        name_count = cur.fetchone()[0]
        print(f"  role history rows: {role_count}")
        print(f"  name history rows: {name_count}")


def print_core_counts(cur) -> None:
    tables = [
        "core.dancers",
        "core.locations",
        "core.events",
        "core.event_instances",
        "core.dancer_points",
        "core.dancer_roles",
        "core.results",
        "history.dancer_points_history",
        "history.dancer_roles_history",
        "history.dancer_names_history",
    ]
    print("\nRow counts in Supabase:")
    for table in tables:
        cur.execute(f"SELECT count(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory with WSDC CSV files",
    )
    parser.add_argument(
        "--skip-points-history",
        action="store_true",
        help="Skip loading history from changed_* points CSV",
    )
    parser.add_argument(
        "--skip-roles-history",
        action="store_true",
        help="Skip loading role + name history from changed_dancer_role_info.csv",
    )
    parser.add_argument(
        "--roles-only",
        action="store_true",
        help="Only rebuild role + name history from changed_dancer_role_info.csv (skip staging/core)",
    )
    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="parse_runs id for history backfill (default: latest running backfill)",
    )
    args = parser.parse_args()

    if args.roles_only:
        roles_changed = args.data_dir / "changed_dancer_role_info.csv"
        if not roles_changed.exists():
            sys.exit(f"Missing {roles_changed}")
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '0'")
                run_id = resolve_backfill_run_id(cur, args.run_id)
            conn.commit()
            print(f"Legacy history only (run_id={run_id}) ...")
            backfill_legacy_history_subprocess(args.data_dir, run_id, conn)
            with conn.cursor() as cur:
                mark_run_success(cur, run_id, conn)
        print("\nLegacy role + name history backfill complete.")
        return

    print(f"Data directory: {args.data_dir}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0'")
        conn.commit()

        print("Loading CSVs into staging ...")
        staging_counts = load_staging_from_dir(
            conn,
            args.data_dir,
            skip_changed_roles=True,
        )
        for name, count in staging_counts.items():
            print(f"  {name}: {count} rows")

        with conn.cursor() as cur:
            run_id = start_run(cur, "backfill")
            conn.commit()
            print(f"parse_run id: {run_id}")

            print("Promoting staging -> core ...")
            alias_count, orphan_count, catalog_count, edition_count = (
                promote_staging_to_core(conn, cur)
            )
            print(
                f"Event aliases seeded: {alias_count}; "
                f"result-only events: {orphan_count}."
            )
            print(f"Event catalog: {catalog_count} events, {edition_count} editions.")

            if not args.skip_points_history:
                backfill_points_history(cur, args.data_dir, run_id)

            if not args.skip_roles_history:
                backfill_legacy_history_subprocess(args.data_dir, run_id, conn)

            finish_run(cur, run_id, staging_counts, conn)
            print_core_counts(cur)

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()
