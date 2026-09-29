"""Guards so empty competitions cannot silently wipe exact L2 Dancers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from export import export_view  # noqa: E402
from validate_export_vs_db import (  # noqa: E402
    COMPETITIONS_BEST_MIN_ROWS,
    _competitions_best_health_problem,
)


def test_competitions_best_health_rejects_header_only(tmp_path: Path):
    path = tmp_path / "competitions_best.csv"
    path.write_text("competition_id,level\n", encoding="utf-8")
    problem = _competitions_best_health_problem(tmp_path)
    assert problem is not None
    assert "0 data rows" in problem or f"{COMPETITIONS_BEST_MIN_ROWS}" in problem


def test_competitions_best_health_ok_above_floor(tmp_path: Path):
    path = tmp_path / "competitions_best.csv"
    lines = ["competition_id"] + [str(i) for i in range(COMPETITIONS_BEST_MIN_ROWS)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert _competitions_best_health_problem(tmp_path) is None


def test_export_view_refuses_overwrite_empty_competitions_best(tmp_path: Path):
    out = tmp_path / "competitions_best.csv"
    out.write_text("competition_id\n1\n2\n", encoding="utf-8")

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    # COPY context manager yields an object whose read() returns header-only CSV.
    copy_cm = MagicMock()
    copy_cm.__enter__.return_value = copy_cm
    copy_cm.read.side_effect = [b"competition_id\n", b""]
    cur.copy.return_value = copy_cm

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        export_view(conn, "export.competitions_best", out)

    assert out.read_text(encoding="utf-8") == "competition_id\n1\n2\n"
