-- edition_calendar_dates must survive promote_core's
--   TRUNCATE core.events ... CASCADE
-- A FK to core.events caused CASCADE to wipe planned dates on every full parse.
-- Soft integrity: quality check edition_calendar_orphan_event_ids.
-- @docs-summary: Drop edition_calendar_dates FK so promote CASCADE cannot wipe dates

ALTER TABLE core.edition_calendar_dates
    DROP CONSTRAINT IF EXISTS edition_calendar_dates_event_id_fkey;

COMMENT ON TABLE core.edition_calendar_dates IS
    'Planned edition dates from worldsdc.com/events/calendar/ (and list backfill). '
    'No FK to core.events so promote_core TRUNCATE ... CASCADE cannot wipe this archive. '
    'Copied onto event_editions after each rebuild_event_catalog.';
