"""Tests for pipeline failure Telegram formatting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from telegram_notify import format_pipeline_failed_message


def test_format_pipeline_failed_message():
    text = format_pipeline_failed_message(
        {
            "workflow": "Full WSDC parse pipeline",
            "job": "pipeline",
            "run_url": "https://github.com/zlat1109/wsdc-data-pipeline/actions/runs/1",
        }
    )
    assert "Pipeline failed" in text
    assert "WSDC_Pipeline_Failed" in text
    assert "Full WSDC parse pipeline" in text
