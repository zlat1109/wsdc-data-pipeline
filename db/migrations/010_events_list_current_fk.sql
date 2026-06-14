-- canonical_event_id comes from schedule mapping + supplement catalog;
-- not every mapped id exists in core.events until points promote runs.

ALTER TABLE core.events_list_current
    DROP CONSTRAINT IF EXISTS events_list_current_canonical_event_id_fkey;

COMMENT ON COLUMN core.events_list_current.canonical_event_id IS
    'Mapped WSDC event_id when known; no FK — may reference catalog-only ids before points load.';
