"""Load CSV files into staging tables via PostgreSQL COPY."""

from __future__ import annotations

from pathlib import Path

import psycopg

STAGING_TABLES: dict[str, str] = {
    "dancers_points_info.csv": "staging.dancers_points_info",
    "dancer_role_info.csv": "staging.dancer_role_info",
    "dancers_results_info.csv": "staging.dancers_results_info",
    "location_info.csv": "staging.location_info",
    "events_wsdc.csv": "staging.events_wsdc",
}

OPTIONAL_CHANGED: list[tuple[list[str], str]] = [
    (["changed_dancers_points_info.csv", "changed_dancer_points_info.csv"],
     "staging.changed_dancers_points_info"),
    (["changed_dancer_role_info.csv"], "staging.changed_dancer_role_info"),
]


def truncate_staging(conn: psycopg.Connection) -> None:
    tables = sorted(
        set(STAGING_TABLES.values())
        | {table for _, table in OPTIONAL_CHANGED}
    )
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE "
            + ", ".join(tables)
        )


def copy_csv(conn: psycopg.Connection, csv_path: Path, table: str) -> int:
    with conn.cursor() as cur:
        with cur.copy(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)"
        ) as copy:
            copy.write(csv_path.read_bytes())
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def load_staging_from_dir(conn: psycopg.Connection, data_dir: Path) -> dict[str, int]:
    """Truncate staging and load main CSV set. Returns row counts per file."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    truncate_staging(conn)
    counts: dict[str, int] = {}

    for filename, table in STAGING_TABLES.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Required CSV missing: {path}")
        counts[filename] = copy_csv(conn, path, table)

    for candidates, table in OPTIONAL_CHANGED:
        for filename in candidates:
            path = data_dir / filename
            if path.exists():
                counts[filename] = copy_csv(conn, path, table)
                break

    conn.commit()
    return counts
