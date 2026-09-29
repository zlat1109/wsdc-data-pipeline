"""Detach/rematch competitions around event_editions truncate."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))

from build_event_catalog import (
    _competitions_table_exists,
    _detach_competitions_from_editions,
    _rematch_competitions_to_editions,
    _stash_competition_edition_keys,
)


def test_competitions_table_exists_reads_information_schema():
    cur = MagicMock()
    cur.fetchone.return_value = (True,)
    assert _competitions_table_exists(cur) is True
    sql = cur.execute.call_args[0][0]
    assert "core" in sql and "competitions" in sql


def test_stash_returns_temp_table_count():
    cur = MagicMock()
    cur.fetchone.return_value = (42,)
    assert _stash_competition_edition_keys(cur) == 42
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("CREATE TEMP TABLE _competition_edition_keys" in s for s in executed)


def test_detach_updates_matched_rows():
    cur = MagicMock()
    cur.rowcount = 17
    assert _detach_competitions_from_editions(cur) == 17
    sql = cur.execute.call_args[0][0]
    assert "match_status = 'unmatched'" in sql
    assert "edition_id = NULL" in sql


def test_rematch_noops_without_temp_table():
    cur = MagicMock()
    cur.fetchone.return_value = (False,)
    assert _rematch_competitions_to_editions(cur) == (0, 0)


def test_rematch_joins_on_event_year_month():
    cur = MagicMock()
    # to_regclass exists, then COUNT(*)=3, then UPDATE rowcount=2
    cur.fetchone.side_effect = [(True,), (3,)]
    cur.rowcount = 2
    assert _rematch_competitions_to_editions(cur) == (2, 3)
    update_sql = cur.execute.call_args_list[-1].args[0]
    assert "ed.event_year = k.event_year" in update_sql
    assert "ed.event_month = k.event_month" in update_sql
    assert "match_status = 'matched'" in update_sql
