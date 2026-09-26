-- Harden function search_path (Supabase advisor) and enable RLS defense-in-depth
-- on warehouse tables. service_role bypasses RLS; anon/authenticated already lack
-- schema USAGE on core/staging/history.

ALTER FUNCTION core.dancer_name_at(integer, date)
  SET search_path = core, history, pg_temp;

ALTER FUNCTION core.dancer_roles_division_sig(
  text, text, text, text, text, text, text, text, text
) SET search_path = core, pg_temp;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'core.levels', 'core.dancers', 'core.locations', 'core.events', 'core.event_aliases',
    'core.event_instances', 'core.results', 'core.dancer_points', 'core.dancer_roles',
    'core.scheduled_events', 'core.events_list_current', 'core.event_catalog',
    'core.event_editions', 'core.dancer_aliases', 'core.edition_calendar_dates',
    'core.rules_editions', 'core.tier_definitions', 'core.tier_points',
    'core.edition_division_tiers', 'core.edition_location_baseline',
    'staging.dancers_points_info', 'staging.dancer_role_info', 'staging.dancers_results_info',
    'staging.location_info', 'staging.events_wsdc', 'staging.changed_dancers_points_info',
    'staging.changed_dancer_role_info',
    'history.parse_runs', 'history.dancer_points_history', 'history.dancer_roles_history',
    'history.events_list_runs', 'history.events_list_changes', 'history.dancer_names_history'
  ]
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

COMMENT ON TABLE core.event_instances IS
  'DEPRECATED legacy edition table; prefer core.event_editions. location_id is unused (always null). Scheduled for removal after consumer audit.';
