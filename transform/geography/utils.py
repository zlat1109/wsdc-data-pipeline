"""Shared utility helpers for the geography transform layer."""

from __future__ import annotations

import pandas as pd


def norm_value(value: object) -> str:
    """Normalize any scalar to a stripped string; None / NaN → ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()
