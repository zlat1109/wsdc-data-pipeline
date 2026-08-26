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
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_updates_gate import registry_cooldown_blocks  # noqa: E402


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
    cooldown_active = bool(report.get("cooldown_active"))
    cooldown_blocks = registry_cooldown_blocks(
        cooldown_active=cooldown_active,
        ready=ready,
        ready_reason=report.get("ready_reason"),
        gate_status=report.get("gate_status"),
    )
    if cooldown_blocks:
        status = "🧊 <b>Cooldown: registry catch-up уже был на этой неделе</b>"
    else:
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

    pending = report.get("pending_events") or []
    gate_status = report.get("gate_status")
    ready_reason = report.get("ready_reason")

    if gate_status == "no_concluded_events":
        lines.extend(
            [
                "",
                "ℹ️ Нет завершённых ивентов в snapshot (тихие выходные / только будущие) — parse не запускаем.",
            ]
        )
    elif ready_reason == "no_new_ids" and pending:
        lines.extend(
            [
                "",
                "ℹ️ Новых dancer ID нет — live-coverage по pending не сканируем. "
                "Ждём появления результатов (или новых ID) для оставшихся ивентов.",
            ]
        )
    if cooldown_blocks:
        lines.extend(
            [
                "",
                f"До: <code>{_esc(report.get('cooldown_until', 'next Monday'))}</code>",
                f"Last success run_id: <code>{_esc(report.get('last_success_run_id', '?'))}</code>",
            ]
        )

    if pending:
        lines.extend(["", "<b>Ждём результаты (pending)</b>:"])
        for name in pending:
            lines.append(f"• {_esc(name)}")

    suggestions = report.get("db_name_suggestions") or {}
    if suggestions:
        lines.extend(["", "<b>Возможные расхождения в названии (DB подсказки)</b>:"])
        for name, info in suggestions.items():
            sug = info.get("suggested_db_name")
            score = info.get("score")
            edition_year = info.get("edition_year")
            edition_month = info.get("edition_month")
            if sug:
                lines.append(
                    f"• {_esc(name)} → {_esc(sug)} "
                    f"(score <code>{_esc(score)}</code>, edition <code>{_esc(edition_year)}-{_esc(edition_month)}</code>)"
                )

    matched = report.get("matched_events") or {}
    if matched:
        lines.extend(["", "<b>Найдено в live (новые танцоры)</b>:"])
        for expected, live in matched.items():
            lines.append(f"• {_esc(expected)} → {_esc(live)}")

    trigger_events = report.get("trigger_events") or []
    if trigger_events:
        lines.extend(["", "<b>Триггер full-parse (ивенты в live, ещё не в DB)</b>:"])
        for name in trigger_events:
            lines.append(f"• {_esc(name)}")

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

    if report.get("zombie_parse_close") and int(
        (report.get("zombie_parse_close") or {}).get("closed_count") or 0
    ) > 0:
        z = report["zombie_parse_close"]
        lines.append("")
        lines.append(
            f"🧹 Auto-closed stuck parse_runs: <code>{_esc(z.get('closed_count'))}</code> "
            f"(age ≥ <code>{_esc(z.get('min_age_minutes'))}</code>m)"
        )
        for item in (z.get("stuck") or [])[:4]:
            lines.append(
                f"• run_id <code>{_esc(item.get('run_id'))}</code> "
                f"age <code>{_esc(item.get('age_minutes'))}</code>m "
                f"source <code>{_esc(item.get('source'))}</code>"
            )

    if report.get("parse_in_flight"):
        age = report.get("parse_in_flight_age_minutes")
        lines.append("")
        lines.append(
            "⏳ Full-parse уже выполняется "
            f"(run_id <code>{_esc(report.get('parse_in_flight_run_id', '?'))}</code>"
            + (
                f", ~<code>{_esc(age)}</code>m"
                if age is not None
                else ""
            )
            + ") — повторный запуск отложен."
        )
        # Warn before auto-close window; still give one-liner for manual close.
        if age is not None and int(age) >= 60:
            lines.append(
                "⚠ Похоже на zombie parse_run — если workflow уже упал: "
                "<code>python scripts/close_parse_runs.py --dry-run</code> "
                "затем <code>--apply</code>"
            )

    if cooldown_blocks:
        lines.append("")
        lines.append(
            "Авто-parse для registry-only (все ивенты уже в DB) отключён до следующего понедельника."
        )
    elif ready:
        lines.append("")
        if report.get("ready_reason") == "partial_events_ready":
            lines.append(
                "Часть ожидаемых ивентов уже в live — стартуем полный full-parse "
                "(весь registry, не только эти ивенты)."
            )
        else:
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
        "🚀 <b>Часть ивентов готова — начинаю полный парсинг (full parse)</b>",
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
    trigger_events = report.get("trigger_events") or []
    if trigger_events:
        lines.extend(["", "<b>Ивенты-триггер (partial gate)</b>:"])
        for name in trigger_events:
            live = matched.get(name)
            if live:
                lines.append(f"✅ {_esc(name)} → {_esc(live)}")
            else:
                lines.append(f"✅ {_esc(name)}")
    elif matched or pending:
        lines.extend(["", "<b>Ивенты (gate)</b>:"])
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

    ps = _format_point_summary_section()
    if ps:
        lines.extend(["", *ps])

    cn = _format_champion_news_section()
    if cn:
        lines.extend(["", *cn])

    ops = _format_ops_reminders(stats)
    if ops:
        lines.extend(["", *ops])

    attention = _format_attention_sections()
    if attention:
        lines.extend(["", "⚠️ <b>Требует внимания</b>", ""] + attention)

    if stats.get("repo"):
        lines.append(f"Repo: {_esc(stats['repo'])}")

    return "\n".join(lines)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _format_point_summary_section() -> list[str]:
    """Optional Point Summary line for #WSDC_Pipeline_Complete."""
    report_path = Path(
        os.getenv(
            "POINT_SUMMARY_REPORT",
            "data/quality_reports/point_summary_last.json",
        )
    )
    data = _load_json(report_path)
    if not data:
        return []
    if data.get("ok") is False or data.get("error") or data.get("failed"):
        err = data.get("error") or data.get("failed") or "build failed"
        return [f"⚠️ Point Summary FAILED: {_esc(err)}"]
    created = int(data.get("created_count") or 0)
    updated = int(data.get("updated_count") or 0)
    names = []
    for slug in (data.get("created") or [])[:8]:
        # slug: YYYY-MM-DD-event-name → title-ish
        parts = str(slug).split("-", 3)
        label = parts[3].replace("-", " ").title() if len(parts) >= 4 else slug
        names.append(label)
    lines = [
        f"📊 Point Summary: +<code>{created}</code> "
        f"(updated <code>{updated}</code>)",
        '<a href="https://wsdc-analytics.github.io/points-summary.html">'
        "points-summary.html</a>",
    ]
    for name in names:
        lines.append(f"• {_esc(name)}")
    if created > len(names):
        lines.append(f"• … +{created - len(names)} more")
    return lines


def _format_champion_news_section() -> list[str]:
    """Optional Champion News line for #WSDC_Pipeline_Complete."""
    report_path = Path(
        os.getenv(
            "CHAMPION_NEWS_REPORT",
            "data/quality_reports/champion_news_last.json",
        )
    )
    data = _load_json(report_path)
    if not data:
        return []
    if data.get("ok") is False or data.get("error") or data.get("failed"):
        err = data.get("error") or data.get("failed") or "build failed"
        return [f"⚠️ Champion News FAILED: {_esc(err)}"]
    created = int(data.get("created_count") or 0)
    updated = int(data.get("updated_count") or 0)
    lines = [
        f"👑 Champion News: +<code>{created}</code> "
        f"(updated <code>{updated}</code>)",
        '<a href="https://wsdc-analytics.github.io/champion-news.html">'
        "champion-news.html</a>",
    ]
    for slug in (data.get("created") or [])[:8]:
        lines.append(f"• {_esc(slug)}")
    if created > 8:
        lines.append(f"• … +{created - 8} more")
    if created > 0:
        lines.append(
            "Editorial Telegram: manual — see docs/operations/champion-news.md"
        )
    return lines


def _format_ops_reminders(stats: dict) -> list[str]:
    """Optional hands-off reminders (Tableau / force rebuild)."""
    if not stats.get("csv_committed"):
        return []
    return [
        "🖥 Tableau Public: refresh extracts after CSV commit (manual)",
        "Force calendar/site after DB-only location fix: Actions → "
        "<b>Force rebuild calendar/site</b>",
    ]


def _scd2_reconcile_command(check_name: str) -> str | None:
    mapping = {
        "points_history_drift": "scripts/reconcile_points_history.py",
        "roles_history_drift": "scripts/reconcile_roles_history.py",
        "names_history_drift": "scripts/reconcile_names_history.py",
    }
    script = mapping.get(check_name)
    if not script:
        return None
    return f"python {script} --dry-run && python {script} --apply"


def _format_supabase_quality_attention(report: dict) -> list[str]:
    summary = report.get("summary") or {}
    errors = int(summary.get("errors", 0))
    warnings = int(summary.get("warnings", 0))
    if errors == 0 and warnings == 0:
        return []

    lines = [
        "<b>Supabase quality checks</b>",
        f"Passed: <code>{_esc(summary.get('passed', 0))}</code> / "
        f"<code>{_esc(summary.get('total', 0))}</code> · "
        f"errors <code>{_esc(errors)}</code> · warnings <code>{_esc(warnings)}</code>",
    ]
    failed = [c for c in report.get("checks") or [] if not c.get("ok")]
    scd2 = [c for c in failed if str(c.get("name") or "").endswith("_history_drift")]
    other = [c for c in failed if c not in scd2]
    if scd2:
        lines.append("<b>SCD2 history drift</b>")
        for check in scd2[:6]:
            lines.append(
                f"• <code>{_esc(check.get('name'))}</code>: "
                f"<code>{_esc(check.get('value'))}</code> "
                f"(≤ <code>{_esc(check.get('max_value'))}</code>)"
            )
            cmd = _scd2_reconcile_command(str(check.get("name") or ""))
            if cmd:
                lines.append(f"  ↳ <code>{_esc(cmd)}</code>")
            elif check.get("fix_hint"):
                lines.append(f"  ↳ {_esc(check.get('fix_hint'))}")
    for check in other[:8]:
        sev = str(check.get("severity", "error")).upper()
        lines.append(
            f"• [{_esc(sev)}] <code>{_esc(check.get('name'))}</code>: "
            f"<code>{_esc(check.get('value'))}</code> "
            f"(≤ <code>{_esc(check.get('max_value'))}</code>)"
        )
        hint = check.get("fix_hint")
        if hint:
            lines.append(f"  ↳ {_esc(hint)}")
    if len(other) > 8:
        lines.append(f"… +{len(other) - 8} ещё")
    lines.append("Log: <code>data/quality_reports/supabase_latest.json</code>")
    return lines


# Location / venue mismatch codes — prioritize + render rich Telegram cards.
_LOCATION_ATTENTION_CODES = frozenset(
    {
        "SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT",
        "EVENT_ID_CANONICAL_LOCATION_MISMATCH",
        "BASELINE_VS_LOCATION_OVERRIDE",
        "EDITION_LOCATION_BASELINE_DRIFT",
        "EVENT_NAME_LOCATION_COUNTRY_CONFLICT",
        "EVENT_NAME_LOCATION_ID_COLLISION",
        "CATALOG_TYPICAL_UPCOMING_CONFLICT",
    }
)


def _location_example_card(code: str, ex: dict) -> list[str]:
    """One Telegram card for a location mismatch example."""
    name = str(ex.get("event_name") or ex.get("canonical_name") or "?")[:55]
    eid = ex.get("event_id")
    year = ex.get("event_year")
    month = ex.get("event_month")
    edition = ""
    if year is not None and str(year) and month is not None and str(month):
        edition = f"{year}-{month}"
    header_bits = [f"<b>{_esc(name)}</b>"]
    if eid not in (None, ""):
        header_bits.append(f"id <code>{_esc(eid)}</code>")
    if edition:
        header_bits.append(f"<code>{_esc(edition)}</code>")
    lines = ["• " + " · ".join(header_bits)]

    if code == "SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT":
        lines.append(
            f"  results <code>{_esc(ex.get('results_country'))}</code> "
            f"(lid <code>{_esc(ex.get('location_id'))}</code>) → "
            f"schedule <code>{_esc(ex.get('scheduled_country'))}</code> "
            f"({_esc(str(ex.get('scheduled_location') or '')[:40])})"
        )
        lines.append("  ↳ add EVENT_NAME_LOCATION_OVERRIDES or confirm new event_id")
    elif code == "EVENT_ID_CANONICAL_LOCATION_MISMATCH":
        lines.append(
            f"  canonical <code>{_esc(ex.get('canonical_country'))}</code> "
            f"({_esc(str(ex.get('canonical_location') or '')[:40])}) vs "
            f"results <code>{_esc(ex.get('results_country'))}</code> "
            f"(lid <code>{_esc(ex.get('results_location_id'))}</code>)"
        )
        lines.append("  ↳ update KNOWN_EVENT_METADATA / EVENT_NAME_LOCATION_OVERRIDES")
    elif code == "BASELINE_VS_LOCATION_OVERRIDE":
        lines.append(
            f"  baseline lid <code>{_esc(ex.get('baseline_location_id'))}</code> → "
            f"override lid <code>{_esc(ex.get('override_location_id'))}</code> "
            f"({_esc(str(ex.get('override_location') or '')[:40])})"
        )
        lines.append("  ↳ UPDATE edition_location_baseline source=manual after remap")
    elif code == "EDITION_LOCATION_BASELINE_DRIFT":
        lines.append(
            f"  baseline lid <code>{_esc(ex.get('baseline_location_id'))}</code> → "
            f"current <code>{_esc(ex.get('current_location_id'))}</code>"
        )
        lines.append("  ↳ confirm venue move (manual) or fix shared wrong lid")
    elif code == "EVENT_NAME_LOCATION_COUNTRY_CONFLICT":
        lines.append(
            f"  lid <code>{_esc(ex.get('location_id'))}</code> "
            f"<code>{_esc(ex.get('location_country'))}</code> vs name hints "
            f"{_esc(ex.get('name_hints') or '')}"
        )
        lines.append("  ↳ verify lid or add override")
    elif code == "EVENT_NAME_LOCATION_ID_COLLISION":
        lines.append(
            f"  lids <code>{_esc(ex.get('location_ids'))}</code> "
            f"countries <code>{_esc(ex.get('countries'))}</code>"
        )
        lines.append("  ↳ split series or force one lid via overrides")
    elif code == "CATALOG_TYPICAL_UPCOMING_CONFLICT":
        lines.append(
            f"  typical {_esc(str(ex.get('typical_location') or '')[:40])} vs "
            f"upcoming {_esc(str(ex.get('upcoming_location') or '')[:40])}"
        )
        lines.append("  ↳ update catalog typical or confirm series move")
    else:
        # Fallback: dump a few useful keys
        bits = []
        for key in (
            "location_id",
            "results_country",
            "scheduled_country",
            "baseline_location_id",
            "override_location_id",
            "current_location_id",
        ):
            if ex.get(key) not in (None, ""):
                bits.append(f"{key}={ex.get(key)}")
        if bits:
            lines.append("  " + _esc(" · ".join(bits)[:120]))
    return lines


def _format_location_mismatch_cards(manual_items: list) -> list[str]:
    """Rich cards for location findings (priority section)."""
    # Cross-country / poison-seed first — collision lists are noisy and ate the old top-6.
    _code_priority = {
        "SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT": 0,
        "EVENT_ID_CANONICAL_LOCATION_MISMATCH": 1,
        "BASELINE_VS_LOCATION_OVERRIDE": 2,
        "EDITION_LOCATION_BASELINE_DRIFT": 3,
        "EVENT_NAME_LOCATION_COUNTRY_CONFLICT": 4,
        "CATALOG_TYPICAL_UPCOMING_CONFLICT": 5,
        "EVENT_NAME_LOCATION_ID_COLLISION": 6,
    }
    loc_items = [f for f in manual_items if f.get("code") in _LOCATION_ATTENTION_CODES]
    loc_items.sort(key=lambda f: _code_priority.get(str(f.get("code") or ""), 99))
    if not loc_items:
        return []
    lines = [
        "<b>Location mismatches</b>",
        f"Findings: <code>{_esc(len(loc_items))}</code> "
        "(load continues — fix lids / baseline / overrides)",
    ]
    cards_shown = 0
    max_cards = 10
    for item in loc_items:
        code = str(item.get("code") or "")
        examples = [e for e in (item.get("examples") or []) if isinstance(e, dict)]
        # Collision findings: at most 2 examples so cross-country cards stay visible.
        if code == "EVENT_NAME_LOCATION_ID_COLLISION":
            examples = examples[:2]
        if not examples:
            lines.append(f"• [{_esc(item.get('severity'))}] <code>{_esc(code)}</code>")
            cards_shown += 1
            continue
        for ex in examples:
            if cards_shown >= max_cards:
                break
            lines.extend(_location_example_card(code, ex))
            cards_shown += 1
        if cards_shown >= max_cards:
            break
    remaining_ex = max(
        0, sum(len(f.get("examples") or []) for f in loc_items) - cards_shown
    )
    if remaining_ex > 0:
        lines.append(f"… +{remaining_ex} more examples in quality report")
    fix = next(
        (str(f.get("suggested_fix") or "").strip() for f in loc_items if f.get("suggested_fix")),
        "",
    )
    if fix:
        lines.append(f"Hint: {_esc(fix[:160])}")
    lines.append("Log: <code>data/quality_reports/latest.json</code>")
    return lines


def _format_preprocess_quality_attention(q: dict) -> list[str]:
    qs = q.get("summary") or {}
    manual_new = int(qs.get("manual_review_new_count", qs.get("new_findings", 0)) or 0)
    manual_total = int(qs.get("manual_review_count", qs.get("total_findings", 0)) or 0)
    manual_items = (q.get("manual_review_required") or {}).get("findings") or []
    if manual_total == 0 and not manual_items:
        return []

    loc_lines = _format_location_mismatch_cards(manual_items)
    other_items = [f for f in manual_items if f.get("code") not in _LOCATION_ATTENTION_CODES]
    show_items = [f for f in other_items if f.get("is_new")] if manual_new else other_items

    lines: list[str] = []
    if loc_lines:
        lines.extend(loc_lines)
    if show_items:
        if lines:
            lines.append("")
        lines.extend(
            [
                "<b>Preprocess manual review</b>",
                f"New: <code>{_esc(manual_new)}</code> · total open: <code>{_esc(manual_total)}</code>",
            ]
        )
        for item in show_items[:6]:
            examples = item.get("examples") or []
            example = ""
            if examples and isinstance(examples[0], dict):
                example = str(
                    examples[0].get("event_name") or examples[0].get("location_id") or ""
                )[:50]
            lines.append(
                f"• [{_esc(item.get('severity'))}] <code>{_esc(item.get('code'))}</code>"
                + (f": {_esc(example)}" if example else "")
            )
        lines.append("Log: <code>data/quality_reports/latest.json</code>")
    elif not loc_lines:
        return []
    return lines


def _format_baseline_drift_attention() -> list[str]:
    report = _load_json(
        PROJECT_ROOT / "data" / "quality_reports" / "edition_location_baseline_drift.json"
    )
    if not report:
        return []
    drift_count = int(report.get("drift_count", 0) or 0)
    poison = report.get("poison_seed_suspects") or []
    if drift_count <= 0 and not poison:
        return []
    lines = [
        "<b>Edition location baseline</b>",
        f"Drifts: <code>{_esc(drift_count)}</code> · "
        f"auto-added: <code>{_esc(report.get('auto_added', 0))}</code>"
        + (
            f" · poison suspects: <code>{_esc(len(poison))}</code>"
            if poison
            else ""
        ),
    ]
    for item in (report.get("drifts") or [])[:6]:
        base_loc = str(item.get("baseline_location") or "")[:35]
        cur_loc = str(item.get("current_location") or "")[:35]
        geo = ""
        if base_loc or cur_loc:
            geo = f" ({_esc(base_loc)} → {_esc(cur_loc)})"
        lines.append(
            f"• id <code>{_esc(item.get('event_id'))}</code> "
            f"{_esc(item.get('event_year'))}-{_esc(item.get('event_month'))} "
            f"<code>{_esc(str(item.get('event_name', '')[:40]))}</code>: "
            f"lid <code>{_esc(item.get('baseline_location_id'))}</code> → "
            f"<code>{_esc(item.get('current_location_id'))}</code>{geo}"
        )
        lines.append("  ↳ confirm venue move (manual) or fix shared wrong lid")
    for item in poison[:4]:
        lines.append(
            f"• ⚠ poison-seed auto-add id <code>{_esc(item.get('event_id'))}</code> "
            f"{_esc(item.get('event_year'))}-{_esc(item.get('event_month'))} "
            f"<code>{_esc(str(item.get('event_name', '')[:35]))}</code>: "
            f"lid <code>{_esc(item.get('location_id'))}</code> "
            f"vs override <code>{_esc(item.get('override_location_id'))}</code>"
        )
        lines.append("  ↳ do not trust auto baseline; UPDATE source=manual after remap")
    lines.append("Log: <code>data/quality_reports/edition_location_baseline_drift.json</code>")
    return lines


def _format_attention_sections() -> list[str]:
    supabase = _load_json(PROJECT_ROOT / "data" / "quality_reports" / "supabase_latest.json")
    preprocess = _load_json(PROJECT_ROOT / "data" / "quality_reports" / "latest.json")
    supabase_lines = _format_supabase_quality_attention(supabase) if supabase else []
    preprocess_lines = _format_preprocess_quality_attention(preprocess) if preprocess else []
    baseline_lines = _format_baseline_drift_attention()
    if not supabase_lines and not preprocess_lines and not baseline_lines:
        return []
    sections_flat: list[str] = []
    if supabase_lines:
        sections_flat.extend(supabase_lines)
    if preprocess_lines:
        if sections_flat:
            sections_flat.append("")
        sections_flat.extend(preprocess_lines)
    if baseline_lines:
        if sections_flat:
            sections_flat.append("")
        sections_flat.extend(baseline_lines)
    return sections_flat


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


def format_pipeline_failed_message(context: dict) -> str:
    workflow = context.get("workflow", "unknown")
    run_url = context.get("run_url", "")
    job = context.get("job", "")
    lines = [
        "#WSDC_Pipeline_Failed",
        "",
        "❌ <b>Pipeline failed</b>",
        "",
        f"Workflow: <code>{_esc(workflow)}</code>",
    ]
    if job:
        lines.append(f"Job: <code>{_esc(job)}</code>")
    if run_url:
        lines.append(f"Logs: <a href=\"{_esc(run_url)}\">GitHub Actions</a>")
    lines.extend(["", "Проверь логи и при необходимости перезапусти вручную."])
    return "\n".join(lines)


def cmd_pipeline_failed() -> None:
    context = {
        "workflow": os.getenv("GITHUB_WORKFLOW", "unknown"),
        "job": os.getenv("GITHUB_JOB", ""),
        "run_url": os.getenv("GITHUB_SERVER_URL", "https://github.com")
        + "/"
        + os.getenv("GITHUB_REPOSITORY", "")
        + "/actions/runs/"
        + os.getenv("GITHUB_RUN_ID", ""),
    }
    send_telegram(format_pipeline_failed_message(context))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="Notify after check-updates")
    probe.add_argument("report", type=Path, help="JSON from check_updates --json-report")

    parse_start = sub.add_parser("parse-start", help="Notify when full parse is triggered")
    parse_start.add_argument("report", type=Path, help="JSON from check_updates --json-report")

    sub.add_parser("parse-start-live", help="Notify parse start using live DB + WSDC scan")
    sub.add_parser("pipeline-complete", help="Notify after full-parse load+export")
    sub.add_parser("pipeline-failed", help="Notify when a pipeline workflow fails")

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
    elif args.command == "pipeline-failed":
        cmd_pipeline_failed()
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

    geo_review = report.get("geo_review") or []
    geo_count = int(s.get("geo_review_count", len(geo_review)) or 0)
    if geo_count:
        lines.extend(
            [
                "",
                f"⚠️ <b>Trial geo review</b>: <code>{_esc(geo_count)}</code>",
            ]
        )
        for item in geo_review[:8]:
            lines.append(
                f"• {_esc(item.get('event_name'))} "
                f"(<code>{_esc(item.get('reason'))}</code>) "
                f"— {_esc((item.get('location_raw') or '')[:40])}"
            )
        if len(geo_review) > 8:
            lines.append(f"… +{len(geo_review) - 8} ещё")

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
