-- Staging tables mirror the parser CSV outputs (current laptop format, 13/9/10-column versions).
-- All columns are text: casting and normalization happen in the load step.
-- Tables are truncated before each load.

CREATE TABLE IF NOT EXISTS staging.dancers_points_info (
    dancer_id    text,
    role         text,
    dance        text,
    level        text,
    total_points text,
    update_date  text
);

CREATE TABLE IF NOT EXISTS staging.dancer_role_info (
    dancer_id                              text,
    dancer_name                            text,
    dominate_role                          text,
    dominate_required                      text,
    dominate_allowed                       text,
    non_dominate_role                      text,
    non_dominate_required                  text,
    non_dominate_allowed                   text,
    non_dominate_recommended               text,
    non_dominate_role_highest_level_points text,
    non_dominate_role_highest_level        text,
    update_date                            text
);

CREATE TABLE IF NOT EXISTS staging.dancers_results_info (
    dancer_id                 text,
    event_dance               text,
    event_competition         text,
    event_role                text,
    event_name_id             text,
    event_name                text,
    event_result              text,
    event_points              text,
    event_month               text,
    event_year                text,
    location_id               text,
    event_year_and_month      text,
    event_result_standardized text
);

CREATE TABLE IF NOT EXISTS staging.location_info (
    location_id                  text,
    event_city                   text,
    event_state                  text,
    event_country                text,
    latitude                     text,
    longitude                    text,
    event_location               text,
    event_location_standardized  text,
    coordinates_valid            text
);

CREATE TABLE IF NOT EXISTS staging.events_wsdc (
    event_instance_id text,
    id                text,
    name              text,
    location          text,
    url               text,
    date              text,
    parsed_date       text,
    event_year        text,
    event_month       text,
    event_year_month  text
);

-- Backfill sources: accumulated change logs from the old workflow.
CREATE TABLE IF NOT EXISTS staging.changed_dancers_points_info (
    dancer_id    text,
    role         text,
    dance        text,
    level        text,
    total_points text,
    update_date  text
);

CREATE TABLE IF NOT EXISTS staging.changed_dancer_role_info (
    dancer_id                              text,
    dancer_name                            text,
    dominate_role                          text,
    dominate_required                      text,
    dominate_allowed                       text,
    non_dominate_role                      text,
    non_dominate_required                  text,
    non_dominate_allowed                   text,
    non_dominate_recommended               text,
    non_dominate_role_highest_level_points text,
    non_dominate_role_highest_level        text,
    update_date                            text
);
