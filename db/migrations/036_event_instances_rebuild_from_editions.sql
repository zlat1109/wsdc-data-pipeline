-- Rebuild policy for deprecated core.event_instances:
-- promote_core truncates the table; rebuild_event_catalog repopulates it from
-- core.event_editions (location_id + location_raw + dates). Direct consumers
-- should use event_editions; export.events_wsdc already does.

COMMENT ON TABLE core.event_instances IS
  'DEPRECATED: rebuilt from core.event_editions after each catalog rebuild. '
  'Prefer event_editions. Do not treat location_id/location_raw here as '
  'authoritative for new features. Candidate for DROP after one release cycle.';
