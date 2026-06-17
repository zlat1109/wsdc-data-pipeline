"""Tests for Telegram notification formatting."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from telegram_notify import (
    format_events_list_message,
    format_parse_start_message,
    format_pipeline_message,
    format_probe_message,
)


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
    assert "отдельном сообщении" in text


def test_format_probe_cooldown():
    report = {
        "checked_at": "2026-06-17",
        "ready": False,
        "cooldown_active": True,
        "cooldown_until": "2026-06-22T00:00:00+02:00",
        "last_success_run_id": 123,
        "watermark": 28420,
        "live_max_id": 28435,
        "approx_new_ids": 15,
    }
    text = format_probe_message(report)
    assert "Cooldown" in text
    assert "2026-06-22" in text
    assert "run_id" in text


def test_format_parse_start():
    text = format_parse_start_message(
        {
            "checked_at": "2026-06-15",
            "watermark": 28367,
            "live_max_id": 28420,
            "approx_new_ids": 53,
            "weekend_snapshot": "weekend_2026-06-08_2026-06-21.json",
            "matched_events": {"Baltic Swing": "Baltic Swing"},
            "pending_events": ["Baltic Swing"],
            "new_dancers_sample": [{"name": "Test User", "wscid": 28420}],
        }
    )
    assert "WSDC_Pipeline_Parse_Start" in text
    assert "28420" in text
    assert "Baltic Swing" in text
    assert "28367" in text


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


def test_format_events_list_inactive_and_mapping(tmp_path, monkeypatch):
    import telegram_notify as tn

    events_dir = tmp_path / "data" / "events_list"
    mapping_dir = events_dir / "mapping"
    mapping_dir.mkdir(parents=True)
    (events_dir / "current.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "event_name": "Dance N Play",
                        "start_date": "2026-06-18",
                        "is_active": False,
                        "canceled": True,
                        "on_hiatus": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (mapping_dir / "latest.json").write_text(
        json.dumps({"summary": {"confirmed": 1, "suggested": 0, "review": 0, "new_unmapped": 2}, "suggested": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(tn, "PROJECT_ROOT", tmp_path)

    text = format_events_list_message(
        {
            "scraped_at": "2026-06-16T12:00:00+00:00",
            "summary": {
                "total": 3,
                "active": 2,
                "inactive": 1,
                "added": 0,
                "removed": 0,
                "unchanged": 3,
            },
            "mapping_summary": {"confirmed": 1, "suggested": 0, "review": 0, "new_unmapped": 2},
        }
    )
    assert "inactive" in text
    assert "Dance N Play" in text
    assert "Suggested:" in text
    assert "Лезть не обязательно" in text
