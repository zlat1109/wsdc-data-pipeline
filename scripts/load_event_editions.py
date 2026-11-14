#!/usr/bin/env python3
"""Load Todd Event Editions enrichment into core (attributes, status, metros…).

WSDC rows only. ``core.event_editions`` remains SoT for occurred editions.
Blocking reconciliation gate uses ``data/reference/event_editions_decisions.yaml``.

``--apply`` runs in a single psycopg connection transaction (commit on clean
exit from ``with connect()``, rollback on exception). Truncate + COPY + metro
backfill + CR official_id update are atomic.

After weekly ``promote_core`` (which TRUNCATEs ``core.locations``), re-run with
``--with-metros-venues`` so ``locations.metro_id`` is restored.

Usage:
    python scripts/load_event_editions.py \\
        --ee-path ~/Downloads/"Analytical Datasets"/"Event Editions"/event_editions.parquet \\
        --dry-run

    python scripts/load_event_editions.py --ee-path … --apply --migrate \\
        --with-metros-venues --with-officials
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
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"
REPORT_PATH = REPORT_DIR / "event_editions_recon.json"
DEFAULT_EE = Path.home() / "Downloads" / "Analytical Datasets" / "Event Editions" / "event_editions.parquet"

COPY_COLUMNS: dict[str, list[str]] = {
    "edition_attributes": [
        "event_id",
        "event_year",
        "event_month",
        "todd_edition_id",
        "match_kind",
        "venue_id",
        "registry_status",
        "scoring_software",
        "coordinates_precision",
        "date_precision",
        "accommodation_hotel",
        "wsdc_event_name",
        "row_info",
        "load_id",
    ],
    "edition_status_history": [
        "event_id",
        "event_year",
        "event_month",
        "todd_edition_id",
        "edition_status",
        "cancelled_covid",
        "event_edition_name",
        "start_date",
        "end_date",
        "registry_status",
        "city",
        "region",
        "country",
        "load_id",
    ],
    "metros": ["metro_id", "name", "country", "latitude", "longitude"],
    "venues": [
        "venue_id",
        "name",
        "name_normalized",
        "address",
        "venue_type",
        "venue_url",
        "latitude",
        "longitude",
        "location_id",
    ],
    "officials": ["official_id", "canonical_name", "name_normalized", "dancer_id"],
    "edition_officials": [
        "event_id",
        "event_year",
        "event_month",
        "official_id",
        "role",
        "rounds",
        "panel_order",
    ],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ee-path",
        type=Path,
        default=os.environ.get("EE_PATH", DEFAULT_EE),
        help="Event Editions event_editions.parquet (or EE_PATH)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--migrate", action="store_true")
    p.add_argument("--with-metros-venues", action="store_true")
    p.add_argument("--with-officials", action="store_true")
    p.add_argument(
        "--check-conflicts",
        action="store_true",
        help="live soft-FK orphan probes (no load)",
    )
    p.add_argument("--report", type=Path, default=REPORT_PATH)
    p.add_argument(
        "--decisions",
        type=Path,
        default=PROJECT_ROOT / "data" / "reference" / "event_editions_decisions.yaml",
    )
    return p.parse_args(argv)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_parquet(path: Path):
    import duckdb

    con = duckdb.connect()
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _ee_src AS SELECT * FROM read_parquet(?)",
        [str(path)],
    )
    return con.execute("SELECT * FROM _ee_src").df()


def read_manifest(ee_path: Path) -> dict[str, Any]:
    manifest = ee_path.parent / "export_manifest.json"
    if not manifest.is_file():
        return {}
    return json.loads(manifest.read_text(encoding="utf-8"))


def fetch_editions(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT edition_id, event_id, event_year, event_month, "
            "place_city, start_date, end_date FROM core.event_editions"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_locations(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT location_id, event_city, event_state, event_country "
            "FROM core.locations"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_dancers(conn) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT dancer_id, dancer_name FROM core.dancers")
        out: list[dict[str, Any]] = []
        for dancer_id, dancer_name in cur.fetchall():
            parts = str(dancer_name or "").strip().split(None, 1)
            first = parts[0] if parts else ""
            last = parts[1] if len(parts) > 1 else ""
            out.append(
                {
                    "dancer_id": int(dancer_id),
                    "first_name": first,
                    "last_name": last,
                }
            )
        return out


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


def copy_table(conn, table: str, columns: list[str], rows: Sequence[dict[str, Any]]) -> int:
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


def truncate_ee_tables(conn, *, with_metros_venues: bool, with_officials: bool) -> None:
    with conn.cursor() as cur:
        if with_officials:
            cur.execute("TRUNCATE core.edition_officials RESTART IDENTITY")
            cur.execute("DELETE FROM core.officials")
        # Soft refs / FK from locations.metro_id → metros: clear then DELETE
        # (TRUNCATE metros fails while locations FK exists, even when all NULL).
        cur.execute("UPDATE core.edition_attributes SET venue_id = NULL")
        if with_metros_venues:
            cur.execute("UPDATE core.locations SET metro_id = NULL")
            cur.execute("DELETE FROM core.venues")
            cur.execute("DELETE FROM core.metros")
        cur.execute(
            "TRUNCATE core.edition_attributes, core.edition_status_history RESTART IDENTITY"
        )


def insert_load_row(
    conn,
    *,
    source_file: str,
    sha: str,
    built_at: str | None,
    git_commit: str | None,
    row_counts: dict[str, int],
    match_stats: dict[str, Any],
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO core.ee_loads
                (source_file, file_sha256, built_at, git_commit, row_counts, match_stats)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING load_id
            """,
            (
                source_file,
                sha,
                built_at,
                git_commit,
                json.dumps(row_counts),
                json.dumps(match_stats, default=str),
            ),
        )
        return int(cur.fetchone()[0])


def apply_tables(
    conn,
    tables,
    *,
    source_file: str,
    sha: str,
    manifest: dict[str, Any],
    with_metros_venues: bool,
    with_officials: bool,
) -> int:
    counts = tables.counts()
    load_id = insert_load_row(
        conn,
        source_file=source_file,
        sha=sha,
        built_at=manifest.get("built_at"),
        git_commit=manifest.get("git_commit"),
        row_counts=counts,
        match_stats={**tables.stats, "gate": tables.gate},
    )
    truncate_ee_tables(
        conn, with_metros_venues=with_metros_venues, with_officials=with_officials
    )

    if with_metros_venues:
        n = copy_table(conn, "core.metros", COPY_COLUMNS["metros"], tables.metros)
        print(f"  COPY core.metros: {n:,}")
        n = copy_table(conn, "core.venues", COPY_COLUMNS["venues"], tables.venues)
        print(f"  COPY core.venues: {n:,}")
        with conn.cursor() as cur:
            for link in tables.location_metro_links:
                cur.execute(
                    "UPDATE core.locations SET metro_id = %s WHERE location_id = %s",
                    (link["metro_id"], link["location_id"]),
                )
            print(f"  UPDATE locations.metro_id: {len(tables.location_metro_links):,}")

    attrs = [{**r, "load_id": load_id} for r in tables.attributes]
    status = [{**r, "load_id": load_id} for r in tables.status_history]
    n = copy_table(conn, "core.edition_attributes", COPY_COLUMNS["edition_attributes"], attrs)
    print(f"  COPY core.edition_attributes: {n:,}")
    n = copy_table(
        conn, "core.edition_status_history", COPY_COLUMNS["edition_status_history"], status
    )
    print(f"  COPY core.edition_status_history: {n:,}")

    if with_officials:
        n = copy_table(conn, "core.officials", COPY_COLUMNS["officials"], tables.officials)
        print(f"  COPY core.officials: {n:,}")
        n = copy_table(
            conn,
            "core.edition_officials",
            COPY_COLUMNS["edition_officials"],
            tables.edition_officials,
        )
        print(f"  COPY core.edition_officials: {n:,}")
        # soft-link CR judge marks by normalized name
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE core.cr_judge_marks jm
                SET official_id = o.official_id
                FROM core.officials o
                WHERE lower(regexp_replace(jm.judge_name, '\\s+', ' ', 'g')) = o.name_normalized
                """
            )
            print(f"  UPDATE cr_judge_marks.official_id: {cur.rowcount:,}")

    with conn.cursor() as cur:
        cur.execute(
            "ANALYZE core.edition_attributes, core.edition_status_history, core.ee_loads"
        )
    return load_id


def run_live_conflict_checks(conn) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM core.edition_attributes a
            WHERE NOT EXISTS (
              SELECT 1 FROM core.event_editions e
              WHERE e.event_id = a.event_id
                AND e.event_year = a.event_year
                AND e.event_month = a.event_month
            )
            """
        )
        orphan_attrs = int(cur.fetchone()[0])
        if orphan_attrs:
            issues.append({"check": "attr_orphan_natural_key", "count": orphan_attrs})

        cur.execute(
            """
            SELECT count(*) FROM core.edition_attributes a
            WHERE a.venue_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM core.venues v WHERE v.venue_id = a.venue_id)
            """
        )
        orphan_venue = int(cur.fetchone()[0])
        if orphan_venue:
            issues.append({"check": "attr_orphan_venue", "count": orphan_venue})

        cur.execute(
            """
            SELECT count(*) FROM core.locations
            WHERE metro_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM core.metros m WHERE m.metro_id = metro_id)
            """
        )
        orphan_metro = int(cur.fetchone()[0])
        if orphan_metro:
            issues.append({"check": "location_orphan_metro", "count": orphan_metro})

    return {"ok": not issues, "issues": issues}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.check_conflicts and not args.dry_run and not args.apply:
        from connection import connect  # type: ignore

        with connect() as conn:
            report = run_live_conflict_checks(conn)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    if not args.dry_run and not args.apply:
        print("Specify --dry-run, --apply, or --check-conflicts.", file=sys.stderr)
        return 2

    ee_path = Path(args.ee_path).expanduser()
    if not ee_path.exists():
        print(f"Missing parquet: {ee_path}", file=sys.stderr)
        return 2

    if args.migrate or args.apply:
        rc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "db" / "apply.py")],
            cwd=str(PROJECT_ROOT),
            check=False,
        ).returncode
        if rc != 0:
            return rc

    from transform.event_editions.build import build_ee_tables
    from transform.event_editions.decisions import load_decisions
    from connection import connect  # type: ignore

    print(f"Reading {ee_path} …")
    sha = file_sha256(ee_path)
    manifest = read_manifest(ee_path)
    df = load_parquet(ee_path)
    decisions = load_decisions(args.decisions)

    with connect() as conn:
        editions = fetch_editions(conn)
        locations = fetch_locations(conn) if args.with_metros_venues else []
        dancers = fetch_dancers(conn) if args.with_officials else []
        print(f"core.event_editions={len(editions):,}")
        tables = build_ee_tables(
            df,
            core_editions=editions,
            decisions=decisions,
            locations=locations,
            dancers=dancers,
            include_metros_venues=args.with_metros_venues,
            include_officials=args.with_officials,
        )
        print("Counts:", json.dumps(tables.counts(), indent=2))
        print("Stats:", json.dumps(tables.stats, indent=2))
        print(
            f"Gate: ok={tables.gate.get('ok')} blockers={tables.gate.get('blocker_count')}"
        )

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "source_file": str(ee_path),
            "file_sha256": sha,
            "manifest": manifest,
            "counts": tables.counts(),
            "stats": tables.stats,
            "gate": tables.gate,
            "mode": "apply" if args.apply else "dry-run",
        }
        args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"Report → {args.report}")

        if not tables.gate.get("ok"):
            print("GATE BLOCKED — unresolved discrepancies:", file=sys.stderr)
            for issue in (tables.gate.get("issues") or [])[:30]:
                print(f"  - {issue}", file=sys.stderr)
            return 1

        if args.dry_run:
            print("DRY-RUN — no writes.")
            return 0

        print("Applying (full replace of EE enrichment tables) …")
        load_id = apply_tables(
            conn,
            tables,
            source_file=str(ee_path),
            sha=sha,
            manifest=manifest,
            with_metros_venues=args.with_metros_venues,
            with_officials=args.with_officials,
        )
        live = run_live_conflict_checks(conn)
        print(f"Applied load_id={load_id}")
        print(f"Live conflict checks: {'OK' if live['ok'] else live}")
        report["load_id"] = load_id
        report["live_conflicts"] = live
        report["mode"] = "apply"
        args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return 0 if live["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
