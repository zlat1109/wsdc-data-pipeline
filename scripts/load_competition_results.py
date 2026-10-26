#!/usr/bin/env python3
"""Load Competition Results enrichment into ``core.cr_*`` tables.

Inputs stay local (parquet). Only scrape-originated WSDC rows are loaded —
prelims/semis/quarters, unscored finalists, partners, judge marks, other divs.
Never invents dancers or editions (nullable FKs + match_status).

Usage:
    python scripts/load_competition_results.py \\
        --cr-path ~/Downloads/"Competition Results"/results.parquet --dry-run

    python scripts/load_competition_results.py \\
        --cr-path … --apply --migrate
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"
REPORT_PATH = REPORT_DIR / "cr_load_report.json"

TABLE_ORDER = [
    ("cr_editions", "core.cr_editions"),
    ("cr_divisions", "core.cr_divisions"),
    ("cr_rounds", "core.cr_rounds"),
    ("cr_round_results", "core.cr_round_results"),
    ("cr_final_couples", "core.cr_final_couples"),
    ("cr_judge_marks", "core.cr_judge_marks"),
]

# Columns written via COPY (exclude GENERATED columns).
COPY_COLUMNS: dict[str, list[str]] = {
    "cr_editions": [
        "cr_edition_id",
        "wsdc_event_id",
        "cr_name",
        "cr_date",
        "edition_id",
        "match_status",
        "scoring_source",
        "filing_year",
        "filing_month",
        "canonical_event_id",
        "load_id",
    ],
    "cr_divisions": [
        "cr_division_id",
        "cr_edition_id",
        "raw_division",
        "level",
        "category",
        "label",
        "competition_bucket",
    ],
    "cr_rounds": [
        "cr_round_id",
        "cr_division_id",
        "round",
        "source_url",
        "total_competitors",
    ],
    "cr_round_results": [
        "cr_round_result_id",
        "cr_round_id",
        "role",
        "cr_identity",
        "dancer_id",
        "competitor_name",
        "place",
        "callback",
        "partner_cr_identity",
        "partner_dancer_id",
    ],
    "cr_final_couples": [
        "couple_id",
        "cr_round_id",
        "leader_result_id",
        "follower_result_id",
        "place",
    ],
    "cr_judge_marks": [
        "cr_round_result_id",
        "couple_id",
        "judge_name",
        "mark",
    ],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--cr-path",
        type=Path,
        default=os.environ.get("CR_RESULTS_PATH"),
        help="Competition Results results.parquet (or CR_RESULTS_PATH)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--migrate",
        action="store_true",
        help="run db/apply.py before --apply",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=REPORT_PATH,
        help="dry-run / apply report JSON path",
    )
    return p.parse_args(argv)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_parquet_filtered(path: Path):
    import duckdb

    con = duckdb.connect()
    # Only enrichment rows (WSDC + scrape-originated).
    return con.execute(
        f"""
        SELECT *
        FROM read_parquet('{path}')
        WHERE starts_with(event_edition_id, 'wsdc:')
          AND result_from_other_source
        """
    ).df()


def fetch_editions(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT edition_id, event_id, event_year, event_month
            FROM core.event_editions
            """
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_dancer_ids(conn) -> set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT dancer_id FROM core.dancers")
        return {int(r[0]) for r in cur.fetchall()}


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "t" if v else "f"
    return str(v)


def rows_to_csv(rows: Sequence[dict[str, Any]], columns: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for row in rows:
        w.writerow([_csv_cell(row.get(c)) for c in columns])
    return buf.getvalue().encode("utf-8")


def truncate_cr_tables(conn) -> None:
    with conn.cursor() as cur:
        # Child → parent order via CASCADE from editions root.
        cur.execute(
            """
            TRUNCATE
                core.cr_judge_marks,
                core.cr_final_couples,
                core.cr_round_results,
                core.cr_rounds,
                core.cr_divisions,
                core.cr_editions
            RESTART IDENTITY
            """
        )


def insert_load_row(
    conn,
    *,
    source_file: str,
    sha: str,
    row_counts: dict[str, int],
    match_stats: dict[str, Any],
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO core.cr_loads (source_file, file_sha256, row_counts, match_stats)
            VALUES (%s, %s, %s::jsonb, %s::jsonb)
            RETURNING load_id
            """,
            (
                source_file,
                sha,
                json.dumps(row_counts),
                json.dumps(match_stats, default=str),
            ),
        )
        return int(cur.fetchone()[0])


def copy_table(
    conn,
    table: str,
    columns: list[str],
    rows: Sequence[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    cols_sql = ", ".join(columns)
    payload = rows_to_csv(rows, columns)
    with conn.cursor() as cur:
        with cur.copy(
            f"COPY {table} ({cols_sql}) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')"
        ) as copy:
            copy.write(payload)
    return len(rows)


def apply_tables(conn, tables, *, source_file: str, sha: str) -> int:
    counts = tables.counts()
    load_id = insert_load_row(
        conn,
        source_file=source_file,
        sha=sha,
        row_counts=counts,
        match_stats=tables.stats,
    )
    truncate_cr_tables(conn)

    editions = [{**r, "load_id": load_id} for r in tables.editions]
    mapping = {
        "cr_editions": editions,
        "cr_divisions": tables.divisions,
        "cr_rounds": tables.rounds,
        "cr_round_results": tables.round_results,
        "cr_final_couples": tables.final_couples,
        "cr_judge_marks": tables.judge_marks,
    }
    for key, fq in TABLE_ORDER:
        n = copy_table(conn, fq, COPY_COLUMNS[key], mapping[key])
        print(f"  COPY {fq}: {n:,}")

    with conn.cursor() as cur:
        cur.execute(
            """
            ANALYZE core.cr_editions, core.cr_divisions, core.cr_rounds,
                     core.cr_round_results, core.cr_final_couples, core.cr_judge_marks
            """
        )
    return load_id


def acceptance_checks(tables) -> dict[str, Any]:
    counts = tables.counts()
    stats = tables.stats
    pure_wsdc_leaked = 0  # filter already applied upstream
    matched = int(stats.get("matched_editions") or 0)
    unmatched = int(stats.get("unmatched_editions") or 0)
    # Scrape-layer editions are ~600–700; require a solid match rate, not a
    # fixed absolute floor from the full CR edition catalog.
    match_rate = matched / max(matched + unmatched, 1)
    return {
        "ok": (
            counts["cr_editions"] >= 500
            and match_rate >= 0.95
            and counts["cr_round_results"] > 100_000
            and counts["cr_final_couples"] > 10_000
        ),
        "matched_editions": matched,
        "unmatched_editions": unmatched,
        "match_rate": round(match_rate, 4),
        "final_couples_incomplete": stats.get("final_couples_incomplete"),
        "pure_wsdc_leaked": pure_wsdc_leaked,
        "counts": counts,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply.", file=sys.stderr)
        return 2
    if not args.cr_path:
        print("Missing --cr-path / CR_RESULTS_PATH.", file=sys.stderr)
        return 2
    cr_path = Path(args.cr_path).expanduser()
    if not cr_path.exists():
        print(f"Missing parquet: {cr_path}", file=sys.stderr)
        return 2

    if args.migrate or args.apply:
        rc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "db" / "apply.py")],
            cwd=str(PROJECT_ROOT),
            check=False,
        ).returncode
        if rc != 0:
            return rc

    print(f"Reading {cr_path} …")
    sha = file_sha256(cr_path)
    df = load_parquet_filtered(cr_path)
    print(f"Filtered enrichment rows: {len(df):,}")

    from connection import connect  # type: ignore
    from transform.competition_results.build import build_cr_tables

    with connect() as conn:
        editions = fetch_editions(conn)
        known = fetch_dancer_ids(conn)
        print(
            f"core.event_editions={len(editions):,}  core.dancers={len(known):,}"
        )
        tables = build_cr_tables(df, editions=editions, known_dancer_ids=known)
        checks = acceptance_checks(tables)
        print("Counts:", json.dumps(tables.counts(), indent=2))
        print(
            f"Editions matched={tables.stats.get('matched_editions')} "
            f"unmatched={tables.stats.get('unmatched_editions')} "
            f"incomplete_couples={tables.stats.get('final_couples_incomplete')}"
        )

        unmatched_sample = [
            {
                "cr_edition_id": e["cr_edition_id"],
                "cr_name": e["cr_name"],
                "wsdc_event_id": e["wsdc_event_id"],
                "filing_year": e["filing_year"],
                "filing_month": e["filing_month"],
                "canonical_event_id": e["canonical_event_id"],
            }
            for e in tables.editions
            if e["match_status"] == "unmatched"
        ][:50]

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_file": str(cr_path),
            "file_sha256": sha,
            "counts": tables.counts(),
            "stats": tables.stats,
            "acceptance": checks,
            "unmatched_editions_sample": unmatched_sample,
            "mode": "apply" if args.apply else "dry-run",
        }

        if args.apply:
            if not checks["ok"]:
                print("Acceptance checks failed — aborting apply.", file=sys.stderr)
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(
                    json.dumps(payload, indent=2, default=str) + "\n"
                )
                return 1
            print("Applying (full replace) …")
            load_id = apply_tables(
                conn, tables, source_file=str(cr_path), sha=sha
            )
            conn.commit()
            payload["load_id"] = load_id
            print(f"Applied load_id={load_id}")
        else:
            print("DRY-RUN — no writes.")

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(f"Report → {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
