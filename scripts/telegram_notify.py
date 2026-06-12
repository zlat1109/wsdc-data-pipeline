#!/usr/bin/env python3
"""Send WSDC pipeline notifications to Telegram."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", flush=True)
        return False

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    print("Telegram message sent", flush=True)
    return True


def format_probe_message(report: dict) -> str:
    ready = bool(report.get("ready"))
    status = "✅ <b>Готов к обновлению</b>" if ready else "⏸ <b>Обновления пока нет</b>"
    lines = [
        f"{report.get('checked_at', '')}",
        "#WSDC_Pipeline_Check",
        "",
        f"🔍 <b>Check updates</b>",
        status,
        "",
        f"Watermark: <code>{_esc(report.get('watermark'))}</code>",
        f"Live max ID: <code>{_esc(report.get('live_max_id'))}</code>",
        f"Новых ID (approx): <code>{_esc(report.get('approx_new_ids'))}</code>",
    ]

    if report.get("weekend_snapshot"):
        lines.append(
            f"Snapshot: <code>{_esc(report['weekend_snapshot'])}</code> "
            f"({_esc(report.get('weekend_start', '?'))} … {_esc(report.get('weekend_end', '?'))})"
        )

    if report.get("already_in_db_events"):
        lines.extend(["", "<b>Уже в базе</b> (пропущены):"])
        for name in report["already_in_db_events"]:
            lines.append(f"• {_esc(name)}")

    if report.get("no_pending"):
        lines.extend(["", "⚠️ Нет pending upcoming events — проверь sync snapshot из weekly bot"])

    pending = report.get("pending_events") or []
    if pending:
        lines.extend(["", "<b>Ждём результаты (pending)</b>:"])
        for name in pending:
            lines.append(f"• {_esc(name)}")

    matched = report.get("matched_events") or {}
    if matched:
        lines.extend(["", "<b>Найдено в live (новые танцоры)</b>:"])
        for expected, live in matched.items():
            lines.append(f"• {_esc(expected)} → {_esc(live)}")

    missing = report.get("missing_events") or []
    if missing:
        lines.extend(["", "<b>Ещё не найдено в live</b>:"])
        for name in missing:
            lines.append(f"• {_esc(name)}")

    sample = report.get("new_dancers_sample") or []
    if sample:
        lines.extend(["", "<b>Новые танцоры (sample)</b>:"])
        for dancer in sample[:8]:
            label = dancer.get("name") or dancer.get("wscid")
            dancer_id = dancer.get("wscid", "?")
            lines.append(f"• {_esc(label)} (<code>{_esc(dancer_id)}</code>)")

    if ready:
        lines.extend(["", "▶️ Запускается <b>full-parse</b> pipeline"])
    else:
        lines.append("")
        lines.append("Следующая проверка по расписанию check-updates.")

    return "\n".join(lines)


def format_pipeline_message(stats: dict) -> str:
    lines = [
        stats.get("finished_at", "")[:10],
        "#WSDC_Pipeline_Complete",
        "",
        "✅ <b>Данные WSDC обновлены</b>",
        "",
        f"Load run_id: <code>{_esc(stats.get('run_id'))}</code>",
        f"Dancers (max ID): <code>{_esc(stats.get('max_dancer_id'))}</code>",
    ]

    if stats.get("prev_watermark") is not None:
        delta = (stats.get("max_dancer_id") or 0) - (stats.get("prev_watermark") or 0)
        lines.append(
            f"Было watermark: <code>{_esc(stats['prev_watermark'])}</code> "
            f"(+<code>{_esc(delta)}</code>)"
        )

    if stats.get("rows_results") is not None:
        lines.append(f"Results rows loaded: <code>{_esc(stats['rows_results'])}</code>")
    if stats.get("rows_points") is not None:
        lines.append(f"Points rows loaded: <code>{_esc(stats['rows_points'])}</code>")

    pending = stats.get("pending_events") or []
    if pending:
        lines.extend(["", "<b>События цикла</b>:"])
        for name in pending:
            lines.append(f"• {_esc(name)}")

    if stats.get("csv_committed"):
        lines.extend(["", "📁 CSV экспорт закоммичен в <code>data/*.csv</code>"])
    if stats.get("repo"):
        lines.append(f"Repo: {_esc(stats['repo'])}")

    return "\n".join(lines)


def cmd_probe(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    send_telegram(format_probe_message(report))


def cmd_pipeline_complete() -> None:
    from connection import connect  # noqa: WPS433

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(dancer_id), 0) FROM core.dancers")
        max_dancer_id = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT run_id, rows_results, rows_points, max_dancer_id_watermark,
                   probe_details, finished_at
            FROM history.parse_runs
            WHERE status = 'success' AND finished_at IS NOT NULL
            ORDER BY run_id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            send_telegram(
                "✅ <b>Pipeline finished</b>\n\nLoad run не найден в history.parse_runs."
            )
            return

        run_id, rows_results, rows_points, wm, probe_details, finished_at = row
        pending: list[str] = []
        if isinstance(probe_details, dict):
            pending = probe_details.get("pending_events") or []

        cur.execute(
            """
            SELECT max_dancer_id_watermark
            FROM history.parse_runs
            WHERE status = 'success' AND run_id < %s
            ORDER BY run_id DESC
            LIMIT 1
            """,
            (run_id,),
        )
        prev = cur.fetchone()
        prev_watermark = int(prev[0]) if prev and prev[0] is not None else wm

    stats = {
        "run_id": run_id,
        "max_dancer_id": max_dancer_id,
        "prev_watermark": prev_watermark,
        "rows_results": rows_results,
        "rows_points": rows_points,
        "pending_events": pending,
        "finished_at": finished_at.isoformat() if finished_at else "",
        "csv_committed": os.getenv("PIPELINE_CSV_COMMITTED", "false").lower() == "true",
        "repo": os.getenv("GITHUB_REPOSITORY", ""),
    }
    send_telegram(format_pipeline_message(stats))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Notify after check-updates")
    probe.add_argument("report", type=Path, help="JSON from check_updates --json-report")

    sub.add_parser("pipeline-complete", help="Notify after full-parse load+export")

    args = parser.parse_args()
    if args.command == "probe":
        cmd_probe(args.report)
    elif args.command == "pipeline-complete":
        cmd_pipeline_complete()


if __name__ == "__main__":
    main()
