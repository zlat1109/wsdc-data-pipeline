"""Tests for declarative correction YAML registry."""

from datetime import date

from transform.knowledge.corrections import (
    active_corrections,
    edition_date_repair_fills,
    edition_date_repairs,
    load_corrections,
    result_role_rule,
    stale_corrections,
)


def test_load_corrections_includes_dump_date_repairs():
    docs = load_corrections()
    assert docs
    ids = {d["id"] for d in docs}
    assert "dump-edition-date-repairs-2014-2023" in ids
    assert "bavarian-allstar-roles-2026" in ids


def test_active_corrections_filter_by_kind():
    rows = active_corrections(kind="edition_date")
    assert rows
    assert all(r.get("kind") == "edition_date" for r in rows)
    assert all(r.get("status") == "active" for r in rows)


def test_result_role_rule_from_yaml():
    rule = result_role_rule("bavarian-allstar-roles-2026")
    assert rule is not None
    assert rule["event_id"] == 233
    assert rule["event_year"] == 2026
    assert "all-star" in rule["division_keys"]
    assert "bavarian open" in rule["event_name_substrings"]


def test_edition_date_repairs_include_known_keys():
    repairs = edition_date_repairs()
    assert (92, 2023, 3) in repairs
    start, end = repairs[(92, 2023, 3)]
    assert start == date(2023, 3, 2)
    assert end == date(2023, 3, 6)
    fills = edition_date_repair_fills()
    assert any(f["event_id"] == 92 and f["date_source"] == "knowledge_correction" for f in fills)


def test_retired_bavarian_yaml_disables_role_flip(monkeypatch):
    import pandas as pd

    import transform.knowledge.corrections as corrections
    from transform import result_role_corrections as rrc

    results = pd.DataFrame(
        {
            "event_name": ["Bavarian Open"],
            "event_year": ["2026"],
            "event_competition": ["All-Star"],
        }
    )
    assert rrc.select_bavarian_allstar_2026_mask(results).tolist() == [True]

    monkeypatch.setattr(corrections, "result_role_rule", lambda _id: None)
    assert rrc.select_bavarian_allstar_2026_mask(results).tolist() == [False]


def test_stale_corrections_empty_when_expires_null():
    assert stale_corrections(today=date(2099, 1, 1)) == []
