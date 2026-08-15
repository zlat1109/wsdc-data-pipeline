"""CSV/staging boolean tokens (t/f) must promote into core.locations."""

from __future__ import annotations

from pathlib import Path

import pytest

from db.csv_bool import csv_bool_sql_expr, parse_csv_bool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMOTE_CORE = PROJECT_ROOT / "db" / "sql" / "promote_core.sql"
REPAIR_SCRIPT = PROJECT_ROOT / "scripts" / "repair_results_location.py"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("t", True),
        ("T", True),
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("f", False),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", None),
        ("nan", None),
        (None, None),
        (True, True),
        (False, False),
    ],
)
def test_parse_csv_bool(raw, expected):
    assert parse_csv_bool(raw) is expected


def test_csv_bool_sql_expr_includes_postgres_tf_tokens():
    expr = csv_bool_sql_expr("coordinates_valid")
    assert "WHEN 't' THEN true" in expr
    assert "WHEN 'f' THEN false" in expr
    assert "coordinates_valid" in expr


def test_csv_bool_sql_expr_rejects_injection():
    with pytest.raises(ValueError):
        csv_bool_sql_expr("coordinates_valid; drop table x")


def test_promote_core_accepts_csv_t_f_coordinates_valid():
    text = PROMOTE_CORE.read_text(encoding="utf-8")
    assert "WHEN 't' THEN true" in text
    assert "WHEN 'f' THEN false" in text
    assert "coordinates_valid" in text


def test_repair_results_location_uses_shared_csv_bool_helper():
    text = REPAIR_SCRIPT.read_text(encoding="utf-8")
    assert "from csv_bool import csv_bool_sql_expr" in text
    assert "csv_bool_sql_expr(" in text
