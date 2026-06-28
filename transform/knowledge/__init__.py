"""Single source of truth for WSDC event/location knowledge."""

from transform.knowledge.apply import (
    apply_event_corrections,
    apply_event_location_patches,
    event_location_patches,
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
    MERGE_EVENT_ID_MAP,
    RESULT_TO_CATALOG_EVENT_NAME,
    build_event_name_normalization,
)
from transform.knowledge.merge_map import apply_merge_event_id_map
from transform.knowledge.locations import (
    LOCATION_ID_CORRECTIONS,
    LOCATION_INFO_CITY_CORRECTIONS,
    LocationPatch,
)

__all__ = [
    'EVENT_LOCATION_EXACT_CORRECTIONS',
    'EVENT_LOCATION_SUBSTRING_CORRECTIONS',
    'EVENT_NAME_LOCATION_OVERRIDES',
    'EVENT_NAME_NORMALIZATION',
    'EVENT_NAME_VARIANT_TO_CATALOG',
    'KNOWN_EVENT_METADATA',
    'LOCATION_ID_CORRECTIONS',
    'LOCATION_INFO_CITY_CORRECTIONS',
    'MERGE_EVENT_ID_MAP',
    'LocationPatch',
    'RESULT_TO_CATALOG_EVENT_NAME',
    'apply_event_corrections',
    'apply_event_location_patches',
    'apply_merge_event_id_map',
    'build_event_name_normalization',
    'event_location_patches',
]
