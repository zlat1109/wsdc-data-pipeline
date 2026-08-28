-- Replace materialized snapshot with a live view (always fresh on SELECT).
-- @docs-summary: export.completed_event_editions as regular VIEW (was MV 032)

DROP FUNCTION IF EXISTS export.refresh_completed_event_editions();
DROP VIEW IF EXISTS export.completed_event_editions;
DROP MATERIALIZED VIEW IF EXISTS export.completed_event_editions;

CREATE VIEW export.completed_event_editions AS
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

FROM with_location;

COMMENT ON VIEW export.completed_event_editions IS
    'Completed WSDC editions (results-backed, past). event_seq=1 is oldest; '
    'start_date/end_date NULL when only month is known; live view (no refresh).';
