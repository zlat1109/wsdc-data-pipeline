-- Competition Results enrichment (scrape layer absent from WSDC public results).
-- Parallel to core.results: prelims/semis/quarters, unscored finalists, partners,
-- judge marks, other divisions. Nullable FKs — never invent dancers/events.

CREATE TABLE IF NOT EXISTS core.cr_loads (
    load_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loaded_at     timestamptz NOT NULL DEFAULT now(),
    source_file   text NOT NULL,
    file_sha256   text,
    row_counts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    match_stats   jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE core.cr_loads IS
    'One row per Competition Results load into core.cr_*.';

CREATE TABLE IF NOT EXISTS core.cr_editions (
    cr_edition_id      text PRIMARY KEY,  -- wsdc:<id>:<Month YYYY>
    wsdc_event_id      int,
    cr_name            text,
    cr_date            date,
    edition_id         bigint REFERENCES core.event_editions (edition_id),
    match_status       text NOT NULL
        CHECK (match_status IN ('matched', 'unmatched')),
    scoring_source     text,              -- eepro / scoringdance / …
    filing_year        int,
    filing_month       int,
    canonical_event_id int,
    load_id            bigint REFERENCES core.cr_loads (load_id)
);

CREATE INDEX IF NOT EXISTS cr_editions_edition_idx
    ON core.cr_editions (edition_id);
CREATE INDEX IF NOT EXISTS cr_editions_match_idx
    ON core.cr_editions (match_status);
CREATE INDEX IF NOT EXISTS cr_editions_source_idx
    ON core.cr_editions (scoring_source);

COMMENT ON TABLE core.cr_editions IS
    'Competition Results editions linked to core.event_editions when matched.';

CREATE TABLE IF NOT EXISTS core.cr_divisions (
    cr_division_id     text PRIMARY KEY,  -- {cr_edition_id}#{raw_division}
    cr_edition_id      text NOT NULL REFERENCES core.cr_editions (cr_edition_id)
        ON DELETE CASCADE,
    raw_division       text NOT NULL,
    level              text REFERENCES core.levels (level),
    category           text NOT NULL
        CHECK (category IN ('skill', 'age', 'strictly', 'fun', 'pro-am')),
    label              text NOT NULL,
    competition_bucket text,
    UNIQUE (cr_edition_id, raw_division)
);

CREATE INDEX IF NOT EXISTS cr_divisions_level_idx
    ON core.cr_divisions (level);
CREATE INDEX IF NOT EXISTS cr_divisions_category_idx
    ON core.cr_divisions (category);

COMMENT ON TABLE core.cr_divisions IS
    'Per-edition divisions from Competition Results (skill + age/fun/strictly).';

CREATE TABLE IF NOT EXISTS core.cr_rounds (
    cr_round_id        text PRIMARY KEY,  -- {cr_division_id}#{round}
    cr_division_id     text NOT NULL REFERENCES core.cr_divisions (cr_division_id)
        ON DELETE CASCADE,
    round              text NOT NULL
        CHECK (round IN ('prelim', 'quarter', 'semi', 'final')),
    source_url         text,
    total_competitors  int,
    UNIQUE (cr_division_id, round)
);

CREATE INDEX IF NOT EXISTS cr_rounds_round_idx
    ON core.cr_rounds (round);

COMMENT ON TABLE core.cr_rounds IS
    'Rounds within a CR division (prelim / quarter / semi / final).';

CREATE TABLE IF NOT EXISTS core.cr_round_results (
    cr_round_result_id bigint PRIMARY KEY,
    cr_round_id        text NOT NULL REFERENCES core.cr_rounds (cr_round_id)
        ON DELETE CASCADE,
    role               text NOT NULL CHECK (role IN ('Leader', 'Follower')),
    cr_identity        text NOT NULL,
    dancer_id          int REFERENCES core.dancers (dancer_id),
    competitor_name    text,
    place              text,
    callback           text,
    partner_cr_identity text,
    partner_dancer_id  int REFERENCES core.dancers (dancer_id)
);

CREATE INDEX IF NOT EXISTS cr_round_results_round_idx
    ON core.cr_round_results (cr_round_id);
CREATE INDEX IF NOT EXISTS cr_round_results_dancer_idx
    ON core.cr_round_results (dancer_id);
CREATE INDEX IF NOT EXISTS cr_round_results_identity_idx
    ON core.cr_round_results (cr_identity);

COMMENT ON TABLE core.cr_round_results IS
    'One competitor per round. dancer_id set only for known WSDC ids; '
    'redacted competitors keep cr_identity and null name.';

CREATE TABLE IF NOT EXISTS core.cr_final_couples (
    couple_id           bigint PRIMARY KEY,
    cr_round_id         text NOT NULL REFERENCES core.cr_rounds (cr_round_id)
        ON DELETE CASCADE,
    leader_result_id    bigint NOT NULL
        REFERENCES core.cr_round_results (cr_round_result_id) ON DELETE CASCADE,
    follower_result_id  bigint NOT NULL
        REFERENCES core.cr_round_results (cr_round_result_id) ON DELETE CASCADE,
    place               text,
    UNIQUE (cr_round_id, leader_result_id, follower_result_id)
);

CREATE INDEX IF NOT EXISTS cr_final_couples_round_idx
    ON core.cr_final_couples (cr_round_id);

COMMENT ON TABLE core.cr_final_couples IS
    'Finals: one row per dancing couple (judge ranks the pair).';

CREATE TABLE IF NOT EXISTS core.cr_judge_marks (
    judge_mark_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cr_round_result_id  bigint REFERENCES core.cr_round_results (cr_round_result_id)
        ON DELETE CASCADE,
    couple_id           bigint REFERENCES core.cr_final_couples (couple_id)
        ON DELETE CASCADE,
    judge_name          text NOT NULL,
    mark                text NOT NULL,
    CONSTRAINT cr_judge_marks_target_chk CHECK (
        (cr_round_result_id IS NOT NULL AND couple_id IS NULL)
        OR (cr_round_result_id IS NULL AND couple_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS cr_judge_marks_result_idx
    ON core.cr_judge_marks (cr_round_result_id);
CREATE INDEX IF NOT EXISTS cr_judge_marks_couple_idx
    ON core.cr_judge_marks (couple_id);
CREATE INDEX IF NOT EXISTS cr_judge_marks_judge_idx
    ON core.cr_judge_marks (judge_name);

COMMENT ON TABLE core.cr_judge_marks IS
    'Long-form marks: per competitor in prelim/semi/quarter; per couple in finals.';

-- Export views ----------------------------------------------------------------

CREATE OR REPLACE VIEW export.cr_editions AS
SELECT
    e.cr_edition_id,
    e.wsdc_event_id,
    e.cr_name,
    e.cr_date,
    e.edition_id,
    e.match_status,
    e.scoring_source,
    e.filing_year,
    e.filing_month,
    e.canonical_event_id,
    ed.event_id,
    ev.name AS event_name,
    ed.event_year,
    ed.event_month,
    ed.start_date,
    ed.end_date,
    e.load_id
FROM core.cr_editions e
LEFT JOIN core.event_editions ed ON ed.edition_id = e.edition_id
LEFT JOIN core.events ev ON ev.event_id = ed.event_id;

CREATE OR REPLACE VIEW export.cr_round_results AS
SELECT
    rr.cr_round_result_id,
    rr.cr_round_id,
    r.round,
    rr.role,
    rr.cr_identity,
    rr.dancer_id,
    rr.competitor_name,
    rr.place,
    rr.callback,
    rr.partner_cr_identity,
    rr.partner_dancer_id,
    d.cr_division_id,
    d.raw_division,
    d.level,
    d.category,
    d.label,
    d.competition_bucket,
    e.cr_edition_id,
    e.edition_id,
    e.match_status,
    e.scoring_source,
    ed.event_id,
    ev.name AS event_name,
    ed.event_year,
    ed.event_month,
    r.source_url
FROM core.cr_round_results rr
JOIN core.cr_rounds r ON r.cr_round_id = rr.cr_round_id
JOIN core.cr_divisions d ON d.cr_division_id = r.cr_division_id
JOIN core.cr_editions e ON e.cr_edition_id = d.cr_edition_id
LEFT JOIN core.event_editions ed ON ed.edition_id = e.edition_id
LEFT JOIN core.events ev ON ev.event_id = ed.event_id;

CREATE OR REPLACE VIEW export.cr_judge_marks AS
SELECT
    jm.judge_mark_id,
    jm.judge_name,
    jm.mark,
    jm.cr_round_result_id,
    jm.couple_id,
    COALESCE(rr.cr_round_id, fc.cr_round_id) AS cr_round_id,
    CASE
        WHEN jm.couple_id IS NOT NULL THEN 'couple'
        ELSE 'competitor'
    END AS mark_target
FROM core.cr_judge_marks jm
LEFT JOIN core.cr_round_results rr ON rr.cr_round_result_id = jm.cr_round_result_id
LEFT JOIN core.cr_final_couples fc ON fc.couple_id = jm.couple_id;

-- CR finals left-joined to scored WSDC public results (unscored finalists).
CREATE OR REPLACE VIEW export.cr_finals_vs_scored AS
SELECT
    rr.cr_round_result_id,
    rr.role,
    rr.cr_identity,
    rr.dancer_id,
    rr.competitor_name,
    rr.place AS cr_place,
    rr.partner_cr_identity,
    rr.partner_dancer_id,
    d.level,
    d.label,
    d.category,
    e.cr_edition_id,
    e.edition_id,
    e.scoring_source,
    ed.event_id,
    ed.event_year,
    ed.event_month,
    res.result_id AS scored_result_id,
    res.result_raw AS scored_result_raw,
    res.points AS scored_points,
    (res.result_id IS NULL) AS unscored_finalist
FROM core.cr_round_results rr
JOIN core.cr_rounds r ON r.cr_round_id = rr.cr_round_id AND r.round = 'final'
JOIN core.cr_divisions d ON d.cr_division_id = r.cr_division_id
JOIN core.cr_editions e ON e.cr_edition_id = d.cr_edition_id
LEFT JOIN core.event_editions ed ON ed.edition_id = e.edition_id
LEFT JOIN core.results res
  ON res.dancer_id = rr.dancer_id
 AND res.event_id = ed.event_id
 AND res.event_year = ed.event_year
 AND res.event_month = ed.event_month
 AND res.role = rr.role
 AND (
      d.level IS NULL
      OR res.division ILIKE d.level
      OR res.division ILIKE replace(d.level, '-', ' ')
      OR (d.level = 'All-Star' AND res.division ILIKE 'All-Star%')
      OR (d.level = 'Champion' AND res.division ILIKE 'Champion%')
      OR (d.level = 'Master' AND res.division ILIKE 'Master%')
 );

-- RLS defense-in-depth (service_role bypasses)
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'core.cr_loads',
    'core.cr_editions',
    'core.cr_divisions',
    'core.cr_rounds',
    'core.cr_round_results',
    'core.cr_final_couples',
    'core.cr_judge_marks'
  ]
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
