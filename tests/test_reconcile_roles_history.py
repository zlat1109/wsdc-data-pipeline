"""Tests for reconcile_roles_history CLI."""

from pathlib import Path


def test_reconcile_roles_history_has_main():
    path = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_roles_history.py"
    source = path.read_text(encoding="utf-8")
    assert "def main() -> None:" in source
    assert 'if __name__ == "__main__":' in source
