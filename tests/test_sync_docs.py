"""Tests for scripts/sync_docs.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_sync_docs():
    path = PROJECT_ROOT / "scripts" / "sync_docs.py"
    spec = importlib.util.spec_from_file_location("sync_docs", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_escape_md_cell():
    mod = _load_sync_docs()
    assert mod._escape_md_cell("a|b") == r"a\|b"
    assert mod._escape_md_cell("plain") == "plain"


def test_apply_block_replaces_marked_region():
    mod = _load_sync_docs()
    text = (
        "intro\n<!-- docs-sync:test -->\nold body\n<!-- /docs-sync:test -->\noutro"
    )
    updated = mod.apply_block(text, "test", "new body")
    assert "new body" in updated
    assert "old body" not in updated
    assert updated.startswith("intro")


def test_apply_block_missing_marker_exits():
    mod = _load_sync_docs()
    with pytest.raises(SystemExit):
        mod.apply_block("no markers", "missing", "body")


def test_apply_block_two_blocks_on_same_file():
    mod = _load_sync_docs()
    text = """<!-- docs-sync:a -->
a-old
<!-- /docs-sync:a -->
<!-- docs-sync:b -->
b-old
<!-- /docs-sync:b -->"""
    once = mod.apply_block(text, "a", "a-new")
    twice = mod.apply_block(once, "b", "b-new")
    assert "a-new" in twice
    assert "b-new" in twice
    assert "a-old" not in twice
    assert "b-old" not in twice


def test_migration_summary_prefers_docs_summary_tag(tmp_path):
    mod = _load_sync_docs()
    sql = tmp_path / "999_test.sql"
    sql.write_text(
        "-- @docs-summary: Custom one-line summary\n-- ignored line\nCREATE TABLE x (id int);"
    )
    assert mod._migration_summary(sql) == "Custom one-line summary"


def test_migration_summary_joins_comment_paragraph(tmp_path):
    mod = _load_sync_docs()
    sql = tmp_path / "998_test.sql"
    sql.write_text(
        "-- Line one.\n-- Line two.\n\nCREATE TABLE x (id int);"
    )
    assert mod._migration_summary(sql) == "Line one. Line two."


def test_migration_summary_from_real_migration():
    mod = _load_sync_docs()
    path = PROJECT_ROOT / "db/migrations/023_dancer_roles_division_sig.sql"
    summary = mod._migration_summary(path)
    assert "md5 signature" in summary.lower()


def test_migration_index_includes_latest():
    mod = _load_sync_docs()
    table = mod.build_migration_index_table()
    assert "023_dancer_roles_division_sig.sql" in table
    assert "021_dancer_names_history.sql" in table


def test_find_stale_paths():
    mod = _load_sync_docs()
    path = PROJECT_ROOT / "docs/database/migrations.md"
    current = path.read_text(encoding="utf-8")
    assert path not in mod.find_stale_paths({path: current})
    assert path in mod.find_stale_paths({path: current + "\n"})


def test_check_mode_does_not_modify_tracked_docs():
    mod = _load_sync_docs()
    migrations = PROJECT_ROOT / "docs/database/migrations.md"
    before = migrations.read_text(encoding="utf-8")
    before_mtime = migrations.stat().st_mtime

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts/sync_docs.py"), "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    after = migrations.read_text(encoding="utf-8")
    assert after == before
    assert migrations.stat().st_mtime == before_mtime
    assert result.returncode == 0, result.stderr
