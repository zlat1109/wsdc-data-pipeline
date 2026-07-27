-- @docs-summary: WSDC tier rules reference (editions, competitor ranges, Chart 5 points)
-- Source of truth: transform/knowledge/tier_rules.py via scripts/load_tier_rules.py

CREATE TABLE IF NOT EXISTS core.rules_editions (
    rules_version         text PRIMARY KEY,
    valid_from            date NOT NULL,
    valid_to              date,
    tier_basis            text NOT NULL
        CHECK (tier_basis IN ('none', 'smaller_role', 'per_role')),
    min_role_competitors  int NOT NULL DEFAULT 5,
    points_depth          int NOT NULL DEFAULT 5,
    inherits_from         text REFERENCES core.rules_editions (rules_version),
    source_url            text,
    source                text NOT NULL,
    notes                 text,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.tier_definitions (
    rules_version       text NOT NULL REFERENCES core.rules_editions (rules_version),
    tier                int NOT NULL CHECK (tier >= 0),
    min_competitors     int NOT NULL CHECK (min_competitors >= 0),
    max_competitors     int,
    prelim_rounds       int NOT NULL DEFAULT 1,
    finalist_points     int NOT NULL DEFAULT 0,
    source              text NOT NULL,
    PRIMARY KEY (rules_version, tier),
    CHECK (max_competitors IS NULL OR max_competitors >= min_competitors)
);

CREATE TABLE IF NOT EXISTS core.tier_points (
    rules_version   text NOT NULL,
    tier            int NOT NULL,
    placement       int NOT NULL CHECK (placement BETWEEN 1 AND 5),
    points          int NOT NULL CHECK (points >= 0),
    source          text NOT NULL,
    PRIMARY KEY (rules_version, tier, placement),
    FOREIGN KEY (rules_version, tier)
        REFERENCES core.tier_definitions (rules_version, tier)
);

CREATE INDEX IF NOT EXISTS rules_editions_valid_idx
    ON core.rules_editions (valid_from, valid_to);

COMMENT ON TABLE core.rules_editions IS
    'WSDC Points Registry / Event Rules editions with validity windows and tier basis.';
COMMENT ON TABLE core.tier_definitions IS
    'Per-edition Tier competitor ranges, prelim rounds, and finalist point awards.';
COMMENT ON TABLE core.tier_points IS
    'Chart 5 (Points Awarded per Tier): points for placements 1-5.';

CREATE SCHEMA IF NOT EXISTS export;

CREATE OR REPLACE VIEW export.tier_rules AS
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
    d.source AS definition_source,
    MAX(p.points) FILTER (WHERE p.placement = 1) AS points_1st,
    MAX(p.points) FILTER (WHERE p.placement = 2) AS points_2nd,
    MAX(p.points) FILTER (WHERE p.placement = 3) AS points_3rd,
    MAX(p.points) FILTER (WHERE p.placement = 4) AS points_4th,
    MAX(p.points) FILTER (WHERE p.placement = 5) AS points_5th
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
    d.source
ORDER BY e.valid_from, d.tier;
