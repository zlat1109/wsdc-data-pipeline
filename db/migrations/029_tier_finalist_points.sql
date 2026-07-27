-- @docs-summary: Tier points placement 0 = finalist award; finalist_max_place; status rollup fix
-- Extends 027/028: Chart 5 places 1-5 plus additional-finalist points; severity-aware entries view.

ALTER TABLE core.tier_definitions
    ADD COLUMN IF NOT EXISTS finalist_max_place int;

COMMENT ON COLUMN core.tier_definitions.finalist_points IS
    'Points awarded to additional finalists beyond top 5 (0 if none).';
COMMENT ON COLUMN core.tier_definitions.finalist_max_place IS
    'Highest place receiving finalist_points (NULL = all remaining finalists / N/A).';

ALTER TABLE core.tier_points
    DROP CONSTRAINT IF EXISTS tier_points_placement_check;

ALTER TABLE core.tier_points
    ADD CONSTRAINT tier_points_placement_check
    CHECK (placement BETWEEN 0 AND 5);

COMMENT ON TABLE core.tier_points IS
    'Chart 5 places 1-5 plus placement=0 for additional-finalist points.';

-- CREATE OR REPLACE cannot insert/reorder columns; recreate export views.
DROP VIEW IF EXISTS export.edition_division_entries;
DROP VIEW IF EXISTS export.tier_rules;

CREATE VIEW export.tier_rules AS
SELECT
    e.rules_version,
    e.valid_from,
    e.valid_to,
    e.tier_basis,
    e.min_role_competitors,
    e.points_depth,
    e.inherits_from,
    e.source_url,
    e.source AS edition_source,
    e.notes,
    d.tier,
    d.min_competitors,
    d.max_competitors,
    d.prelim_rounds,
    d.finalist_points,
    d.finalist_max_place,
    d.source AS definition_source,
    MAX(p.points) FILTER (WHERE p.placement = 1) AS points_1st,
    MAX(p.points) FILTER (WHERE p.placement = 2) AS points_2nd,
    MAX(p.points) FILTER (WHERE p.placement = 3) AS points_3rd,
    MAX(p.points) FILTER (WHERE p.placement = 4) AS points_4th,
    MAX(p.points) FILTER (WHERE p.placement = 5) AS points_5th,
    MAX(p.points) FILTER (WHERE p.placement = 0) AS points_finalist
FROM core.rules_editions e
JOIN core.tier_definitions d ON d.rules_version = e.rules_version
LEFT JOIN core.tier_points p
    ON p.rules_version = d.rules_version AND p.tier = d.tier
GROUP BY
    e.rules_version,
    e.valid_from,
    e.valid_to,
    e.tier_basis,
    e.min_role_competitors,
    e.points_depth,
    e.inherits_from,
    e.source_url,
    e.source,
    e.notes,
    d.tier,
    d.min_competitors,
    d.max_competitors,
    d.prelim_rounds,
    d.finalist_points,
    d.finalist_max_place,
    d.source
ORDER BY e.valid_from, d.tier;

CREATE VIEW export.edition_division_entries AS
WITH ranked AS (
    SELECT
        t.*,
        CASE t.status
            WHEN 'unmatched' THEN 6
            WHEN 'ambiguous' THEN 5
            WHEN 'no_points' THEN 4
            WHEN 'legacy_chart' THEN 3
            WHEN 'no_tier_system' THEN 2
            WHEN 'matched' THEN 1
            ELSE 0
        END AS status_rank
    FROM export.edition_division_tiers t
),
roles AS (
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
        (ARRAY_AGG(status ORDER BY status_rank DESC)
            FILTER (WHERE role = 'Leader'))[1] AS leader_status,
        (ARRAY_AGG(status ORDER BY status_rank DESC)
            FILTER (WHERE role = 'Follower'))[1] AS follower_status,
        MAX(scored_dancers) FILTER (WHERE role = 'Leader') AS leader_scored,
        MAX(scored_dancers) FILTER (WHERE role = 'Follower') AS follower_scored,
        MAX(est_min_competitors) FILTER (WHERE role = 'Leader') AS leader_est_min,
        MAX(est_max_competitors) FILTER (WHERE role = 'Leader') AS leader_est_max,
        MAX(est_min_competitors) FILTER (WHERE role = 'Follower') AS follower_est_min,
        MAX(est_max_competitors) FILTER (WHERE role = 'Follower') AS follower_est_max,
        BOOL_OR(range_conflict) AS range_conflict,
        (ARRAY_AGG(status ORDER BY status_rank DESC))[1] AS worst_status
    FROM ranked
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
    worst_status,
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
