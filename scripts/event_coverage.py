"""Check whether live WSDC data covers all upcoming events from last weekend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from parser.event_name_matcher import find_best_match
from parser.extract_api import extract_event_names
from parser.http_client import WSDCHttpClient


@dataclass
class EventCoverageResult:
    expected: list[str]
    found_live_names: set[str] = field(default_factory=set)
    matched: dict[str, str] = field(default_factory=dict)  # expected -> live name
    missing: list[str] = field(default_factory=list)
    dancers_scanned: int = 0
    threshold: float = 0.75
    already_in_db: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.expected) and not self.missing


def check_event_coverage(
    client: WSDCHttpClient,
    start_id: int,
    end_id: int,
    expected_events: list[str],
    *,
    threshold: float | None = None,
    max_scans: int | None = None,
) -> EventCoverageResult:
    """Scan new dancer IDs (newest first) until all expected events are seen live."""
    threshold = threshold or float(os.getenv("EVENT_COVERAGE_THRESHOLD", "0.75"))
    max_scans = max_scans or int(os.getenv("EVENT_COVERAGE_MAX_SCANS", "500"))

    result = EventCoverageResult(expected=list(expected_events), threshold=threshold)
    if not expected_events:
        return result

    pending = set(expected_events)
    scans = 0

    for dancer_id in range(end_id, start_id - 1, -1):
        if not pending:
            break
        if scans >= max_scans:
            break
        scans += 1

        data = client.fetch_dancer(dancer_id)
        if not data:
            continue

        live_names = extract_event_names(data)
        result.found_live_names.update(live_names)

        for expected in list(pending):
            match, score = find_best_match(expected, sorted(live_names), threshold=threshold)
            if match:
                result.matched[expected] = match
                pending.remove(expected)

    result.dancers_scanned = scans
    result.missing = sorted(pending)
    return result
