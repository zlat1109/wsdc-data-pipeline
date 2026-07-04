"""Tests for pandas dtype helpers."""

import pandas as pd

from transform.pandas_utils import assign_column_values, scalar_for_dtype


def test_scalar_for_dtype_string():
    assert scalar_for_dtype(47, pd.Series(dtype="string").dtype) == "47"
    assert scalar_for_dtype(None, pd.Series(dtype="string").dtype) == ""


def test_scalar_for_dtype_int_column():
    assert scalar_for_dtype(47, pd.Series(dtype="int64").dtype) == 47


def test_assign_column_values_respects_string_dtype():
    df = pd.DataFrame({"event_name_id": pd.Series(["66"], dtype="string")})
    mask = df["event_name_id"] == "66"
    assign_column_values(df, "event_name_id", mask, 47)
    assert df.loc[0, "event_name_id"] == "47"
