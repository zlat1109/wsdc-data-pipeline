"""Parse CSV boolean tokens used in location_info / staging text columns.

Postgres COPY and local exports often store booleans as ``t``/``f``.
Weekly ``promote_core`` must accept those alongside ``true``/``false``.
"""

from __future__ import annotations

# Shared SQL CASE for staging.text → core boolean columns.
# Keep in sync with parse_csv_bool() below.
CSV_BOOL_SQL_CASE = """\
CASE LOWER(TRIM({column}))
    WHEN 'true' THEN true
    WHEN 't' THEN true
    WHEN '1' THEN true
    WHEN 'yes' THEN true
    WHEN 'false' THEN false
    WHEN 'f' THEN false
    WHEN '0' THEN false
    WHEN 'no' THEN false
    ELSE NULL
END"""


def csv_bool_sql_expr(column: str = "coordinates_valid") -> str:
    """Return a SQL expression casting a staging text column to boolean."""
    if not column.replace("_", "").isalnum():
        raise ValueError(f"unsafe SQL column name: {column!r}")
    return CSV_BOOL_SQL_CASE.format(column=column)


def parse_csv_bool(value: object) -> bool | None:
    """Map CSV/staging boolean tokens to Python bool (or None if unknown/empty)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes"}:
        return True
    if text in {"false", "f", "0", "no"}:
        return False
    return None
