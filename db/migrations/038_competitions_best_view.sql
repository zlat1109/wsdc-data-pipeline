-- @docs-summary: competitions consistency checks + best-row export view
-- Follow-up to 037: prevent level_id/level drift, enforce match_status↔edition_id,
-- and expose one preferred row per (edition_id, level) so SUM counts stay safe.

ALTER TABLE core.competitions
    DROP CONSTRAINT IF EXISTS competitions_match_edition_chk;

ALTER TABLE core.competitions
    ADD CONSTRAINT competitions_match_edition_chk CHECK (
        (match_status = 'matched' AND edition_id IS NOT NULL)
        OR (match_status = 'unmatched' AND edition_id IS NULL)
    );

CREATE OR REPLACE FUNCTION core.competitions_level_pair_ok()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.levels l
        WHERE l.level_id = NEW.level_id
          AND l.level = NEW.level
    ) THEN
        RAISE EXCEPTION
            'competitions level_id=% does not match level=%',
            NEW.level_id, NEW.level;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS competitions_level_pair_trg ON core.competitions;
CREATE TRIGGER competitions_level_pair_trg
    BEFORE INSERT OR UPDATE OF level_id, level
    ON core.competitions
    FOR EACH ROW
    EXECUTE FUNCTION core.competitions_level_pair_ok();

COMMENT ON FUNCTION core.competitions_level_pair_ok() IS
    'Enforce core.competitions.(level_id, level) matches core.levels pair.';

-- One preferred dump row per matched edition+division.
-- Prefer rows with both role counts, then newest dump_updated_at, then highest id.
CREATE OR REPLACE VIEW export.competitions_best AS
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
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY edition_id, level
            ORDER BY
                (leader_count IS NOT NULL AND follower_count IS NOT NULL) DESC,
                dump_updated_at DESC NULLS LAST,
                competition_id DESC
        ) AS rn
    FROM core.competitions
    WHERE match_status = 'matched'
      AND edition_id IS NOT NULL
) c
JOIN core.event_editions ed ON ed.edition_id = c.edition_id
LEFT JOIN core.events e ON e.event_id = ed.event_id
WHERE c.rn = 1;

COMMENT ON VIEW export.competitions_best IS
    'Deduped matched competitions: one row per (edition_id, level). '
    'Use this for headcount analytics; core.competitions keeps full dump lineage '
    '(multiple competitionevents can collapse onto the same edition month).';
