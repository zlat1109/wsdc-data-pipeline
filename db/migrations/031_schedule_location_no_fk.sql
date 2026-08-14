-- Schedule tables must survive promote_core's
--   TRUNCATE core.locations ... CASCADE
-- Migration 030 attached location_id FKs; full parse then wiped
-- core.events_list_current + core.scheduled_events (empty scheduled_events.csv,
-- runs 31421430091 / 31525495964).
-- Soft integrity: quality checks events_list_current_empty /
-- schedule_orphan_location_id.
-- ON DELETE SET NULL does not help: TRUNCATE CASCADE still truncates
-- referencing tables (PostgreSQL sql-truncate).
-- @docs-summary: Drop schedule location_id FKs so promote CASCADE cannot wipe the calendar

ALTER TABLE core.events_list_current
    DROP CONSTRAINT IF EXISTS events_list_current_location_id_fkey;

ALTER TABLE core.scheduled_events
    DROP CONSTRAINT IF EXISTS scheduled_events_location_id_fkey;

COMMENT ON COLUMN core.events_list_current.location_id IS
    'Resolved place for nearest upcoming edition (copied from scheduled_events). '
    'No FK to core.locations — promote_core TRUNCATE ... CASCADE must not wipe the schedule.';

COMMENT ON COLUMN core.scheduled_events.location_id IS
    'Resolved place for this edition (trial/list geo). Null until ensure_location runs. '
    'No FK to core.locations — promote_core TRUNCATE ... CASCADE must not wipe the archive.';
