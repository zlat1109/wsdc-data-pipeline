-- @docs-summary: Infer Tier and competitor ranges per edition/division/role/dance
-- Rebuilt by db/build_edition_tiers.py after each points load / catalog rebuild.

CREATE TABLE IF NOT EXISTS core.edition_division_tiers (
    event_id                int NOT NULL,
    event_year              int NOT NULL,
    event_month             int NOT NULL,
    division                text NOT NULL,
    role                    text NOT NULL
        CHECK (role IN ('Leader', 'Follower')),
    dance                   text NOT NULL DEFAULT 'West Coast Swing',
    edition_id              bigint,
    rules_version           text,
    observed_points_1       int,
    observed_points_2       int,
    observed_points_3       int,
    observed_points_4       int,
    observed_points_5       int,
    finalists               int NOT NULL DEFAULT 0,
    scored_dancers          int NOT NULL DEFAULT 0,
    tier                    int,
    status                  text NOT NULL
        CHECK (status IN (
            'matched', 'legacy_chart', 'no_tier_system',
            'no_points', 'ambiguous', 'unmatched'
        )),
    vector_distance         int NOT NULL DEFAULT 0,
    range_basis             text
        CHECK (range_basis IS NULL OR range_basis IN ('per_role', 'smaller_role', 'none')),
    rule_min_competitors    int,
    rule_max_competitors    int,
    est_min_competitors     int,
    est_max_competitors     int,
    range_conflict          boolean NOT NULL DEFAULT false,
    updated_at              timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, event_year, event_month, division, role, dance)
);

CREATE INDEX IF NOT EXISTS edition_division_tiers_edition_idx
    ON core.edition_division_tiers (edition_id);

CREATE INDEX IF NOT EXISTS edition_division_tiers_status_idx
    ON core.edition_division_tiers (status);

CREATE INDEX IF NOT EXISTS edition_division_tiers_year_idx
    ON core.edition_division_tiers (event_year, event_month);

COMMENT ON TABLE core.edition_division_tiers IS
    'Inferred Tier + competitor range per edition/division/role/dance from Chart 5 vectors.';

CREATE OR REPLACE VIEW export.edition_division_tiers AS
SELECT
    t.edition_id,
    t.event_id,
    e.name AS event_name,
    t.event_year,
    t.event_month,
    t.division,
    t.role,
    t.dance,
    t.rules_version,
    t.observed_points_1,
    t.observed_points_2,
    t.observed_points_3,
    t.observed_points_4,
    t.observed_points_5,
    t.finalists,
    t.scored_dancers,
    t.tier,
    t.status,
    t.vector_distance,
    t.range_basis,
    t.rule_min_competitors,
    t.rule_max_competitors,
    t.est_min_competitors,
    t.est_max_competitors,
    t.range_conflict,
    t.updated_at
FROM core.edition_division_tiers t
LEFT JOIN core.events e ON e.event_id = t.event_id
ORDER BY t.event_year DESC, t.event_month DESC, e.name, t.division, t.role;

-- Rollup: competitor range estimate at division (both roles) grain.
CREATE OR REPLACE VIEW export.edition_division_entries AS
WITH roles AS (
    SELECT
        edition_id,
        event_id,
        event_year,
        event_month,
        division,
        dance,
        MAX(event_name) AS event_name,
        COUNT(*) FILTER (WHERE role = 'Leader') AS leader_rows,
        COUNT(*) FILTER (WHERE role = 'Follower') AS follower_rows,
        MAX(tier) FILTER (WHERE role = 'Leader') AS leader_tier,
        MAX(tier) FILTER (WHERE role = 'Follower') AS follower_tier,
        MAX(status) FILTER (WHERE role = 'Leader') AS leader_status,
        MAX(status) FILTER (WHERE role = 'Follower') AS follower_status,
        MAX(est_min_competitors) FILTER (WHERE role = 'Leader') AS leader_est_min,
        MAX(est_max_competitors) FILTER (WHERE role = 'Leader') AS leader_est_max,
        MAX(est_min_competitors) FILTER (WHERE role = 'Follower') AS follower_est_min,
        MAX(est_max_competitors) FILTER (WHERE role = 'Follower') AS follower_est_max,
        MAX(scored_dancers) FILTER (WHERE role = 'Leader') AS leader_scored,
        MAX(scored_dancers) FILTER (WHERE role = 'Follower') AS follower_scored,
        BOOL_OR(range_conflict) AS range_conflict
    FROM export.edition_division_tiers
    GROUP BY edition_id, event_id, event_year, event_month, division, dance
)
SELECT
    edition_id,
    event_id,
    event_name,
    event_year,
    event_month,
    division,
    dance,
    leader_tier,
    follower_tier,
    leader_status,
    follower_status,
    leader_scored,
    follower_scored,
    CASE
        WHEN leader_rows > 0 AND follower_rows > 0
            AND leader_est_min IS NOT NULL AND follower_est_min IS NOT NULL
        THEN leader_est_min + follower_est_min
        ELSE NULL
    END AS est_min_entries,
    CASE
        WHEN leader_rows > 0 AND follower_rows > 0
            AND leader_est_max IS NOT NULL AND follower_est_max IS NOT NULL
        THEN leader_est_max + follower_est_max
        ELSE NULL
    END AS est_max_entries,
    (leader_rows > 0 AND follower_rows > 0) AS both_roles_present,
    range_conflict
FROM roles
ORDER BY event_year DESC, event_month DESC, event_name, division;
