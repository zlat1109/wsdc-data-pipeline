"""Parse-ready decision logic for check-updates (partial-readiness gate)."""

from __future__ import annotations

from typing import Any


def compute_live_ready_pending(
    pending: list[str],
    matched: dict[str, str],
    already_in_db: list[str],
) -> list[str]:
    """Pending events visible in live WSDC data but not yet loaded in Supabase."""
    already = set(already_in_db)
    return [event for event in pending if event in matched and event not in already]


def registry_cooldown_blocks(
    *,
    cooldown_active: bool,
    ready: bool,
    ready_reason: str | None,
    gate_status: str | None,
) -> bool:
    """True when weekly cooldown actually prevents an auto-parse (registry-only path)."""
    if not cooldown_active:
        return False
    if ready_reason == "cooldown":
        return True
    return gate_status == "all_loaded" and not ready


def block_ready_if_parse_in_flight(
    ready: bool,
    reason: str,
    *,
    parse_in_flight: bool,
) -> tuple[bool, str]:
    """Suppress duplicate triggers while a pipeline run is active."""
    if ready and parse_in_flight:
        return False, "parse_in_flight"
    return ready, reason


def evaluate_parse_ready(
    *,
    ids_changed: bool,
    skip_event_gate: bool,
    cooldown_active: bool,
    ignore_cooldown: bool,
    gate_status: str,
    coverage: Any,
    pending: list[str] | None = None,
    already_in_db: list[str] | None = None,
) -> tuple[bool, str, list[str]]:
    """Return (ready, reason, trigger_events).

    Partial-readiness gate: trigger full-parse when any expected weekend event
    appears in live data and is not yet in Supabase. Full parse scope unchanged.
    """
    pending = list(pending or [])
    already_in_db = list(already_in_db or [])
    trigger_events: list[str] = []

    if not ids_changed:
        return False, "no_new_ids", trigger_events

    if skip_event_gate:
        if cooldown_active and not ignore_cooldown:
            return False, "cooldown", trigger_events
        return True, "skip_event_gate", trigger_events

    if gate_status == "no_concluded_events":
        return False, "no_concluded_events", trigger_events

    if gate_status == "all_loaded":
        if cooldown_active and not ignore_cooldown:
            return False, "cooldown", trigger_events
        return True, "all_loaded", trigger_events

    if gate_status != "pending" or coverage is None:
        return False, "waiting_events", trigger_events

    matched = getattr(coverage, "matched", None) or {}
    trigger_events = compute_live_ready_pending(pending, matched, already_in_db)
    if trigger_events:
        return True, "partial_events_ready", trigger_events

    return False, "waiting_events", trigger_events
