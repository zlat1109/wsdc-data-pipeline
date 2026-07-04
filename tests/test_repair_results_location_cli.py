"""Tests for repair_results_location CLI contract."""

from pathlib import Path


def test_repair_results_location_requires_dry_run_or_apply():
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "repair_results_location.py"
    ).read_text(encoding="utf-8")
    assert "add_mutually_exclusive_group(required=True)" in source
    assert '--dry-run"' in source or "--dry-run" in source
    assert '--apply"' in source or "--apply" in source
    assert 'if __name__ == "__main__"' in source


def test_repair_results_location_docstring_lists_dry_run_and_apply():
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "repair_results_location.py"
    ).read_text(encoding="utf-8")
    assert "repair_results_location.py --dry-run" in source
    assert "repair_results_location.py --apply" in source
