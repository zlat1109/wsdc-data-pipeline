"""Rules behind the Event Data Registry (WSDC public results vs Competition Results)."""

from __future__ import annotations

import pandas as pd

from scripts.build_event_data_completeness_report import (
    flags_for,
    format_side_labels,
    normalize_side_label,
    resolve_software,
)
from transform.results_form_match import form_start_month, match_forms

SKILL4 = "Advanced|Intermediate|Newcomer|Novice"


def _row(**kw):
    base = {
        "skill_divs": SKILL4,
        "prelim_divs": SKILL4,
        "judge_divs": SKILL4,
        "final_divs": SKILL4,
        "scraped_final_divs": SKILL4,
        "partner_divs": SKILL4,
    }
    base.update(kw)
    return base


def test_prelims_full_when_every_division_has_prelims():
    f = flags_for(_row())
    assert f["chk_prelims"] == "full"
    assert f["chk_partners"] == "full"


def test_scraped_final_without_prelim_is_finals_only_not_a_gap():
    f = flags_for(_row(prelim_divs="Intermediate|Newcomer|Novice"))
    assert f["chk_prelims"] == "full"
    assert "Finals-only" in f["tip_prelims"]
    assert "Advanced" in f["tip_prelims"]


def test_division_known_only_from_wsdc_public_final_is_a_gap():
    f = flags_for(
        _row(
            prelim_divs="Intermediate|Newcomer|Novice",
            scraped_final_divs="Intermediate|Newcomer|Novice",
        )
    )
    assert f["chk_prelims"] == "partial"
    assert "Not in scoring data" in f["tip_prelims"]


def test_partners_never_full_without_prelims():
    f = flags_for(_row(prelim_divs="", judge_divs="", scraped_final_divs=""))
    assert f["chk_prelims"] == "none"
    assert f["chk_partners"] == "partial"
    assert "no prelims" in f["tip_partners"]


def test_partners_none_without_partner_links():
    f = flags_for(_row(partner_divs=""))
    assert f["chk_partners"] == "none"


def test_judges_partial_when_some_divisions_unjudged():
    f = flags_for(_row(judge_divs="Novice"))
    assert f["chk_judges"] == "partial"


def test_side_labels_normalize_fun_and_age_divisions():
    assert normalize_side_label("Strictly Swing Intermediate Finals") == "Strictly Intermediate"
    assert normalize_side_label("Jack & Jill Follower Masters Prelims") == "Masters"
    assert normalize_side_label("Switch Jack&Jill final") == "Switch J&J"
    assert normalize_side_label("Jack & Jill All American Prelims") == "All American"
    assert normalize_side_label("Sophisticated Jack&Jill semi") == "Sophisticated"
    assert normalize_side_label("Jack & Jill Novice") == ""


def test_side_labels_drop_bare_strictly_when_leveled_present():
    blob = "|||".join(["Strictly Novice final", "strictly", "Masters Jack&Jill final"])
    assert format_side_labels(blob) == "Masters · Strictly Novice"


def test_form_month_parsing():
    assert form_start_month("10/16/25 - 10/20/25") == 10
    assert form_start_month("Feb 20th-24th 2025") == 2
    assert form_start_month("22-24.03.2024") == 3
    assert form_start_month("12/04 au 14/04/24") == 4
    assert form_start_month("2024-06-09 00:00:00") == 6
    assert form_start_month("") is None


def test_software_scraped_source_wins_over_disagreeing_form():
    name, conf, note = resolve_software(cr_known=["eepro"], form_sw="net2order")
    assert conf == "confirmed"
    assert name == "EEPro"
    assert "Competition Results" in note


def test_software_form_when_not_scraped():
    name, conf, note = resolve_software(cr_known=[], form_sw="eepro")
    assert conf == "confirmed" and name == "EEPro" and note == "Results Form"


def test_software_other_year_form_when_not_scraped():
    name, conf, note = resolve_software(
        cr_known=[], series_sw="scoringdance", series_yr=2025
    )
    assert conf == "likely"
    assert name == "scoring.dance"
    assert "2025" in note


def test_form_match_uses_year_month_and_name():
    editions = pd.DataFrame(
        [
            (1, 2024, 6, "Liberty Swing Dance Championships"),
            (2, 2024, 6, "Festival City Swing"),
            (3, 2023, 6, "Liberty Swing Dance Championships"),
            (4, 2024, 9, "Rose City Swing"),
            (5, 2024, 9, "Rocket City Swing"),
        ],
        columns=["edition_id", "event_year", "event_month", "event_name"],
    )
    forms = pd.DataFrame(
        [
            (2024, "Liberty Swing", "6/27-30/2024"),
            (2024, "Rocket City Swing 2024", "9/12/24 - 9/15/24"),
            (2024, "The Open", "11/27-12/1"),
        ],
        columns=["form_year_folder", "event_name", "event_dates"],
    )
    out = match_forms(forms, editions)
    assert out.loc[0, "m_ok"] and out.loc[0, "m_edition_id"] == 1
    assert out.loc[1, "m_ok"] and out.loc[1, "m_edition_id"] == 5
    assert not out.loc[2, "m_ok"]
