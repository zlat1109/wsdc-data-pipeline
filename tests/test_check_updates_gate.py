"""Tests for check-updates parse-ready decisions (partial-readiness gate)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_updates_gate import (
    block_ready_if_parse_in_flight,
    compute_live_ready_pending,
    evaluate_parse_ready,
    registry_cooldown_blocks,
)
from dataclasses import dataclass, field


@dataclass
class _Coverage:
    expected: list[str]
    matched: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.expected) and not self.missing


def _coverage(*, matched: dict[str, str], missing: list[str]) -> _Coverage:
    return _Coverage(
        expected=list(matched) + list(missing),
        matched=matched,
        missing=missing,
    )


def test_no_parse_when_zero_new_ids():
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=False,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=None,
        pending=["Big Apple Dance Festival", "Mediterranean Open WCS"],
        already_in_db=["SwingLab Berlin"],
    )
    assert ready is False
    assert reason == "no_new_ids"
    assert trigger == []


def test_compute_live_ready_pending_excludes_already_in_db():
    result = compute_live_ready_pending(
        pending=["A", "B", "C"],
        matched={"A": "A live", "B": "B live"},
        already_in_db=["A"],
    )
    assert result == ["B"]


def test_partial_ready_when_one_of_many_events_matched():
    coverage = _coverage(
        matched={"Big Apple": "Big Apple Dance Festival"},
        missing=["Neverland Swing", "Carolina", "MY Swing", "Americano"],
    )
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        pending=coverage.expected,
        already_in_db=[],
    )
    assert ready is True
    assert reason == "partial_events_ready"
    assert trigger == ["Big Apple"]


def test_no_parse_when_zero_events_matched():
    coverage = _coverage(matched={}, missing=["Neverland Swing"])
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        pending=coverage.expected,
        already_in_db=[],
    )
    assert ready is False
    assert reason == "waiting_events"
    assert trigger == []


def test_no_parse_when_matched_events_already_in_db():
    coverage = _coverage(
        matched={"Big Apple": "Big Apple Dance Festival"},
        missing=["Neverland Swing"],
    )
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        pending=coverage.expected,
        already_in_db=["Big Apple"],
    )
    assert ready is False
    assert reason == "waiting_events"
    assert trigger == []


def test_no_parse_on_quiet_weekend_without_concluded_events():
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="no_concluded_events",
        coverage=None,
    )
    assert ready is False
    assert reason == "no_concluded_events"
    assert trigger == []


def test_parse_when_all_weekend_events_already_loaded():
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="all_loaded",
        coverage=None,
    )
    assert ready is True
    assert reason == "all_loaded"
    assert trigger == []


def test_partial_ready_ignores_weekly_cooldown():
    coverage = _coverage(
        matched={"Baltic Swing": "Baltic Swing"},
        missing=["Neverland Swing"],
    )
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=True,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        pending=coverage.expected,
        already_in_db=[],
    )
    assert ready is True
    assert reason == "partial_events_ready"
    assert trigger == ["Baltic Swing"]


def test_all_loaded_respects_weekly_cooldown():
    ready, reason, _ = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=True,
        ignore_cooldown=False,
        gate_status="all_loaded",
        coverage=None,
    )
    assert ready is False
    assert reason == "cooldown"


def test_pending_without_coverage_returns_waiting():
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=None,
        pending=["Big Apple"],
        already_in_db=[],
    )
    assert ready is False
    assert reason == "waiting_events"
    assert trigger == []


def test_all_events_matched_triggers_partial_ready():
    coverage = _coverage(
        matched={
            "A": "A",
            "B": "B",
        },
        missing=[],
    )
    ready, reason, trigger = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        pending=coverage.expected,
        already_in_db=[],
    )
    assert ready is True
    assert reason == "partial_events_ready"
    assert set(trigger) == {"A", "B"}


def test_block_ready_if_parse_in_flight():
    ready, reason = block_ready_if_parse_in_flight(
        True,
        "partial_events_ready",
        parse_in_flight=True,
    )
    assert ready is False
    assert reason == "parse_in_flight"


def test_block_ready_passes_through_when_not_in_flight():
    ready, reason = block_ready_if_parse_in_flight(
        True,
        "partial_events_ready",
        parse_in_flight=False,
    )
    assert ready is True
    assert reason == "partial_events_ready"


def test_registry_cooldown_blocks_only_registry_path():
    assert registry_cooldown_blocks(
        cooldown_active=True,
        ready=True,
        ready_reason="partial_events_ready",
        gate_status="pending",
    ) is False
    assert registry_cooldown_blocks(
        cooldown_active=True,
        ready=False,
        ready_reason="cooldown",
        gate_status="all_loaded",
    ) is True
    assert registry_cooldown_blocks(
        cooldown_active=True,
        ready=False,
        ready_reason="waiting_events",
        gate_status="pending",
    ) is False
