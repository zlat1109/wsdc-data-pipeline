-- Schemas for the WSDC data pipeline.
-- staging: raw per-run loads (truncated before each load)
-- core:    normalized current state
-- history: full change history (SCD2) + run journal

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS history;
