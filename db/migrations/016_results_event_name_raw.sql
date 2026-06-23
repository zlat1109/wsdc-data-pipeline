-- Preserve raw API/staging event name on results (export view must not erase it).

ALTER TABLE core.results
    ADD COLUMN IF NOT EXISTS event_name_raw text;

CREATE INDEX IF NOT EXISTS results_event_name_raw_idx
    ON core.results (event_name_raw)
    WHERE event_name_raw IS NOT NULL;
