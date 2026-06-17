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
    'KNOWN_EVENT_METADATA',
    'LOCATION_ID_CORRECTIONS',
    'LOCATION_INFO_CITY_CORRECTIONS',
    'LocationPatch',
    'apply_event_corrections',
    'apply_event_location_patches',
    'event_location_patches',
]
