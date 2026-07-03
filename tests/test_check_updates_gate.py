"""Tests for check-updates parse-ready decisions."""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_updates_gate import evaluate_parse_ready, should_friday_final_parse
from dataclasses import dataclass, field


@dataclass
class _Coverage:
    expected: list[str]
    matched: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.expected) and not self.missing

MADRID = ZoneInfo("Europe/Madrid")
FRIDAY_EVENING = datetime(2026, 7, 3, 20, 0, tzinfo=MADRID)
FRIDAY_MORNING = datetime(2026, 7, 3, 8, 0, tzinfo=MADRID)


def _coverage(*, matched: dict[str, str], missing: list[str]) -> _Coverage:
    return _Coverage(
        expected=list(matched) + list(missing),
        matched=matched,
        missing=missing,
    )


def test_friday_partial_when_some_events_matched():
    coverage = _coverage(
        matched={"Baltic Swing": "Baltic Swing"},
        missing=["Neverland Swing"],
    )
    ready, bypass, reason = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        now=FRIDAY_EVENING,
    )
    assert ready is True
    assert bypass is True
    assert reason == "friday_final_partial"


def test_friday_no_parse_when_zero_events_matched():
    coverage = _coverage(matched={}, missing=["Neverland Swing"])
    ready, bypass, reason = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        now=FRIDAY_EVENING,
    )
    assert ready is False
    assert bypass is False
    assert reason == "waiting_events"


def test_friday_no_parse_on_morning_slot():
    coverage = _coverage(
        matched={"Baltic Swing": "Baltic Swing"},
        missing=["Neverland Swing"],
    )
    assert not should_friday_final_parse(
        now=FRIDAY_MORNING,
        ids_changed=True,
        coverage=coverage,
        gate_status="pending",
    )


def test_no_parse_on_quiet_weekend_without_concluded_events():
    ready, bypass, reason = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="no_concluded_events",
        coverage=None,
        now=FRIDAY_EVENING,
    )
    assert ready is False
    assert bypass is False
    assert reason == "no_concluded_events"


def test_parse_when_all_weekend_events_already_loaded():
    ready, bypass, reason = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=False,
        ignore_cooldown=False,
        gate_status="all_loaded",
        coverage=None,
        now=FRIDAY_EVENING,
    )
    assert ready is True
    assert reason == "all_loaded"


def test_friday_bypass_ignores_weekly_cooldown():
    coverage = _coverage(
        matched={"Baltic Swing": "Baltic Swing"},
        missing=["Neverland Swing"],
    )
    ready, bypass, reason = evaluate_parse_ready(
        ids_changed=True,
        skip_event_gate=False,
        cooldown_active=True,
        ignore_cooldown=False,
        gate_status="pending",
        coverage=coverage,
        now=FRIDAY_EVENING,
    )
    assert ready is True
    assert bypass is True
