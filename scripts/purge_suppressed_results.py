#!/usr/bin/env python3
"""Purge ``core.results`` (+ export CSV) for active ``suppress_results`` corrections.

Use after adding/updating a YAML under ``transform/knowledge/corrections/`` so the
incomplete edition disappears immediately (preprocess alone only affects the next
load). Rebuilds event catalog and refreshes completed_event_editions MV.

Examples:
    python scripts/purge_suppressed_results.py --dry-run
    python scripts/purge_suppressed_results.py --apply
    python scripts/purge_suppressed_results.py --apply --export
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from transform.knowledge.corrections import (  # noqa: E402
    drop_suppressed_results,
    suppress_results_rules,
)


def _connect():
    load_dotenv(PROJECT_ROOT / ".env")
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("DB_SSLMODE", "require"),
    )


def _delete_sql(rule: dict) -> tuple[str, tuple]:
    clauses = ["event_year = %s"]
    params: list = [rule["event_year"]]
    if rule.get("event_month") is not None:
        clauses.append("event_month = %s")
        params.append(rule["event_month"])
    if rule.get("event_id") is not None:
        clauses.append("event_id = %s")
        params.append(int(rule["event_id"]))
    elif rule.get("event_name_substrings"):
        # Fallback when event_id unknown — match event_name_raw.
        sub = rule["event_name_substrings"][0]
        clauses.append("LOWER(COALESCE(event_name_raw, '')) LIKE %s")
        params.append(f"%{sub}%")
    else:
        raise ValueError(f"{rule.get('id')}: need event_id or event_name_substrings")
    sql = f"DELETE FROM core.results WHERE {' AND '.join(clauses)}"
    return sql, tuple(params)


def purge_db(*, dry_run: bool) -> int:
    rules = suppress_results_rules()
    if not rules:
        print("No active suppress_results corrections.")
        return 0
    total = 0
    with _connect() as conn:
        with conn.cursor() as cur:
            for rule in rules:
                sql, params = _delete_sql(rule)
                where = sql.split("WHERE", 1)[1]
                cur.execute(f"SELECT count(*) FROM core.results WHERE {where}", params)
                n = int(cur.fetchone()[0])
                print(
                    f"{'[dry-run] would delete' if dry_run else 'delete'} "
                    f"{n} rows for {rule['id']} "
                    f"(event_id={rule.get('event_id')}, "
                    f"{rule['event_year']}-{rule.get('event_month') or '*'})"
                )
                if not dry_run and n:
                    cur.execute(sql, params)
                    total += n
            if not dry_run and total:
                catalog_n, edition_n = rebuild_event_catalog(conn)
                print(f"Rebuilt event catalog: {catalog_n} events, {edition_n} editions")
                cur.execute(
                    """
                    SELECT 1
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'export'
                      AND p.proname = 'refresh_completed_event_editions'
                    """
                )
                if cur.fetchone():
                    cur.execute("SELECT export.refresh_completed_event_editions()")
                    print("Refreshed export.completed_event_editions")
                else:
                    print(
                        "Skip MV refresh — export.refresh_completed_event_editions() "
                        "not installed on this database"
                    )
                cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    return total


def purge_csv(data_dir: Path, *, dry_run: bool) -> int:
    path = data_dir / "dancers_results_info.csv"
    if not path.exists():
        print(f"Skip CSV — missing {path}")
        return 0
    df = pd.read_csv(path, dtype=str, low_memory=False)
    kept, n = drop_suppressed_results(df)
    print(
        f"{'[dry-run] would drop' if dry_run else 'dropped'} "
        f"{n} CSV result rows ({len(df)} → {len(kept)})"
    )
    if not dry_run and n:
        kept.to_csv(path, index=False)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Export CSV directory (default: ./data)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="After apply, run export.py --output-dir data",
    )
    parser.add_argument(
        "--skip-csv",
        action="store_true",
        help="Only purge Supabase (CSV refreshed by --export)",
    )
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        print("Pass --dry-run or --apply", file=sys.stderr)
        return 2

    rules = suppress_results_rules()
    print(f"Active suppress_results rules: {len(rules)}")
    for r in rules:
        print(f"  - {r['id']}")

    dry = bool(args.dry_run) and not args.apply
    purge_db(dry_run=dry)
    if not args.skip_csv:
        purge_csv(args.data_dir, dry_run=dry)

    if args.apply and args.export and not dry:
        import subprocess

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "export.py"),
            "--output-dir",
            str(args.data_dir),
        ]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
