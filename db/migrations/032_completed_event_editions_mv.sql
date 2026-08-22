-- Materialized completed-event edition directory for location / ID audits.
-- Refresh after each load: SELECT export.refresh_completed_event_editions();
-- Pre-flight audits: db/sql/audit_completed_event_location_links.sql
-- @docs-summary: MV export.completed_event_editions + refresh helper

DROP MATERIALIZED VIEW IF EXISTS export.completed_event_editions;

CREATE MATERIALIZED VIEW export.completed_event_editions AS
WITH completed AS (
    SELECT
        ed.event_id,
        ed.edition_id,
        ed.location_id,

        c.canonical_name AS event_name,

        COALESCE(
            NULLIF(btrim(l.event_city), ''),
            NULLIF(btrim(ed.place_city), '')
        ) AS city,

        COALESCE(
            NULLIF(btrim(l.event_state), ''),
            NULLIF(btrim(ed.place_state), '')
        ) AS state,

        COALESCE(
            NULLIF(btrim(l.event_country), ''),
            NULLIF(btrim(ed.place_country), '')
        ) AS country,

        CASE
            WHEN ed.start_date IS NOT NULL
             AND ed.date_source IS NOT NULL
            THEN ed.start_date
            WHEN cal.planned_start_date IS NOT NULL
             AND COALESCE(cal.calendar_status, 'scheduled')
                 NOT IN ('hiatus', 'cancelled')
            THEN cal.planned_start_date
            ELSE NULL
        END AS start_date,

        CASE
            WHEN ed.end_date IS NOT NULL
             AND ed.date_source IS NOT NULL
            THEN ed.end_date
            WHEN cal.planned_end_date IS NOT NULL
             AND COALESCE(cal.calendar_status, 'scheduled')
                 NOT IN ('hiatus', 'cancelled')
            THEN cal.planned_end_date
            ELSE NULL
        END AS end_date,

        COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
        ) AS sort_end_date,

        ed.event_month,
        ed.event_year,
        ed.result_rows,

        NULLIF(btrim(l.event_location_standardized), '') AS loc_standardized,
        NULLIF(btrim(l.event_location), '')               AS loc_registry,
        NULLIF(btrim(ed.location_raw), '')               AS loc_raw,
        c.typical_location                              AS loc_typical

    FROM core.event_editions ed
    JOIN core.event_catalog c
      ON c.event_id = ed.event_id
    LEFT JOIN core.locations l
      ON l.location_id = ed.location_id
    LEFT JOIN core.edition_calendar_dates cal
      ON cal.event_id = ed.event_id
     AND cal.event_year = ed.event_year
     AND cal.event_month = ed.event_month

    WHERE ed.result_rows > 0
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
      AND COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
          ) < CURRENT_DATE
),

with_location AS (
    SELECT
        event_id,
        edition_id,
        location_id,
        event_name,
        city,
        state,
        country,
        start_date,
        end_date,
        sort_end_date,
        event_month,
        event_year,
        result_rows,

        COALESCE(
            NULLIF(
                btrim(concat_ws(', ', city, state, country)),
                ''
            ),
            CASE
                WHEN loc_standardized IS NOT NULL
                 AND country IS NOT NULL
                 AND loc_standardized NOT ILIKE ('%' || country || '%')
                THEN btrim(loc_standardized || ', ' || country)
                ELSE loc_standardized
            END,
            loc_registry,
            loc_raw,
            loc_typical
        ) AS event_location

    FROM completed
)

SELECT
    row_number() OVER (
        ORDER BY sort_end_date ASC NULLS LAST, event_name
    )::int AS event_seq,

    event_name,
    event_location,
    country,
    state,
    city,
    start_date,
    end_date,
    event_month,
    event_year,

    event_id,
    edition_id,
    location_id,

    sort_end_date,
    result_rows

FROM with_location
WITH NO DATA;

COMMENT ON MATERIALIZED VIEW export.completed_event_editions IS
    'Completed WSDC editions (results-backed, past). event_seq=1 is oldest; '
    'start_date/end_date NULL when only month is known; refresh after load.';

CREATE UNIQUE INDEX completed_event_editions_edition_uidx
    ON export.completed_event_editions (edition_id);

CREATE INDEX completed_event_editions_event_seq_idx
    ON export.completed_event_editions (event_seq);

CREATE INDEX completed_event_editions_sort_end_idx
    ON export.completed_event_editions (sort_end_date DESC);

CREATE INDEX completed_event_editions_event_id_idx
    ON export.completed_event_editions (event_id);

CREATE INDEX completed_event_editions_location_id_idx
    ON export.completed_event_editions (location_id);

CREATE OR REPLACE FUNCTION export.refresh_completed_event_editions()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'export'
          AND matviewname = 'completed_event_editions'
          AND ispopulated
    ) THEN
        REFRESH MATERIALIZED VIEW export.completed_event_editions;
    ELSE
        REFRESH MATERIALIZED VIEW CONCURRENTLY export.completed_event_editions;
    END IF;
END;
$$;

COMMENT ON FUNCTION export.refresh_completed_event_editions() IS
    'Rebuild export.completed_event_editions (CONCURRENTLY when already populated).';

-- Initial populate (safe on first deploy).
REFRESH MATERIALIZED VIEW export.completed_event_editions;
