-- Extend parse_runs for new-ID probe workflow (watermark-based detection).

ALTER TABLE history.parse_runs
    ADD COLUMN IF NOT EXISTS max_dancer_id_watermark int,
    ADD COLUMN IF NOT EXISTS new_dancer_ids jsonb,
    ADD COLUMN IF NOT EXISTS probe_details jsonb;
