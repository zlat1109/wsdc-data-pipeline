"""Backward-compatible re-exports. Prefer transform.knowledge."""

from transform.knowledge import (
    KNOWN_EVENT_METADATA,
    LOCATION_ID_CORRECTIONS,
    LocationPatch,
    apply_event_location_patches,
    event_location_patches,
)

__all__ = [
    'KNOWN_EVENT_METADATA',
    'LOCATION_ID_CORRECTIONS',
    'LocationPatch',
    'apply_event_location_patches',
    'event_location_patches',
]
