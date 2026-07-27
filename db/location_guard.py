"""Shared guard for the one-row-per-place-string invariant in core.locations.

`locations_event_location_norm_uidx` (migration 026) allows a single row per
normalized `event_location`. Repair passes that rewrite place strings must check
ownership first, otherwise a stale duplicate aborts the whole load transaction.
"""

from __future__ import annotations

import psycopg


def location_text_owner(
    cur: psycopg.Cursor,
    event_location: str | None,
    exclude_id: int,
) -> int | None:
    """Return the location_id already holding this place string, if any."""
    if not event_location or not str(event_location).strip():
        return None
    cur.execute(
        """
        SELECT location_id
        FROM core.locations
        WHERE lower(btrim(event_location)) = lower(btrim(%s))
          AND location_id <> %s
        LIMIT 1
        """,
        (event_location, exclude_id),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None
