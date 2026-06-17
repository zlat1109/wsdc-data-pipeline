-- Index FK columns used in catalog rebuild and location joins (schema-foreign-key-indexes).
CREATE INDEX IF NOT EXISTS results_location_idx
    ON core.results (location_id);

CREATE INDEX IF NOT EXISTS event_editions_location_idx
    ON core.event_editions (location_id);
