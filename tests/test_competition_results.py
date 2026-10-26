"""Unit tests for Competition Results → core.cr_* enrichment."""

from __future__ import annotations

import pandas as pd

from transform.competition_results.build import build_cr_tables
from transform.competition_results.divisions import (
    resolve_category,
    resolve_label,
    resolve_level,
)
from transform.competition_results.editions import (
    EditionKey,
    match_cr_edition,
    parse_cr_edition_id,
)
from transform.competition_results.filters import keep_enrichment_row
from transform.competition_results.rounds import (
    competitor_display_name,
    parse_judge_marks,
    resolve_dancer_id,
)


def test_keep_only_wsdc_scrape_rows():
    assert keep_enrichment_row(
        {
            "event_edition_id": "wsdc:77:August 2024",
            "result_from_other_source": True,
        }
    )
    assert not keep_enrichment_row(
        {
            "event_edition_id": "wsdc:77:August 2024",
            "result_from_other_source": False,
            "result_from_wsdc": True,
        }
    )
    assert not keep_enrichment_row(
        {
            "event_edition_id": "eepro:adc2026",
            "result_from_other_source": True,
        }
    )


def test_parse_cr_edition_id():
    assert parse_cr_edition_id("wsdc:77:August 2024") == (77, 8, 2024)
    assert parse_cr_edition_id("eepro:adc2026") == (None, None, None)


def test_match_edition_with_lookup():
    lookup = {(77, 2024, 8): 999}
    m = match_cr_edition(
        cr_edition_id="wsdc:77:August 2024",
        cr_name="Arizona Dance Classic",
        wsdc_event_id=77,
        scoring_source="eepro",
        lookup=lookup,
    )
    assert m.match_status == "matched" and m.edition_id == 999


def test_match_unmatched_when_missing():
    m = match_cr_edition(
        cr_edition_id="wsdc:77:August 2024",
        lookup={},
    )
    assert m.match_status == "unmatched" and m.edition_id is None


def test_resolve_level_and_category():
    assert resolve_level("All-Stars") == "All-Star"
    assert resolve_level("Champions") == "Champion"
    assert resolve_level("Masters") == "Master"
    assert resolve_level(None, "Strictly Novice Finals") is None
    assert (
        resolve_category(
            competition_bucket="wsdc_pointed_leveled",
            wsdc_division="Novice",
            raw_division="Jack & Jill Novice Prelims",
        )
        == "skill"
    )
    assert (
        resolve_category(
            competition_bucket="wsdc_event_other",
            wsdc_division=None,
            raw_division="Strictly Intermediate Finals",
        )
        == "strictly"
    )
    assert (
        resolve_label(
            competition_bucket="wsdc_pointed_leveled",
            wsdc_division="Novice",
            raw_division="x",
        )
        == "Novice"
    )


def test_dancer_id_and_redacted_name():
    known = {421, 16892}
    assert resolve_dancer_id("421", known) == 421
    assert resolve_dancer_id("99999", known) is None
    assert resolve_dancer_id("n:gina_skalicky", known) is None
    assert resolve_dancer_id("redacted", known) is None
    assert competitor_display_name("redacted", "Secret Name") is None
    assert competitor_display_name("421", "Rob") == "Rob"


def test_parse_judge_marks():
    marks = parse_judge_marks('{"A": "Y", "B": "N"}')
    assert marks == [("A", "Y"), ("B", "N")]
    assert parse_judge_marks(None) == []
    assert parse_judge_marks("{}") == []


def test_build_tables_pairs_final_couples_and_dedupes_marks():
    rows = [
        # prelim — competitor marks
        dict(
            event_edition_id="wsdc:77:August 2024",
            wsdc_event_id=77,
            event_edition_date="2024-08-01",
            event_edition_name="ADC",
            raw_division="Jack & Jill Novice Prelims",
            wsdc_division="Novice",
            round="prelim",
            role="leader",
            total_competitors=10,
            place="1",
            callback="Y",
            identity="421",
            competitor_name="Rob",
            partner_identity=None,
            partner_name=None,
            judge_marks='{"J1": "Y"}',
            source="eepro",
            source_url="http://example/prelim",
            result_from_wsdc=False,
            result_from_other_source=True,
            competition_bucket="wsdc_pointed_leveled",
        ),
        # final couple — identical marks on both roles
        dict(
            event_edition_id="wsdc:77:August 2024",
            wsdc_event_id=77,
            event_edition_date="2024-08-01",
            event_edition_name="ADC",
            raw_division="Jack & Jill Novice Finals",
            wsdc_division="Novice",
            round="final",
            role="leader",
            total_competitors=5,
            place="1",
            callback=None,
            identity="421",
            competitor_name="Rob",
            partner_identity="16892",
            partner_name="Felipa",
            judge_marks='{"J1": "1", "J2": "2"}',
            source="eepro",
            source_url="http://example/final",
            result_from_wsdc=True,
            result_from_other_source=True,
            competition_bucket="wsdc_pointed_leveled",
        ),
        dict(
            event_edition_id="wsdc:77:August 2024",
            wsdc_event_id=77,
            event_edition_date="2024-08-01",
            event_edition_name="ADC",
            raw_division="Jack & Jill Novice Finals",
            wsdc_division="Novice",
            round="final",
            role="follower",
            total_competitors=5,
            place="1",
            callback=None,
            identity="16892",
            competitor_name="Felipa",
            partner_identity="421",
            partner_name="Rob",
            judge_marks='{"J1": "1", "J2": "2"}',
            source="eepro",
            source_url="http://example/final",
            result_from_wsdc=True,
            result_from_other_source=True,
            competition_bucket="wsdc_pointed_leveled",
        ),
        # pure WSDC copy — must be dropped by filter
        dict(
            event_edition_id="wsdc:77:August 2024",
            wsdc_event_id=77,
            event_edition_date="2024-08-01",
            event_edition_name="ADC",
            raw_division="Jack & Jill Advanced Finals",
            wsdc_division="Advanced",
            round="final",
            role="leader",
            total_competitors=5,
            place="1",
            callback=None,
            identity="1",
            competitor_name="X",
            partner_identity=None,
            partner_name=None,
            judge_marks=None,
            source=None,
            source_url=None,
            result_from_wsdc=True,
            result_from_other_source=False,
            competition_bucket="wsdc_pointed_leveled",
        ),
    ]
    df = pd.DataFrame(rows)
    editions = [EditionKey(999, 77, 2024, 8)]
    tables = build_cr_tables(
        df, editions=editions, known_dancer_ids={421, 16892}
    )
    assert tables.counts()["cr_editions"] == 1
    assert tables.editions[0]["match_status"] == "matched"
    assert tables.counts()["cr_final_couples"] == 1
    # prelim marks (1) + final couple marks (2) — not 4
    assert tables.counts()["cr_judge_marks"] == 3
    assert all(m["couple_id"] is not None for m in tables.judge_marks if m["cr_round_result_id"] is None)
    # pure WSDC advanced final not loaded
    assert not any(
        "Advanced" in d["raw_division"] for d in tables.divisions
    )
