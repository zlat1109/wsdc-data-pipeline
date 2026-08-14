"""Load must not commit a partial promote_core on failure."""

from pathlib import Path

LOAD_PY = Path(__file__).resolve().parents[1] / "load.py"


def test_load_rolls_back_before_marking_parse_failed():
    text = LOAD_PY.read_text(encoding="utf-8")
    except_at = text.find("except Exception:")
    assert except_at != -1
    rollback_at = text.find("conn.rollback()", except_at)
    failed_commit_at = text.find("conn.commit()", except_at)
    assert rollback_at != -1
    assert failed_commit_at != -1
    assert rollback_at < failed_commit_at


def test_load_statement_timeout_covers_catalog_rebuild():
    text = LOAD_PY.read_text(encoding="utf-8")
    assert "SET statement_timeout = '30min'" in text
