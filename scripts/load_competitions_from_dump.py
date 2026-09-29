#!/usr/bin/env python3
"""One-shot: load WSDC dump ``competitions`` (WCS) into ``core.competitions``.

Requires local Docker MySQL clone ``wsdc-clone``, or pre-extracted TSVs with
``--skip-extract``. Does **not** run on every parse.

Usage:
    python scripts/load_competitions_from_dump.py --dry-run
    python scripts/load_competitions_from_dump.py --apply
    python scripts/load_competitions_from_dump.py --extract-only
    python scripts/load_competitions_from_dump.py --apply --skip-extract
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

DEFAULT_COMP_TSV = PROJECT_ROOT / "dumps" / "competitions_wcs.tsv"
DEFAULT_CE_TSV = PROJECT_ROOT / "dumps" / "competitionevents_dates.tsv"
REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"
CONTAINER = "wsdc-clone"


def _docker_mysql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        CONTAINER,
        "bash",
        "-c",
        f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" wsdc --default-character-set=utf8mb4 '
        f"-N -B -e {json.dumps(sql)}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker mysql failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def extract_competitions_tsv(path: Path) -> int:
    sql = (
        "SELECT c.id, c.competitionevent_id, c.dancetype_id, c.division_id, "
        "IFNULL(c.leader_count,''), IFNULL(c.follower_count,''), "
        "IFNULL(c.finals_count,''), IFNULL(c.created_at,''), IFNULL(c.updated_at,'') "
        "FROM competitions c WHERE c.dancetype_id = 1 ORDER BY c.id"
    )
    text = _docker_mysql(sql)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = (
        "competition_id\tcompetitionevent_id\tdancetype_id\tdivision_id\t"
        "leader_count\tfollower_count\tfinals_count\tcreated_at\tupdated_at\n"
    )
    path.write_text(header + "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def extract_competitionevents_tsv(path: Path) -> int:
    sql = (
        "SELECT id, event_id, IFNULL(event_name,''), IFNULL(start_date,''), "
        "IFNULL(end_date,'') FROM competitionevents"
    )
    text = _docker_mysql(sql)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sum(1 for ln in text.splitlines() if ln.strip())


def load_competitions_tsv(path: Path):
    from transform.competitions_from_dump import (
        DumpCompetitionRow,
        parse_optional_int,
        parse_timestamp,
    )

    rows: list[DumpCompetitionRow] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for rec in reader:
            rows.append(
                DumpCompetitionRow(
                    competition_id=int(rec["competition_id"]),
                    competitionevent_id=int(rec["competitionevent_id"]),
                    dancetype_id=int(rec["dancetype_id"]),
                    division_id=int(rec["division_id"]),
                    leader_count=parse_optional_int(rec.get("leader_count")),
                    follower_count=parse_optional_int(rec.get("follower_count")),
                    finals_count=parse_optional_int(rec.get("finals_count")),
                    created_at=parse_timestamp(rec.get("created_at")),
                    updated_at=parse_timestamp(rec.get("updated_at")),
                )
            )
    return rows


def _load_editions(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ed.edition_id,
                ed.event_id,
                ed.event_year,
                ed.event_month,
                ed.start_date,
                ed.end_date,
                COALESCE(c.canonical_name, e.name, '') AS event_name
            FROM core.event_editions ed
            LEFT JOIN core.event_catalog c ON c.event_id = ed.event_id
            LEFT JOIN core.events e ON e.event_id = ed.event_id
            """
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def _upsert(conn, rows) -> None:
    """Replace snapshot: delete missing dump ids, then upsert current batch."""
    sql = """
    INSERT INTO core.competitions (
        competition_id, competitionevent_id, edition_id, level_id, level, dance,
        leader_count, follower_count, finals_count, match_status,
        dump_created_at, dump_updated_at, loaded_at
    ) VALUES (
        %(competition_id)s, %(competitionevent_id)s, %(edition_id)s,
        %(level_id)s, %(level)s, %(dance)s,
        %(leader_count)s, %(follower_count)s, %(finals_count)s, %(match_status)s,
        %(dump_created_at)s, %(dump_updated_at)s, %(loaded_at)s
    )
    ON CONFLICT (competition_id) DO UPDATE SET
        competitionevent_id = EXCLUDED.competitionevent_id,
        edition_id = EXCLUDED.edition_id,
        level_id = EXCLUDED.level_id,
        level = EXCLUDED.level,
        dance = EXCLUDED.dance,
        leader_count = EXCLUDED.leader_count,
        follower_count = EXCLUDED.follower_count,
        finals_count = EXCLUDED.finals_count,
        match_status = EXCLUDED.match_status,
        dump_created_at = EXCLUDED.dump_created_at,
        dump_updated_at = EXCLUDED.dump_updated_at,
        loaded_at = EXCLUDED.loaded_at
    """
    loaded_at = datetime.now(timezone.utc)
    payload = []
    ids: list[int] = []
    for row in rows:
        d = asdict(row)
        d["loaded_at"] = loaded_at
        payload.append(d)
        ids.append(int(row.competition_id))
    with conn.cursor() as cur:
        if ids:
            cur.execute(
                "DELETE FROM core.competitions WHERE competition_id <> ALL(%s)",
                (ids,),
            )
        else:
            cur.execute("SELECT count(*) FROM core.competitions")
            existing = int(cur.fetchone()[0])
            if existing > 0:
                raise RuntimeError(
                    f"Refusing to TRUNCATE core.competitions: planned dump batch "
                    f"is empty but table has {existing:,} rows. Fix extract/TSV "
                    f"before --apply."
                )
            cur.execute("TRUNCATE core.competitions")
        cur.executemany(sql, payload)
    conn.commit()


def _tier_crosscheck(conn) -> dict:
    """Compare exact counts vs estimated tier ranges where both exist.

    Join on (event_id, year, month, division) — not edition_id — because
    ``edition_division_tiers.edition_id`` can lag a catalog rebuild.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH comp AS (
                SELECT
                    ed.event_id,
                    ed.event_year,
                    ed.event_month,
                    c.level AS division,
                    c.leader_count,
                    c.follower_count
                FROM core.competitions c
                JOIN core.event_editions ed ON ed.edition_id = c.edition_id
                WHERE c.match_status = 'matched'
                  AND c.leader_count IS NOT NULL
                  AND c.follower_count IS NOT NULL
            ),
            tiers AS (
                SELECT
                    event_id,
                    event_year,
                    event_month,
                    division,
                    role,
                    est_min_competitors,
                    est_max_competitors
                FROM core.edition_division_tiers
                WHERE dance ILIKE '%West Coast%'
                  AND est_min_competitors IS NOT NULL
            )
            SELECT
                COUNT(*) AS compared_role_rows,
                COUNT(*) FILTER (
                    WHERE (t.role = 'Leader' AND (
                        c.leader_count < t.est_min_competitors
                        OR (t.est_max_competitors IS NOT NULL
                            AND c.leader_count > t.est_max_competitors)
                    ))
                    OR (t.role = 'Follower' AND (
                        c.follower_count < t.est_min_competitors
                        OR (t.est_max_competitors IS NOT NULL
                            AND c.follower_count > t.est_max_competitors)
                    ))
                ) AS outside_estimate_range
            FROM comp c
            JOIN tiers t
              ON t.event_id = c.event_id
             AND t.event_year = c.event_year
             AND t.event_month = c.event_month
             AND t.division = c.division
            """
        )
        row = cur.fetchone()
        return {
            "compared_role_rows": int(row[0] or 0),
            "outside_estimate_range": int(row[1] or 0),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--comp-tsv", type=Path, default=DEFAULT_COMP_TSV)
    parser.add_argument("--ce-tsv", type=Path, default=DEFAULT_CE_TSV)
    parser.add_argument("--migrate", action="store_true", help="run db/apply.py first")
    args = parser.parse_args()

    if args.extract_only or (not args.skip_extract and (args.dry_run or args.apply)):
        n_ce = extract_competitionevents_tsv(args.ce_tsv)
        n_comp = extract_competitions_tsv(args.comp_tsv)
        print(f"Extracted competitionevents={n_ce} → {args.ce_tsv}")
        print(f"Extracted competitions(WCS)={n_comp} → {args.comp_tsv}")
        if args.extract_only:
            return 0

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply (or --extract-only).", file=sys.stderr)
        return 2

    from transform.competitions_from_dump import (
        build_ce_to_edition_id,
        count_skipped_divisions,
        plan_competition_rows,
        summarize_plans,
    )
    from transform.dump_edition_dates import load_competitionevents_tsv

    comps = load_competitions_tsv(args.comp_tsv)
    dump_events = load_competitionevents_tsv(args.ce_tsv)
    skipped_div = count_skipped_divisions(comps)

    if args.migrate or args.apply:
        rc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "db" / "apply.py")],
            cwd=str(PROJECT_ROOT),
            check=False,
        ).returncode
        if rc != 0:
            return rc

    from connection import connect  # type: ignore

    with connect() as conn:
        editions = _load_editions(conn)
        ce_map = build_ce_to_edition_id(dump_events, editions)
        planned = plan_competition_rows(comps, ce_map)
        summary = summarize_plans(planned)
        summary["skipped_unknown_division"] = skipped_div
        summary["ce_mapped"] = len(ce_map)
        summary["dump_competitionevents"] = len(dump_events)
        summary["dump_competitions_wcs"] = len(comps)

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / "competitions_load.json"
        ce_by_id = {d.competitionevent_id: d for d in dump_events}
        unmatched = []
        for r in planned:
            if r.match_status != "unmatched":
                continue
            ce = ce_by_id.get(r.competitionevent_id)
            item = asdict(r)
            if ce is not None:
                item["dump_event_name"] = ce.event_name
                item["dump_series_event_id"] = ce.series_event_id
                item["dump_start_date"] = ce.start_date
                item["dump_end_date"] = ce.end_date
            unmatched.append(item)
            if len(unmatched) >= 200:
                break
        # Multi-CE collisions on the same matched edition+level (unsafe to SUM).
        collision_keys: dict[tuple[int, str], list[int]] = {}
        for r in planned:
            if r.edition_id is None:
                continue
            key = (r.edition_id, r.level)
            collision_keys.setdefault(key, []).append(r.competition_id)
        multi = {
            f"{ed}:{lvl}": ids
            for (ed, lvl), ids in collision_keys.items()
            if len(ids) > 1
        }
        summary["edition_level_collision_groups"] = len(multi)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "unmatched_sample": unmatched,
            "edition_level_collisions_sample": dict(list(multi.items())[:50]),
            "note": (
                "For analytics use export.competitions_best (one row per "
                "edition_id+level). core.competitions keeps full dump lineage."
            ),
        }

        if args.apply:
            _upsert(conn, planned)
            payload["crosscheck"] = _tier_crosscheck(conn)
            print(
                f"Upserted {len(planned)} rows into core.competitions "
                f"(matched={summary['matched']}, unmatched={summary['unmatched']})"
            )
            print(f"Tier crosscheck: {payload['crosscheck']}")
        else:
            print(
                f"DRY-RUN planned={len(planned)} "
                f"matched={summary['matched']} unmatched={summary['unmatched']} "
                f"skipped_div={skipped_div} ce_mapped={len(ce_map)}"
            )

        report_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(f"Report → {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
