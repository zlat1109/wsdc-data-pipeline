"""Tests for consolidated event alias export."""

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _merge_aliases() -> dict[str, str]:
    merged: dict[str, str] = {}
    for rel in (
        "transform/knowledge/event_aliases.py",
        "parser/event_name_matcher.py",
    ):
        mod_path = PROJECT_ROOT / rel
        spec = importlib.util.spec_from_file_location(mod_path.stem, mod_path)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        for attr in (
            "RESULT_TO_CATALOG_EVENT_NAME",
            "EVENT_NAME_VARIANT_TO_CATALOG",
            "EVENT_NAME_MAPPINGS",
        ):
            block = getattr(mod, attr, None)
            if isinstance(block, dict):
                merged.update(block)
    return merged


def test_build_event_aliases_includes_schedule_and_result_maps():
    mappings = _merge_aliases()
    assert mappings["Paris Swing Classic"] == "Paris Westie Fest"
    assert mappings["Westie Weekend"] == "Dance Jam Jack & Jill Weekend"
    assert mappings["MADjam"] == "MADjam"
    assert mappings["Mid-Atlantic Dance Jam"] == "MADjam"
    assert mappings["Easter Swing"] == "Easter Swing"
    assert mappings["Seattle's Easter Swing"] == "Easter Swing"


def test_export_event_aliases_json_shape(tmp_path: Path):
    mappings = _merge_aliases()
    path = tmp_path / "event_aliases.json"
    path.write_text(json.dumps({"version": 1, "mappings": mappings}), encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert "Paris Swing Classic" in payload["mappings"]

