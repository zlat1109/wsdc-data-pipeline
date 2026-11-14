-- Officials dim + edition bridge; soft link from cr_judge_marks.

CREATE TABLE IF NOT EXISTS core.officials (
    official_id      bigint PRIMARY KEY,
    canonical_name   text NOT NULL,
    name_normalized  text NOT NULL,
    dancer_id        int  -- soft FK to core.dancers (promote-safe)
);

CREATE UNIQUE INDEX IF NOT EXISTS officials_name_norm_uidx
    ON core.officials (name_normalized);
CREATE INDEX IF NOT EXISTS officials_dancer_idx
    ON core.officials (dancer_id);

COMMENT ON TABLE core.officials IS
    'Judges / chief judges / scorepersons (Results Form names, deduped).';

COMMENT ON COLUMN core.officials.dancer_id IS
    'Soft FK to core.dancers when name uniquely matches; no DB FK.';

CREATE TABLE IF NOT EXISTS core.edition_officials (
    edition_official_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id      int NOT NULL,
    event_year    int NOT NULL,
    event_month   int NOT NULL,
    official_id   bigint NOT NULL REFERENCES core.officials (official_id),
    role          text NOT NULL
        CHECK (role IN ('chief_judge', 'scoreperson', 'judge')),
    rounds        text,
    panel_order   int
);

CREATE UNIQUE INDEX IF NOT EXISTS edition_officials_uidx
    ON core.edition_officials (
        event_id, event_year, event_month, official_id, role, coalesce(panel_order, 0)
    );
CREATE INDEX IF NOT EXISTS edition_officials_official_idx
    ON core.edition_officials (official_id);
CREATE INDEX IF NOT EXISTS edition_officials_edition_idx
    ON core.edition_officials (event_id, event_year, event_month);

COMMENT ON TABLE core.edition_officials IS
    'Officials attached to an edition (Results Form panel / chief / scoreperson).';

ALTER TABLE core.cr_judge_marks
    ADD COLUMN IF NOT EXISTS official_id bigint;

COMMENT ON COLUMN core.cr_judge_marks.official_id IS
    'Soft FK to core.officials (name match); no DB FK.';

CREATE INDEX IF NOT EXISTS cr_judge_marks_official_idx
    ON core.cr_judge_marks (official_id);

CREATE OR REPLACE VIEW export.officials AS
SELECT official_id, canonical_name, name_normalized, dancer_id
FROM core.officials;

CREATE OR REPLACE VIEW export.edition_officials AS
SELECT
    eo.edition_official_id,
    eo.event_id,
    eo.event_year,
    eo.event_month,
    eo.official_id,
    o.canonical_name,
    o.dancer_id,
    eo.role,
    eo.rounds,
    eo.panel_order,
    ev.name AS event_name
FROM core.edition_officials eo
JOIN core.officials o ON o.official_id = eo.official_id
LEFT JOIN core.events ev ON ev.event_id = eo.event_id;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['core.officials', 'core.edition_officials']
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
