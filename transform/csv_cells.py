"""Normalize API/CSV cell values to strings (cloud_parse contract)."""

from __future__ import annotations

from typing import Any


def cell_str(value: Any) -> str:
    """Convert API field to CSV-safe string (empty for None/NaN)."""
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    text = str(value).strip()
    return text if text.lower() != "nan" else ""
