"""Row-level keep rules for Competition Results enrichment."""

from __future__ import annotations

from typing import Any, Mapping


def _truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "t", "true", "yes"}


def keep_enrichment_row(row: Mapping[str, Any]) -> bool:
    """Keep only WSDC editions with scrape-originated data.

    Drops:
    - non-WSDC events (``eepro:…``, ``non_wsdc_event`` buckets without ``wsdc:``);
    - pure WSDC public copies (``result_from_wsdc`` and not ``result_from_other_source``).
    """
    eid = str(row.get("event_edition_id") or "")
    if not eid.startswith("wsdc:"):
        return False
    if not _truthy(row.get("result_from_other_source")):
        return False
    return True
