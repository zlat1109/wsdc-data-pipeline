-- Frozen (event_id, event_year, event_month) → location_id pairs for drift detection.
-- Seeded from completed editions; auto-extended after clean load (see db/edition_location_baseline.py).
-- @docs-summary: Edition location baseline table + export view + seed

CREATE TABLE IF NOT EXISTS core.edition_location_baseline (
    event_id     int  NOT NULL REFERENCES core.events (event_id),
    event_year   int  NOT NULL,
    event_month  int  NOT NULL,
    location_id  int  NOT NULL REFERENCES core.locations (location_id),
    event_name   text,
    source       text NOT NULL DEFAULT 'seed'
        CHECK (source IN ('seed', 'seed_mv', 'auto', 'manual')),
    seeded_at    timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, event_year, event_month)
);

CREATE INDEX IF NOT EXISTS edition_location_baseline_location_idx
    ON core.edition_location_baseline (location_id);

COMMENT ON TABLE core.edition_location_baseline IS
    'Golden edition→location_id map. Compared on each load; drifts → manual review. '
    'New edition keys auto-added when absent from baseline. Update manually in Supabase '
    'after approving a legitimate venue change.';

DROP VIEW IF EXISTS export.edition_location_baseline;
CREATE VIEW export.edition_location_baseline AS
SELECT
    b.event_id,
    b.event_year,
    b.event_month,
    b.location_id,
    b.event_name,
    b.source,
    l.event_city,
    l.event_state,
    l.event_country,
    l.event_location,
    l.event_location_standardized,
    b.seeded_at,
    b.updated_at
FROM core.edition_location_baseline b
LEFT JOIN core.locations l ON l.location_id = b.location_id
ORDER BY b.event_year DESC, b.event_month DESC, b.event_name;

-- One-shot seed from current results-backed editions (same grain as completed_event_editions MV).
INSERT INTO core.edition_location_baseline (
    event_id, event_year, event_month, location_id, event_name, source
)
SELECT
    ed.event_id,
    ed.event_year,
    ed.event_month,
    ed.location_id,
    c.canonical_name,
    'seed_mv'
FROM core.event_editions ed
JOIN core.event_catalog c ON c.event_id = ed.event_id
WHERE ed.result_rows > 0
  AND ed.location_id IS NOT NULL
  AND COALESCE(ed.calendar_status, 'scheduled') NOT IN ('hiatus', 'cancelled')
ON CONFLICT (event_id, event_year, event_month) DO NOTHING;
