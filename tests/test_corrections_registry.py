"""Tests for declarative correction YAML registry."""

from transform.knowledge.corrections import active_corrections, load_corrections


def test_load_corrections_includes_dump_date_repairs():
    docs = load_corrections()
    assert docs
    ids = {d["id"] for d in docs}
    assert "dump-edition-date-repairs-2014-2023" in ids


def test_active_corrections_filter_by_kind():
    rows = active_corrections(kind="edition_date")
    assert rows
    assert all(r.get("kind") == "edition_date" for r in rows)
    assert all(r.get("status") == "active" for r in rows)
