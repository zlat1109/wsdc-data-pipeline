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
RETURNING event_id, event_year, event_month, location_id, event_name
"""

LOCATION_COUNTRY_SQL = """
SELECT location_id, lower(coalesce(nullif(trim(event_country), ''), ''))
FROM core.locations
WHERE location_id = ANY(%s)
"""

RESOLVE_LOCATION_TEXT_SQL = """
SELECT location_id
FROM core.locations
WHERE lower(trim(coalesce(event_location_standardized, ''))) = lower(trim(%s))
   OR lower(trim(coalesce(event_location, ''))) = lower(trim(%s))
ORDER BY location_id
LIMIT 1
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


def find_poison_seed_auto_adds(conn, auto_rows: list[tuple]) -> list[dict[str, Any]]:
    """Flag auto-added baseline rows that disagree with EVENT_NAME_LOCATION_OVERRIDES.

    Auto-add freezes whatever edition.location_id is present. If that lid is already a
    shared wrong lid, drift stays silent — surface those seeds for Telegram attention.
    Still inserts the row (does not block load).
    """
    if not auto_rows:
        return []
    from transform.knowledge.events import (
        EVENT_NAME_LOCATION_OVERRIDES,
        EVENT_NAME_YEAR_LOCATION_OVERRIDES,
    )

    lids = sorted({int(r[3]) for r in auto_rows if r[3] is not None})
    country_by_lid: dict[int, str] = {}

    def _load_countries(extra: list[int]) -> None:
        need = [lid for lid in extra if lid not in country_by_lid]
        if not need:
            return
        with conn.cursor() as cur:
            cur.execute(LOCATION_COUNTRY_SQL, (need,))
            for lid, country in cur.fetchall():
                country_by_lid[int(lid)] = str(country or "")

    _load_countries(lids)

    resolve_cache: dict[str, int | None] = {}

    def _resolve(text: str) -> int | None:
        key = text.strip().lower()
        if key in resolve_cache:
            return resolve_cache[key]
        with conn.cursor() as cur:
            cur.execute(RESOLVE_LOCATION_TEXT_SQL, (text, text))
            row = cur.fetchone()
        lid = int(row[0]) if row else None
        resolve_cache[key] = lid
        if lid is not None:
            _load_countries([lid])
        return lid

    def _target_for(name: str, year: int) -> str | None:
        target = EVENT_NAME_LOCATION_OVERRIDES.get(name)
        for (n, y0, y1), loc_text in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
            if n == name and y0 <= year <= y1:
                return loc_text
        return target

    suspects: list[dict[str, Any]] = []
    for event_id, event_year, event_month, location_id, event_name in auto_rows:
        name = str(event_name or "")
        year = int(event_year)
        target = _target_for(name, year)
        if not target:
            continue
        override_lid = _resolve(target)
        if override_lid is None:
            continue
        current_lid = int(location_id)
        if current_lid == override_lid:
            continue
        cur_country = country_by_lid.get(current_lid, "")
        ov_country = country_by_lid.get(override_lid, "")
        # If we have countries and they match, same-country city move — skip noise.
        if cur_country and ov_country and cur_country == ov_country:
            continue
        suspects.append(
            {
                "event_id": int(event_id),
                "event_year": year,
                "event_month": int(event_month),
                "event_name": name,
                "location_id": current_lid,
                "override_location_id": override_lid,
                "override_location": target,
                "current_country": cur_country,
                "override_country": ov_country,
            }
        )
    return suspects


def sync_edition_location_baseline_after_load(conn) -> dict[str, Any]:
    """Detect drifts, auto-add new edition keys, return summary (does not mutate drifts)."""
    drifts = find_edition_location_drifts(conn)
    with conn.cursor() as cur:
        cur.execute(AUTO_ADD_SQL)
        auto_rows = cur.fetchall()
    poison = find_poison_seed_auto_adds(conn, auto_rows)
    return {
        "drift_count": len(drifts),
        "auto_added": len(auto_rows),
        "drifts": [d.to_dict() for d in drifts[:100]],
        "poison_seed_suspects": poison,
    }
