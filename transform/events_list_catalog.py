"""Load points catalog for Events List mapping."""

from __future__ import annotations

from transform.events_list_mapping import CatalogEvent
from transform.events_list_normalize import normalize_url


def load_catalog() -> list[CatalogEvent]:
    from connection import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_id, name, COALESCE(url, '') FROM core.events ORDER BY name")
        events = [(int(r[0]), r[1], r[2] or "") for r in cur.fetchall()]

        cur.execute(
            """
            SELECT e.event_id, ei.location_raw, COUNT(*) AS cnt
            FROM core.event_instances ei
            JOIN core.events e ON e.event_id = ei.event_id
            WHERE ei.location_raw IS NOT NULL AND TRIM(ei.location_raw) <> ''
            GROUP BY e.event_id, ei.location_raw
            ORDER BY e.event_id, cnt DESC
            """
        )
        loc_rows = cur.fetchall()

    typical: dict[int, str] = {}
    by_event: dict[int, list[tuple[str, int]]] = {}
    for eid, loc, cnt in loc_rows:
        by_event.setdefault(eid, []).append((loc, int(cnt)))
    for eid, pairs in by_event.items():
        typical[eid] = pairs[0][0]

    return [
        CatalogEvent(
            event_id=eid,
            name=name,
            url=url,
            url_norm=normalize_url(url),
            typical_location=typical.get(eid, ""),
        )
        for eid, name, url in events
    ]
