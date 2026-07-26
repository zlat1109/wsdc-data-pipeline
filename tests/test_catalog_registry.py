"""Tests for phantom registry id → canonical event map."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))

from catalog_registry import PHANTOM_ALIAS_TO_CANONICAL


def test_phantom_map_targets_are_not_phantoms():
    sources = set(PHANTOM_ALIAS_TO_CANONICAL)
    targets = set(PHANTOM_ALIAS_TO_CANONICAL.values())
    assert sources.isdisjoint(targets)


def test_phantom_map_uk_and_madjam_and_kazan_targets():
    # UK title ghosts must NOT alias to USA Grand Nationals (22).
    assert PHANTOM_ALIAS_TO_CANONICAL[486] == 154
    assert PHANTOM_ALIAS_TO_CANONICAL[487] == 154
    assert PHANTOM_ALIAS_TO_CANONICAL[488] == 22
    # MADjam / Midnight Madness ghosts (ids reused by WSDC).
    assert PHANTOM_ALIAS_TO_CANONICAL[443] == 92
    assert PHANTOM_ALIAS_TO_CANONICAL[444] == 288
    # Kazan ghost must NOT alias to Swing & Snow (215).
    assert PHANTOM_ALIAS_TO_CANONICAL[467] == 283


def test_merge_event_id_map_does_not_send_443_to_lonestar():
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    assert 443 not in MERGE_EVENT_ID_MAP
    assert MERGE_EVENT_ID_MAP[442] == 120
