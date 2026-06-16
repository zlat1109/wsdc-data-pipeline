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
        lines.append("")
        lines.append("Условия gate выполнены — старт parse в отдельном сообщении.")
    else:
        lines.append("")
        lines.append("Следующая проверка по расписанию check-updates.")

    return "\n".join(lines)


def format_parse_start_message(report: dict) -> str:
    watermark = int(report.get("watermark") or 0)
    live_max = int(report.get("live_max_id") or 0)
    approx_new = int(report.get("approx_new_ids") or max(live_max - watermark, 0))
    parse_total = live_max

    lines = [
        report.get("checked_at", ""),
        "#WSDC_Pipeline_Parse_Start",
        "",
        "🚀 <b>Все условия соблюдены — начинаю полный парсинг</b>",
        "",
        f"Watermark в Supabase: <code>{_esc(watermark)}</code>",
        f"Live max ID на WSDC: <code>{_esc(live_max)}</code>",
        f"Новых registry ID: <code>+{_esc(approx_new)}</code> "
        f"(<code>{_esc(watermark + 1)}</code> … <code>{_esc(live_max)}</code>)",
        "",
        f"Диапазон HTTP parse: <code>1</code> … <code>{_esc(live_max)}</code>",
        f"Танцоров к запросу: <code>~{_esc(parse_total)}</code>",
        "Режим: полная замена role / points / results CSV",
    ]

    if report.get("weekend_snapshot"):
        lines.append(
            f"Snapshot: <code>{_esc(report['weekend_snapshot'])}</code>"
        )

    matched = report.get("matched_events") or {}
    pending = report.get("pending_events") or []
    if matched or pending:
        lines.extend(["", "<b>Ивенты (gate пройден)</b>:"])
        for expected, live in matched.items():
            lines.append(f"✅ {_esc(expected)} → {_esc(live)}")
        for name in pending:
            if name not in matched:
                lines.append(f"• {_esc(name)}")

    sample = report.get("new_dancers_sample") or []
    if sample:
        lines.extend(["", "<b>Новые танцоры (sample)</b>:"])
        for dancer in sample[:8]:
            label = dancer.get("name") or dancer.get("wscid")
            dancer_id = dancer.get("wscid", "?")
            lines.append(f"• {_esc(label)} (<code>{_esc(dancer_id)}</code>)")

    eta_h = max(parse_total * 0.3 / 3600, 0.5)
    lines.extend([
        "",
        f"⏳ Оценка времени: ~{_esc(f'{eta_h:.1f}')} ч (GitHub Actions)",
        "📬 После load + export придёт <b>#WSDC_Pipeline_Complete</b>",
    ])
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

    quality_path = PROJECT_ROOT / "data" / "quality_reports" / "latest.json"
    if quality_path.exists():
        try:
            q = json.loads(quality_path.read_text(encoding="utf-8"))
            qs = q.get("summary") or {}
            applied_n = qs.get("applied_rules_count", 0)
            manual_new = qs.get("manual_review_new_count", qs.get("new_findings", 0))
            manual_total = qs.get("manual_review_count", qs.get("total_findings", 0))
            before_n = qs.get("before_findings_count", 0)

            lines.extend([
                "",
                "<b>Data quality log</b>",
                f"Before: <code>{_esc(before_n)}</code> findings",
                f"Applied rules: <code>{_esc(applied_n)}</code>",
                f"Manual review: <code>{_esc(manual_new)}</code> new / "
                f"<code>{_esc(manual_total)}</code> total",
                f"Log: <code>data/quality_reports/latest.json</code>",
            ])

            applied_rules = (q.get("applied_normalizations") or {}).get("rules") or []
            if applied_rules:
                lines.append("")
                lines.append("<b>Applied (sample)</b>:")
                for rule in applied_rules[:4]:
                    lines.append(
                        f"• {_esc(rule.get('rule_id'))}: "
                        f"{_esc(str(rule.get('from_value', ''))[:40])} → "
                        f"{_esc(str(rule.get('to_value', ''))[:40])} "
                        f"(<code>{_esc(rule.get('rows_affected'))}</code>)"
                    )

            manual_items = (q.get("manual_review_required") or {}).get("findings") or []
            new_items = [f for f in manual_items if f.get("is_new")][:4]
            if new_items:
                lines.append("")
                lines.append("<b>Manual review (new)</b>:")
                for item in new_items:
                    lines.append(
                        f"• [{_esc(item.get('severity'))}] {_esc(item.get('code'))}: "
                        f"{_esc(str(item.get('message', ''))[:70])}"
                    )
        except (json.JSONDecodeError, OSError):
            pass

    if stats.get("repo"):
        lines.append(f"Repo: {_esc(stats['repo'])}")

    return "\n".join(lines)


def cmd_probe(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    send_telegram(format_probe_message(report))


def cmd_parse_start(report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    send_telegram(format_parse_start_message(report))


def cmd_parse_start_live() -> None:
    """Parse-start stats when full-parse is run manually (no probe_report.json)."""
    import requests
    from datetime import date

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from wsdc_id_probe import scan_ids_above_watermark  # noqa: WPS433
    from connection import connect  # noqa: WPS433

    anchor = int(os.getenv("PROBE_ANCHOR_ID", "26410"))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(dancer_id), 0) FROM core.dancers")
        watermark = int(cur.fetchone()[0])

    live_max = scan_ids_above_watermark(requests.Session(), anchor).live_max_id
    report = {
        "checked_at": date.today().isoformat(),
        "ready": True,
        "watermark": watermark,
        "live_max_id": live_max,
        "approx_new_ids": max(live_max - watermark, 0),
        "pending_events": [],
        "matched_events": {},
        "new_dancers_sample": [],
    }
    send_telegram(format_parse_start_message(report))


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

    parse_start = sub.add_parser("parse-start", help="Notify when full parse is triggered")
    parse_start.add_argument("report", type=Path, help="JSON from check_updates --json-report")

    sub.add_parser("parse-start-live", help="Notify parse start using live DB + WSDC scan")
    sub.add_parser("pipeline-complete", help="Notify after full-parse load+export")

    events_list = sub.add_parser("events-list", help="Notify after weekly events list sync")
    events_list.add_argument("report", type=Path, nargs="?", default=None)

    args = parser.parse_args()
    if args.command == "probe":
        cmd_probe(args.report)
    elif args.command == "parse-start":
        cmd_parse_start(args.report)
    elif args.command == "parse-start-live":
        cmd_parse_start_live()
    elif args.command == "pipeline-complete":
        cmd_pipeline_complete()
    elif args.command == "events-list":
        cmd_events_list(args.report)


def format_events_list_message(report: dict) -> str:
    s = report.get("summary") or {}
    inactive = int(s.get("inactive", 0))
    active = int(s.get("active", s.get("total", 0) - inactive))
    lines = [
        report.get("scraped_at", "")[:10],
        "#WSDC_Events_List",
        "",
        "📅 <b>WSDC Events List updated</b>",
        "",
        f"На сайте: <code>{_esc(s.get('total', 0))}</code> "
        f"(active <code>{_esc(active)}</code> · inactive <code>{_esc(inactive)}</code>)",
        f"Добавлено: <code>{_esc(s.get('added', 0))}</code>",
        f"Убрали из списка: <code>{_esc(s.get('removed', 0))}</code>",
        f"Без изменений: <code>{_esc(s.get('unchanged', 0))}</code>",
    ]

    if inactive:
        lines.extend(["", "<b>Inactive</b> (canceled/hiatus — в мэппинг не идут):"])
        current_path = PROJECT_ROOT / "data" / "events_list" / "current.json"
        try:
            doc = json.loads(current_path.read_text(encoding="utf-8"))
            for ev in doc.get("events") or []:
                if ev.get("is_active", True):
                    continue
                tag = []
                if ev.get("canceled"):
                    tag.append("canceled")
                if ev.get("on_hiatus"):
                    tag.append("hiatus")
                suffix = f" ({', '.join(tag)})" if tag else ""
                lines.append(
                    f"• {_esc(ev.get('event_name'))} "
                    f"(<code>{_esc(ev.get('start_date'))}</code>){suffix}"
                )
        except (json.JSONDecodeError, OSError):
            lines.append(f"• <code>{_esc(inactive)}</code> строк — см. current.json")

    added = report.get("added") or []
    if added:
        lines.extend(["", "<b>Новые в расписании</b>:"])
        for ev in added[:10]:
            loc = (ev.get("location_raw") or "")[:45]
            lines.append(
                f"• {_esc(ev.get('event_name'))} "
                f"(<code>{_esc(ev.get('start_date'))}</code>)"
                + (f" — {_esc(loc)}" if loc else "")
            )
        if len(added) > 10:
            lines.append(f"… +{len(added) - 10} ещё")

    removed = report.get("removed") or []
    if removed:
        lines.extend(["", "<b>Пропали из расписания</b>:"])
        for ev in removed[:10]:
            lines.append(
                f"• {_esc(ev.get('event_name'))} (<code>{_esc(ev.get('start_date'))}</code>)"
            )
        if len(removed) > 10:
            lines.append(f"… +{len(removed) - 10} ещё")

    if s.get("added", 0) == 0 and s.get("removed", 0) == 0:
        lines.extend(["", "Изменений с прошлого запуска нет."])

    ms = report.get("mapping_summary") or {}
    mapping_path = PROJECT_ROOT / "data" / "events_list" / "mapping" / "latest.json"
    if not ms and mapping_path.exists():
        try:
            ms = json.loads(mapping_path.read_text(encoding="utf-8")).get("summary") or {}
        except (json.JSONDecodeError, OSError):
            ms = {}

    suggested_items: list[dict] = []
    if mapping_path.exists():
        try:
            mdoc = json.loads(mapping_path.read_text(encoding="utf-8"))
            if not ms:
                ms = mdoc.get("summary") or {}
            suggested_items = mdoc.get("suggested") or []
        except (json.JSONDecodeError, OSError):
            pass

    if ms:
        lines.extend([
            "",
            "<b>Мэппинг с каталогом поинтов</b> (active rows)",
            f"Confirmed: <code>{_esc(ms.get('confirmed', 0))}</code> · "
            f"Suggested: <code>{_esc(ms.get('suggested', 0))}</code> · "
            f"Review: <code>{_esc(ms.get('review', 0))}</code> · "
            f"New: <code>{_esc(ms.get('new_unmapped', 0))}</code>",
        ])

    review_n = int(ms.get("review", 0))
    suggested_n = int(ms.get("suggested", 0))
    new_n = int(ms.get("new_unmapped", 0))

    if suggested_items:
        lines.extend(["", "<b>Suggested</b> (fuzzy — проверь вручную):"])
        for item in suggested_items[:5]:
            lines.append(
                f"• {_esc(item.get('list_name'))} → {_esc(item.get('canonical_name'))} "
                f"(<code>{_esc(item.get('confidence', ''))}</code>)"
            )

    if review_n or suggested_n:
        lines.extend([
            "",
            "⚠️ <b>Есть Suggested/Review</b> — открой mapping/latest.json или поправь алиасы.",
        ])
    elif new_n and s.get("added", 0) == 0 and s.get("removed", 0) == 0:
        lines.extend([
            "",
            "✅ <b>Лезть не обязательно</b> — New в основном trial без записи в points.",
        ])
    elif inactive and not (s.get("added") or s.get("removed")):
        lines.extend([
            "",
            "✅ <b>Лезть не обязательно</b> — inactive это canceled/hiatus на сайте.",
        ])

    lines.extend(["", "Лог: <code>data/events_list/changelog/latest.json</code>"])
    return "\n".join(lines)


def send_events_list_message(report: dict) -> bool:
    return send_telegram(format_events_list_message(report))


def cmd_events_list(report_path: Path | None) -> None:
    path = report_path or (PROJECT_ROOT / "data" / "events_list" / "changelog" / "latest.json")
    if not path.exists():
        print(f"No report at {path}", flush=True)
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    send_events_list_message(report)


if __name__ == "__main__":
    main()
