-- Core: normalized current state.
-- Canonical value format = full words ("Follower", "Intermediate", "All-Star"),
-- matching the old-laptop CSVs that the Tableau dashboards were built on.
-- Abbreviated forms used by the optimized parser map via core.levels.

-- Level dictionary: canonical name, parser abbreviation, progression order.
CREATE TABLE IF NOT EXISTS core.levels (
    level       text PRIMARY KEY,
    level_abbr  text NOT NULL UNIQUE,
    sort_order  int  NOT NULL
);

INSERT INTO core.levels (level, level_abbr, sort_order) VALUES
    ('Newcomer',      'NEW',  10),
    ('Novice',        'NOV',  20),
    ('Intermediate',  'INT',  30),
    ('Advanced',      'ADV',  40),
    ('All-Star',      'ALS',  50),
    ('Champion',      'CHMP', 60),
    ('Master',        'MSTR', 70),
    ('Invitational',  'INV',  80),
    ('Professional',  'PRO',  90),
    ('Teacher',       'TCH',  100),
    ('Sophisticated', 'SPH',  110),
    ('Juniors',       'JRS',  120)
ON CONFLICT (level) DO NOTHING;

CREATE TABLE IF NOT EXISTS core.dancers (
    dancer_id   int PRIMARY KEY,
    dancer_name text
);

CREATE TABLE IF NOT EXISTS core.locations (
    location_id                 int PRIMARY KEY,
    event_city                  text,
    event_state                 text,
    event_country               text,
    latitude                    numeric,
    longitude                   numeric,
    event_location              text,
    event_location_standardized text,
    coordinates_valid           boolean
);

CREATE TABLE IF NOT EXISTS core.events (
    event_id int PRIMARY KEY,   -- WSDC event id ("id" / "event_name_id" in CSVs)
    name     text NOT NULL,
    url      text
);

-- Maps raw event-name variants from either parser version to a canonical event.
CREATE TABLE IF NOT EXISTS core.event_aliases (
    alias    text PRIMARY KEY,
    event_id int NOT NULL REFERENCES core.events
);

CREATE TABLE IF NOT EXISTS core.event_instances (
    event_instance_id int PRIMARY KEY,
    event_id          int REFERENCES core.events,
    location_id       int REFERENCES core.locations,
    location_raw      text,
    date_raw          text,    -- "July 1991" as published by WSDC
    event_date        date,    -- parsed_date
    event_year        int,
    event_month       int
);

CREATE TABLE IF NOT EXISTS core.results (
    result_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dancer_id           int  NOT NULL REFERENCES core.dancers,
    event_id            int  REFERENCES core.events,
    location_id         int  REFERENCES core.locations,
    dance               text,
    division            text,    -- event_competition
    role                text CHECK (role IN ('Leader', 'Follower')),
    event_year          int,
    event_month         int,
    event_date          date,    -- event_year_and_month
    result_raw          text,    -- event_result: "1".."5", "F" (finalist) etc.
    result_standardized text,
    points              int
);

CREATE INDEX IF NOT EXISTS results_dancer_idx ON core.results (dancer_id);
CREATE INDEX IF NOT EXISTS results_event_idx  ON core.results (event_id, event_year, event_month);

-- Current points per dancer/role/dance/level (full snapshot, replaced per run).
CREATE TABLE IF NOT EXISTS core.dancer_points (
    dancer_id    int  NOT NULL REFERENCES core.dancers,
    role         text NOT NULL CHECK (role IN ('Leader', 'Follower')),
    dance        text NOT NULL,
    level        text NOT NULL REFERENCES core.levels,
    total_points int  NOT NULL,
    update_date  date,
    PRIMARY KEY (dancer_id, role, dance, level)
);

-- Current per-dancer role summary (full snapshot, replaced per run).
CREATE TABLE IF NOT EXISTS core.dancer_roles (
    dancer_id                              int PRIMARY KEY REFERENCES core.dancers,
    dominate_role                          text,
    dominate_required                      text,
    dominate_allowed                       text,
    non_dominate_role                      text,
    non_dominate_required                  text,
    non_dominate_allowed                   text,
    non_dominate_recommended               text,
    non_dominate_role_highest_level_points text,
    non_dominate_role_highest_level        text,
    update_date                            date
);
