"""Unit tests for scripts/merge_location_ids.py helpers."""

from unittest.mock import MagicMock

from transform.geography.constants import US_COUNTRY_VALUES, us_country_sql_in_clause

import scripts.merge_location_ids as merge_script


def test_us_country_sql_in_clause_matches_constants():
    clause = us_country_sql_in_clause()
    for country in US_COUNTRY_VALUES:
        assert f"'{country}'" in clause


def test_apply_merges_returns_zero_when_sources_missing():
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 0
    conn.cursor.return_value.__enter__.return_value = cur

    changed = merge_script.apply_merges(conn)

    assert changed == 0
    assert cur.execute.call_count == len(merge_script.LOCATION_ID_MERGE_MAP) * (
        len(merge_script.FK_TABLES) + 1
    )


def test_apply_location_id_corrections_parameter_order():
    """SET cols, then location_id, then DISTINCT cols — not location_id last."""
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 0
    conn.cursor.return_value.__enter__.return_value = cur

    merge_script.apply_location_id_corrections(conn)

    _, params = cur.execute.call_args_list[0][0]
    first_id = sorted(merge_script.LOCATION_ID_CORRECTIONS)[0]
    patch = merge_script.LOCATION_ID_CORRECTIONS[first_id]
    db_values = [None if patch[col] == "" else patch[col] for col in patch]
    assert params == db_values + [first_id] + db_values


def test_apply_location_id_corrections_runs_for_all_patches():
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 0
    conn.cursor.return_value.__enter__.return_value = cur

    updated = merge_script.apply_location_id_corrections(conn)

    assert updated == 0
    assert cur.execute.call_count == len(merge_script.LOCATION_ID_CORRECTIONS)


def test_clear_non_us_event_states_uses_shared_country_list():
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 0
    conn.cursor.return_value.__enter__.return_value = cur

    cleared = merge_script.clear_non_us_event_states(conn)

    assert cleared == 0
    sql = cur.execute.call_args[0][0]
    for country in US_COUNTRY_VALUES:
        assert country in sql
