"""Tests for event catalog SQL building blocks."""

from transform.event_knowledge import KNOWN_EVENT_METADATA


def test_known_metadata_has_scandinavian_and_bto():
    assert 229 in KNOWN_EVENT_METADATA
    assert 324 in KNOWN_EVENT_METADATA
    assert KNOWN_EVENT_METADATA[229].get("typical_location")


def test_migration_012_defines_edition_unique_key():
    sql = open("db/migrations/012_event_catalog.sql", encoding="utf-8").read()
    assert "UNIQUE (event_id, event_year, event_month)" in sql
    assert "export.results_by_event" in sql
    assert "export.event_catalog" in sql
