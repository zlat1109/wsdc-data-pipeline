"""Tests for Telegram notification formatting."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from telegram_notify import format_probe_message, format_pipeline_message


def test_format_probe_unchanged():
    report = {
        "checked_at": "2026-06-12",
        "ready": False,
        "watermark": 28367,
        "live_max_id": 28370,
        "approx_new_ids": 3,
        "pending_events": ["Baltic Swing"],
        "missing_events": ["Baltic Swing"],
        "matched_events": {},
        "already_in_db_events": ["Jack & Jill O'Rama"],
        "new_dancers_sample": [{"name": "Test Dancer", "wscid": 28368}],
    }
    text = format_probe_message(report)
    assert "Обновления пока нет" in text
    assert "Baltic Swing" in text
    assert "WSDC_Pipeline_Check" in text


def test_format_probe_ready():
    report = {
        "checked_at": "2026-06-12",
        "ready": True,
        "watermark": 28367,
        "live_max_id": 28400,
        "approx_new_ids": 33,
        "pending_events": ["Baltic Swing"],
        "missing_events": [],
        "matched_events": {"Baltic Swing": "Baltic Swing"},
    }
    text = format_probe_message(report)
    assert "Готов к обновлению" in text
    assert "full-parse" in text


def test_format_pipeline_complete():
    text = format_pipeline_message(
        {
            "run_id": 17,
            "max_dancer_id": 28400,
            "prev_watermark": 28367,
            "rows_results": 193800,
            "pending_events": ["Baltic Swing"],
            "finished_at": "2026-06-15T10:00:00+00:00",
            "csv_committed": True,
        }
    )
    assert "Данные WSDC обновлены" in text
    assert "28400" in text
    assert "WSDC_Pipeline_Complete" in text
