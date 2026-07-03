"""Tests for check-updates probe schedule."""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from probe_schedule import is_friday_final_probe

MADRID = ZoneInfo("Europe/Madrid")
FRIDAY_EVENING = datetime(2026, 7, 3, 20, 0, tzinfo=MADRID)
FRIDAY_MORNING = datetime(2026, 7, 3, 8, 0, tzinfo=MADRID)
THURSDAY_EVENING = datetime(2026, 7, 2, 20, 0, tzinfo=MADRID)


def test_friday_evening_slot_env():
    os.environ["PROBE_SLOT"] = "evening"
    try:
        assert is_friday_final_probe(FRIDAY_MORNING)
    finally:
        os.environ.pop("PROBE_SLOT", None)


def test_friday_morning_slot_env_blocks_bypass():
    os.environ["PROBE_SLOT"] = "morning"
    try:
        assert not is_friday_final_probe(FRIDAY_EVENING)
    finally:
        os.environ.pop("PROBE_SLOT", None)


def test_friday_evening_without_slot_uses_hour():
    os.environ.pop("PROBE_SLOT", None)
    assert is_friday_final_probe(FRIDAY_EVENING)
    assert not is_friday_final_probe(FRIDAY_MORNING)


def test_thursday_evening_never_final():
    os.environ["PROBE_SLOT"] = "evening"
    try:
        assert not is_friday_final_probe(THURSDAY_EVENING)
    finally:
        os.environ.pop("PROBE_SLOT", None)
