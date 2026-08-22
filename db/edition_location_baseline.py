"""Edition location baseline: drift detection and auto-extend after load."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EditionLocationDrift:
    event_id: int
    event_year: int
    event_month: int
    event_name: str
    baseline_location_id: int
    current_location_id: int
    baseline_location: str
    current_location: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DRIFT_SQL = """
SELECT
    b.event_id,
    b.event_year,
    b.event_month,
    COALESCE(c.canonical_name, b.event_name, '') AS event_name,
    b.location_id AS baseline_location_id,
    ed.location_id AS current_location_id,
    COALESCE(bl.event_location_standardized, bl.event_location, '') AS baseline_location,
    COALESCE(cl.event_location_standardized, cl.event_location, '') AS current_location
FROM core.edition_location_baseline b
JOIN core.event_editions ed
  ON ed.event_id = b.event_id
 AND ed.event_year = b.event_year
 AND ed.event_month = b.event_month
LEFT JOIN core.event_catalog c ON c.event_id = b.event_id
LEFT JOIN core.locations bl ON bl.location_id = b.location_id
LEFT JOIN core.locations cl ON cl.location_id = ed.location_id
WHERE ed.result_rows > 0
  AND ed.location_id IS NOT NULL
  AND ed.location_id <> b.location_id
ORDER BY ed.event_year DESC, ed.event_month DESC, c.canonical_name
"""

AUTO_ADD_SQL = """
INSERT INTO core.edition_location_baseline (
    event_id, event_year, event_month, location_id, event_name, source, updated_at
)
SELECT
    ed.event_id,
    ed.event_year,
    ed.event_month,
    ed.location_id,
    c.canonical_name,
    'auto',
    now()
FROM core.event_editions ed
JOIN core.event_catalog c ON c.event_id = ed.event_id
WHERE ed.result_rows > 0
  AND ed.location_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM core.edition_location_baseline b
      WHERE b.event_id = ed.event_id
        AND b.event_year = ed.event_year
        AND b.event_month = ed.event_month
  )
ON CONFLICT (event_id, event_year, event_month) DO NOTHING
RETURNING event_id, event_year, event_month, location_id
"""


def find_edition_location_drifts(conn) -> list[EditionLocationDrift]:
    """Edition keys in baseline whose current location_id changed."""
    with conn.cursor() as cur:
        cur.execute(DRIFT_SQL)
        rows = cur.fetchall()
    out: list[EditionLocationDrift] = []
    for row in rows:
        out.append(
            EditionLocationDrift(
                event_id=int(row[0]),
                event_year=int(row[1]),
                event_month=int(row[2]),
                event_name=str(row[3] or ""),
                baseline_location_id=int(row[4]),
                current_location_id=int(row[5]),
                baseline_location=str(row[6] or ""),
                current_location=str(row[7] or ""),
            )
        )
    return out


def sync_edition_location_baseline_after_load(conn) -> dict[str, Any]:
    """Detect drifts, auto-add new edition keys, return summary (does not mutate drifts)."""
    drifts = find_edition_location_drifts(conn)
    with conn.cursor() as cur:
        cur.execute(AUTO_ADD_SQL)
        auto_added = len(cur.fetchall())
    return {
        "drift_count": len(drifts),
        "auto_added": auto_added,
        "drifts": [d.to_dict() for d in drifts[:100]],
    }


def refresh_completed_event_editions_mv(conn) -> None:
    """Keep completed-editions directory MV in sync after load."""
    with conn.cursor() as cur:
        cur.execute("SELECT export.refresh_completed_event_editions()")
