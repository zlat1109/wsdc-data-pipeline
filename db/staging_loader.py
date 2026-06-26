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


def _table_columns(conn: psycopg.Connection, table: str) -> list[str]:
    schema, name = table.split(".", 1)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, name),
        )
        return [row[0] for row in cur.fetchall()]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def copy_csv(conn: psycopg.Connection, csv_path: Path, table: str) -> int:
    """Load CSV into staging, mapping columns by header name (not file order).

    Supports parser CSVs (full staging columns) and export CSVs in data/
    (Tableau contract — subset of columns).
    """
    import csv
    import uuid

    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        header = next(csv.reader(handle))
    if not header:
        raise ValueError(f"Empty CSV header: {csv_path}")

    table_cols = _table_columns(conn, table)
    shared = [col for col in table_cols if col in header]
    if not shared:
        raise ValueError(
            f"No overlapping columns between {csv_path.name} and {table}: "
            f"csv={header}, table={table_cols}"
        )

    tmp = f"tmp_load_{uuid.uuid4().hex[:12]}"
    tmp_cols_sql = ", ".join(f"{_quote_ident(col)} text" for col in header)
    target_cols_sql = ", ".join(_quote_ident(col) for col in shared)
    select_cols_sql = ", ".join(_quote_ident(col) for col in shared)

    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE {tmp} ({tmp_cols_sql}) ON COMMIT DROP")
        with cur.copy(
            f"COPY {tmp} FROM STDIN WITH (FORMAT csv, HEADER true)"
        ) as copy:
            copy.write(csv_path.read_bytes())
        cur.execute(f"INSERT INTO {table} ({target_cols_sql}) SELECT {select_cols_sql} FROM {tmp}")
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def load_staging_from_dir(
    conn: psycopg.Connection,
    data_dir: Path,
    *,
    skip_changed_roles: bool = False,
) -> dict[str, int]:
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
        if skip_changed_roles and table == "staging.changed_dancer_role_info":
            continue
        for filename in candidates:
            path = data_dir / filename
            if path.exists():
                counts[filename] = copy_csv(conn, path, table)
                break

    conn.commit()
    return counts
