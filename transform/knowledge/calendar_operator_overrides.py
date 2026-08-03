"""Operator-curated calendar statuses not (yet) on the WSDC listing.

These rows are upserted into ``core.edition_calendar_dates`` with
``date_source='operator'``. A later official ``wsdc_calendar`` scrape for the
same ``(event_id, year, month)`` overwrites them (see upsert WHERE in
``db/edition_calendar.py``).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

# Provisional assumptions — review when the WSDC calendar/list catches up.
CALENDAR_OPERATOR_OVERRIDES: list[dict[str, Any]] = [
    {
        "event_id": 148,
        "event_year": 2026,
        "event_month": 7,
        "planned_start_date": date(2026, 7, 24),
        "planned_end_date": date(2026, 7, 27),
        "calendar_status": "hiatus",
        "calendar_title": "Dance Mardi Gras (Hiatus -- 2026)",
        "url": "https://dancemardigras.com/",
        "match_via": "operator_assumption",
        "source_fingerprint": "operator:dmg-2026-hiatus-assumption",
        "notes": (
            "2026 edition not on WSDC calendar/list after 2025 results; "
            "site suggests a skip year — treat as hiatus until list confirms "
            "or 2027 appears."
        ),
    },
]


def operator_override_upsert_rows(
    *,
    scraped_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Payloads compatible with ``upsert_edition_calendar_dates``."""
    now = scraped_at or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for row in CALENDAR_OPERATOR_OVERRIDES:
        out.append(
            {
                "event_id": int(row["event_id"]),
                "event_year": int(row["event_year"]),
                "event_month": int(row["event_month"]),
                "planned_start_date": row["planned_start_date"],
                "planned_end_date": row["planned_end_date"],
                "calendar_status": row["calendar_status"],
                "date_source": "operator",
                "source_fingerprint": row.get("source_fingerprint"),
                "calendar_title": row.get("calendar_title"),
                "url": row.get("url"),
                "match_via": row.get("match_via") or "operator_assumption",
                "scraped_at": now,
                "updated_at": now,
            }
        )
    return out
