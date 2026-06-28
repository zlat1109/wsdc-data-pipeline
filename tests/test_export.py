"""Unit tests for export.py view → filename contract."""

from __future__ import annotations

from export import (
    EVENT_CATALOG_EXPORTS,
    HISTORY_EXPORTS,
    LEGACY_EXPORTS,
    OPTIONAL_EXPORTS,
    build_export_map,
)


def test_default_export_map_includes_legacy_and_event_catalog() -> None:
    exports = build_export_map()
    assert set(LEGACY_EXPORTS.items()) <= set(exports.items())
    assert set(EVENT_CATALOG_EXPORTS.items()) <= set(exports.items())
    assert set(HISTORY_EXPORTS.items()) <= set(exports.items())
    assert "export.results_by_event" not in exports
    assert "export.dancers_results_with_name" not in exports


def test_optional_results_by_event_flag() -> None:
    exports = build_export_map(include_results_by_event=True)
    assert exports["export.results_by_event"] == "results_by_event.csv"


def test_optional_results_with_name_flag() -> None:
    exports = build_export_map(include_results_with_name=True)
    assert exports["export.dancers_results_with_name"] == "dancers_results_with_name.csv"


def test_export_filenames_are_unique() -> None:
    from export import DERIVED_EXPORTS

    all_exports = {
        **LEGACY_EXPORTS,
        **EVENT_CATALOG_EXPORTS,
        **HISTORY_EXPORTS,
        **OPTIONAL_EXPORTS,
    }
    filenames = list(all_exports.values())
    assert len(filenames) == len(set(filenames))
    assert not set(filenames) & set(DERIVED_EXPORTS)
