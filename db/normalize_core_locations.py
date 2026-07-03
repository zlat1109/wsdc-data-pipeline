"""Normalize city display names in core.locations."""

from __future__ import annotations

import pandas as pd
import psycopg

from transform.geography.city import format_event_location, normalize_city_field
from transform.geography.normalize import standardize_country, standardize_location


def normalize_core_location_cities(conn: psycopg.Connection) -> int:
    updated = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT location_id, event_city, event_state, event_country,
                   event_location, event_location_standardized
            FROM core.locations
            """
        )
        rows = cur.fetchall()

        for (
            location_id,
            event_city,
            event_state,
            event_country,
            event_location,
            event_location_standardized,
        ) in rows:
            old_city = str(event_city or "").strip()
            new_city, extracted_state = normalize_city_field(old_city)
            if not new_city:
                continue

            state = str(event_state or "").strip() if event_state else ""
            if not state and extracted_state:
                state = extracted_state

            country = standardize_country(str(event_country or "").strip()) or str(
                event_country or ""
            ).strip()
            row = pd.Series(
                {
                    "event_city": new_city,
                    "event_state": state or None,
                    "event_country": country or None,
                }
            )
            new_location = format_event_location(row)
            new_standardized = standardize_location(row)

            old_location = str(event_location or "").strip()
            old_standardized = str(event_location_standardized or "").strip()

            if (
                new_city == old_city
                and (not extracted_state or state == str(event_state or "").strip())
                and new_location == old_location
                and new_standardized == old_standardized
            ):
                continue

            cur.execute(
                """
                UPDATE core.locations
                SET event_city = %s,
                    event_state = %s,
                    event_country = %s,
                    event_location = %s,
                    event_location_standardized = %s
                WHERE location_id = %s
                """,
                (
                    new_city,
                    state or None,
                    country or None,
                    new_location or old_location,
                    new_standardized or old_standardized,
                    location_id,
                ),
            )
            updated += 1

    return updated
