"""Tests for scripts/sync_docs.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_sync_docs():
    path = PROJECT_ROOT / "scripts" / "sync_docs.py"
    spec = importlib.util.spec_from_file_location("sync_docs", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_summary_from_first_comment():
    mod = _load_sync_docs()
    path = PROJECT_ROOT / "db/migrations/023_dancer_roles_division_sig.sql"
    summary = mod._migration_summary(path)
    assert "md5 signature" in summary.lower()


def test_migration_index_includes_latest():
    mod = _load_sync_docs()
    table = mod.build_migration_index_table()
    assert "023_dancer_roles_division_sig.sql" in table
    assert "021_dancer_names_history.sql" in table
