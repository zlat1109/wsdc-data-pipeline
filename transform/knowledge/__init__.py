"""Single source of truth for WSDC event/location knowledge."""

from transform.knowledge.apply import (
    apply_event_corrections,
    apply_event_location_patches,
    backfill_empty_result_event_locations,
    event_location_patches,
    force_events_wsdc_locations_from_event_name_overrides,
    force_result_locations_from_event_name_overrides,
)
from transform.knowledge.events import (
    EVENT_LOCATION_EXACT_CORRECTIONS,
    EVENT_LOCATION_SUBSTRING_CORRECTIONS,
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    KNOWN_EVENT_METADATA,
)
from transform.knowledge.event_aliases import (
    EVENT_NAME_VARIANT_TO_CATALOG,
    EVENT_NAME_YEAR_SPLITS,
    MERGE_EVENT_ID_MAP,
    RESULT_TO_CATALOG_EVENT_NAME,
    apply_event_name_year_splits,
    build_event_name_normalization,
)
from transform.knowledge.merge_map import apply_merge_event_id_map
from transform.knowledge.locations import (
    CITY_STATE_COUNTRIES,
    LOCATION_ID_CORRECTIONS,
    LOCATION_ID_MERGE_MAP,
    LOCATION_INFO_CITY_CORRECTIONS,
    LOCATION_STRING_ALIASES,
    SINGAPORE_CANONICAL_LOCATION_ID,
    LocationPatch,
)

__all__ = [
    'EVENT_LOCATION_EXACT_CORRECTIONS',
    'EVENT_LOCATION_SUBSTRING_CORRECTIONS',
    'EVENT_NAME_LOCATION_OVERRIDES',
    'EVENT_NAME_NORMALIZATION',
    'EVENT_NAME_VARIANT_TO_CATALOG',
    'EVENT_NAME_YEAR_SPLITS',
    'KNOWN_EVENT_METADATA',
    'CITY_STATE_COUNTRIES',
    'LOCATION_ID_CORRECTIONS',
    'LOCATION_ID_MERGE_MAP',
    'LOCATION_INFO_CITY_CORRECTIONS',
    'LOCATION_STRING_ALIASES',
    'SINGAPORE_CANONICAL_LOCATION_ID',
    'MERGE_EVENT_ID_MAP',
    'LocationPatch',
    'RESULT_TO_CATALOG_EVENT_NAME',
    'apply_event_corrections',
    'apply_event_location_patches',
    'apply_event_name_year_splits',
    'apply_merge_event_id_map',
    'backfill_empty_result_event_locations',
    'build_event_name_normalization',
    'event_location_patches',
    'force_events_wsdc_locations_from_event_name_overrides',
    'force_result_locations_from_event_name_overrides',
]
