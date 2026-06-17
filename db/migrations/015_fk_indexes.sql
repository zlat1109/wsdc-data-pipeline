-- Index unindexed foreign-key columns (schema-foreign-key-indexes).
-- Improves JOINs, CASCADE, and filters on run_id / event_id.

CREATE INDEX IF NOT EXISTS event_instances_event_id_idx
    ON core.event_instances (event_id);

CREATE INDEX IF NOT EXISTS event_instances_location_id_idx
    ON core.event_instances (location_id);

CREATE INDEX IF NOT EXISTS event_aliases_event_id_idx
    ON core.event_aliases (event_id);

CREATE INDEX IF NOT EXISTS dancer_points_history_run_id_idx
    ON history.dancer_points_history (run_id);

CREATE INDEX IF NOT EXISTS dancer_roles_history_run_id_idx
    ON history.dancer_roles_history (run_id);

CREATE INDEX IF NOT EXISTS events_list_current_last_run_id_idx
    ON core.events_list_current (last_run_id);

CREATE INDEX IF NOT EXISTS scheduled_events_last_run_id_idx
    ON core.scheduled_events (last_run_id);
