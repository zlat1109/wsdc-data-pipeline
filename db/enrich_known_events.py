"""Apply KNOWN_EVENT_METADATA to core tables after promote_core."""

from __future__ import annotations

import psycopg

from transform.knowledge import (
    KNOWN_EVENT_METADATA,
    LOCATION_ID_CORRECTIONS,
    event_location_patches,
)
from db.location_guard import location_text_owner


def _apply_location_patch(
    cur: psycopg.Cursor,
    location_id: int,
    fixes: dict[str, str],
    *,
    force: bool = False,
) -> None:
    # core.locations keeps one row per place string (locations_event_location_norm_uidx),
    # so a patch aimed at a merged-away id must not resurrect or duplicate it.
    owner = location_text_owner(cur, fixes.get("event_location"), location_id)
    if owner is not None:
        print(
            f"WARN: skipping location patch {location_id} → "
            f"{fixes.get('event_location')!r}: already owned by location_id {owner}"
        )
        return

    cur.execute(
        """
        SELECT event_city, event_country, event_location
        FROM core.locations WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO core.locations (
                location_id, event_city, event_state, event_country,
                event_location, event_location_standardized, coordinates_valid
            ) VALUES (%s, %s, %s, %s, %s, %s, false)
            """,
            (
                location_id,
                fixes.get("event_city"),
                fixes.get("event_state") or None,
                fixes.get("event_country"),
                fixes.get("event_location"),
                fixes.get("event_location_standardized"),
            ),
        )
        return

    city, country, location = row
    is_empty = not any(
        v and str(v).strip() and str(v).strip().lower() != "nan"
        for v in (city, country, location)
    )
    if not is_empty and not force:
        return

    cur.execute(
        """
        UPDATE core.locations
        SET event_city = %s,
            event_state = %s,
            event_country = %s,
            event_location = %s,
            event_location_standardized = %s,
            latitude = COALESCE(%s::numeric, latitude),
            longitude = COALESCE(%s::numeric, longitude),
            coordinates_valid = CASE
                WHEN %s::numeric IS NOT NULL AND %s::numeric IS NOT NULL THEN true
                ELSE coordinates_valid
            END
        WHERE location_id = %s
        """,
        (
            fixes.get("event_city"),
            fixes.get("event_state") or None,
            fixes.get("event_country"),
            fixes.get("event_location"),
            fixes.get("event_location_standardized"),
            fixes.get("latitude"),
            fixes.get("longitude"),
            fixes.get("latitude"),
            fixes.get("longitude"),
            location_id,
        ),
    )


def enrich_core_known_events(conn: psycopg.Connection) -> None:
    """Patch catalog URLs and empty location rows for events WSDC omits from events_wsdc."""
    with conn.cursor() as cur:
        for event_id, meta in KNOWN_EVENT_METADATA.items():
            url = meta.get("url")
            name = meta.get("name")
            if url:
                cur.execute(
                    """
                    UPDATE core.events
                    SET url = %s
                    WHERE event_id = %s
                    """,
                    (url, event_id),
                )
            if name:
                # Force KNOWN title (e.g. UpTown Swing over stale Swedish Swing
                # Summer Camp on shared event_id 264). Empty-only COALESCE left
                # rebrands stuck and weekend probe pending forever.
                cur.execute(
                    """
                    UPDATE core.events
                    SET name = %s
                    WHERE event_id = %s
                      AND COALESCE(NULLIF(TRIM(name), ''), '') IS DISTINCT FROM %s
                    """,
                    (name, event_id, name),
                )

        for event_id, fixes in event_location_patches().items():
            cur.execute(
                """
                SELECT DISTINCT location_id
                FROM core.results
                WHERE event_id = %s AND location_id IS NOT NULL
                """,
                (event_id,),
            )
            for (location_id,) in cur.fetchall():
                _apply_location_patch(cur, int(location_id), fixes)

        for location_id, fixes in LOCATION_ID_CORRECTIONS.items():
            _apply_location_patch(cur, int(location_id), fixes, force=True)
