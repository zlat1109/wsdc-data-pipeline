"""Small pandas helpers shared across transform modules."""

from __future__ import annotations

from typing import Any

import pandas as pd


def scalar_for_dtype(value: Any, dtype: pd.api.types.Dtype) -> Any:
    """Coerce a Python scalar to match a pandas column dtype."""
    if pd.api.types.is_string_dtype(dtype):
        if value is None:
            return ""
        if isinstance(value, float) and pd.isna(value):
            return ""
        return str(value)
    return value


def assign_column_values(
    df: pd.DataFrame,
    column: str,
    mask: pd.Series,
    value: Any,
) -> None:
    """Assign scalar values without violating StringDtype columns."""
    df.loc[mask, column] = scalar_for_dtype(value, df[column].dtype)
