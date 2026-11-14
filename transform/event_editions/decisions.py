"""Load and query ``event_editions_decisions.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = PROJECT_ROOT / "data" / "reference" / "event_editions_decisions.yaml"


def load_decisions(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_PATH
    if not p.is_file():
        return {"version": 1, "class_rules": [], "cases": []}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    data.setdefault("version", 1)
    data.setdefault("class_rules", [])
    data.setdefault("cases", [])
    return data


def class_rule_allows(decisions: dict[str, Any], class_name: str) -> dict[str, Any] | None:
    for rule in decisions.get("class_rules") or []:
        if rule.get("class") == class_name:
            return rule
    return None


def case_for_key(decisions: dict[str, Any], key: str) -> dict[str, Any] | None:
    for case in decisions.get("cases") or []:
        if case.get("key") == key:
            return case
    return None
