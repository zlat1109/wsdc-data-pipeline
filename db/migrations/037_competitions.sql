-- @docs-summary: WSDC dump competitions (exact role counts) + level_id on core.levels
-- Enrichment from local MySQL clone ``competitions`` (WCS only). Parallel to
-- estimated ``edition_division_tiers``; prefer these counts when matched.

ALTER TABLE core.levels
    ADD COLUMN IF NOT EXISTS level_id int;

UPDATE core.levels SET level_id = 1  WHERE level = 'Juniors';
UPDATE core.levels SET level_id = 2  WHERE level = 'Master';
UPDATE core.levels SET level_id = 3  WHERE level = 'Newcomer';
UPDATE core.levels SET level_id = 4  WHERE level = 'Novice';
UPDATE core.levels SET level_id = 5  WHERE level = 'Intermediate';
UPDATE core.levels SET level_id = 6  WHERE level = 'Advanced';
UPDATE core.levels SET level_id = 7  WHERE level = 'Champion';
UPDATE core.levels SET level_id = 8  WHERE level = 'All-Star';
UPDATE core.levels SET level_id = 9  WHERE level = 'Invitational';
UPDATE core.levels SET level_id = 10 WHERE level = 'Professional';
UPDATE core.levels SET level_id = 12 WHERE level = 'Sophisticated';
UPDATE core.levels SET level_id = 13 WHERE level = 'Teacher';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM core.levels WHERE level_id IS NULL) THEN
        RAISE EXCEPTION 'core.levels.level_id backfill incomplete';
    END IF;
END $$;

ALTER TABLE core.levels
    ALTER COLUMN level_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS levels_level_id_uidx
    ON core.levels (level_id);

COMMENT ON COLUMN core.levels.level_id IS
    'Stable int id aligned with WSDC dump divisions.id (abbr match). '
    'Dump All-Stars/Champions/Masters map to our All-Star/Champion/Master.';

CREATE TABLE IF NOT EXISTS core.competitions (
    competition_id       int PRIMARY KEY,
    competitionevent_id  int NOT NULL,
    edition_id           bigint REFERENCES core.event_editions (edition_id),
    level_id             int NOT NULL,
    level                text NOT NULL REFERENCES core.levels (level),
    dance                text NOT NULL DEFAULT 'West Coast Swing',
    leader_count         int,
    follower_count       int,
    finals_count         int,
    match_status         text NOT NULL
        CHECK (match_status IN ('matched', 'unmatched')),
    dump_created_at      timestamptz,
    dump_updated_at      timestamptz,
    loaded_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT competitions_level_id_fkey
        FOREIGN KEY (level_id) REFERENCES core.levels (level_id)
);

CREATE INDEX IF NOT EXISTS competitions_edition_idx
    ON core.competitions (edition_id);

CREATE INDEX IF NOT EXISTS competitions_ce_idx
    ON core.competitions (competitionevent_id);

CREATE INDEX IF NOT EXISTS competitions_match_status_idx
    ON core.competitions (match_status);

CREATE INDEX IF NOT EXISTS competitions_level_idx
    ON core.competitions (level_id);

COMMENT ON TABLE core.competitions IS
    'Exact per-edition division headcounts from WSDC dump competitions (WCS). '
    'edition_id NULL = unmatched — investigate. Prefer over tier estimates when present.';

CREATE OR REPLACE VIEW export.competitions AS
SELECT
    c.competition_id,
    c.competitionevent_id,
    c.edition_id,
    c.level_id,
    c.level,
    c.dance,
    c.leader_count,
    c.follower_count,
    c.finals_count,
    c.match_status,
    ed.event_id,
    e.name AS event_name,
    ed.event_year,
    ed.event_month,
    ed.start_date,
    ed.end_date,
    c.dump_created_at,
    c.dump_updated_at,
    c.loaded_at
FROM core.competitions c
LEFT JOIN core.event_editions ed ON ed.edition_id = c.edition_id
LEFT JOIN core.events e ON e.event_id = ed.event_id;
