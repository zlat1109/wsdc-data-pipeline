"""Parse-ready decision logic for check-updates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from probe_schedule import is_friday_final_probe


def should_friday_final_parse(
    *,
    now: datetime,
    ids_changed: bool,
    coverage: Any,
    gate_status: str,
) -> bool:
    """Friday evening fallback: parse when some (not all) weekend events are live."""
    if gate_status != "pending":
        return False
    if not is_friday_final_probe(now):
        return False
    if not ids_changed:
        return False
    if coverage is None or coverage.ready:
        return False
    if not coverage.matched:
        return False
    return bool(coverage.missing)


def evaluate_parse_ready(
    *,
    ids_changed: bool,
    skip_event_gate: bool,
    cooldown_active: bool,
    ignore_cooldown: bool,
    gate_status: str,
    coverage: Any,
    now: datetime,
) -> tuple[bool, bool, str]:
    """Return (ready, friday_final_bypass, reason)."""
    if not ids_changed:
        return False, False, "no_new_ids"

    if skip_event_gate:
        if cooldown_active and not ignore_cooldown:
            return False, False, "cooldown"
        return True, False, "skip_event_gate"

    if gate_status == "no_concluded_events":
        return False, False, "no_concluded_events"

    if gate_status == "all_loaded":
        if cooldown_active and not ignore_cooldown:
            return False, False, "cooldown"
        return True, False, "all_loaded"

    assert coverage is not None
    if coverage.ready:
        if cooldown_active and not ignore_cooldown:
            return False, False, "cooldown"
        return True, False, "coverage_complete"

    if should_friday_final_parse(
        now=now,
        ids_changed=ids_changed,
        coverage=coverage,
        gate_status=gate_status,
    ):
        return True, True, "friday_final_partial"

    if cooldown_active and not ignore_cooldown:
        return False, False, "cooldown"
    return False, False, "waiting_events"
