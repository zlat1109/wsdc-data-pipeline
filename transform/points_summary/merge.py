"""Merge Point Summary entities into points_summaries.json by slug."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def post_date_today(today: date | None = None) -> str:
    d = today or date.today()
    return d.strftime("%d-%m-%Y")


def _post_date_sort_key(post_date: str) -> tuple[int, int, int]:
    try:
        d, m, y = post_date.strip().split("-")
        return (int(y), int(m), int(d))
    except Exception:
        return (0, 0, 0)


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def load_summaries(path: Path) -> dict:
    if not path.exists():
        return {"summaries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"summaries": []}
    summaries = payload.get("summaries")
    if not isinstance(summaries, list):
        payload["summaries"] = []
    return payload


def flatten_events_by_slug(payload: dict) -> dict[str, dict]:
    """Map slug → {event, post_date, block_index, event_index}."""
    out: dict[str, dict] = {}
    for bi, block in enumerate(payload.get("summaries") or []):
        post_date = (block.get("post_date") or "").strip()
        for ei, event in enumerate(block.get("events") or []):
            slug = (event.get("slug") or "").strip()
            if not slug:
                continue
            out[slug] = {
                "event": event,
                "post_date": post_date,
                "block_index": bi,
                "event_index": ei,
            }
    return out


def _preserve_unknown_fields(existing: dict, new_event: dict) -> dict:
    """New report wins known rebuild fields; keep telegraph_url and unknowns."""
    merged = deepcopy(existing)
    for key, value in new_event.items():
        if key == "telegraph_url":
            continue
        if key == "slug":
            merged["slug"] = value
            continue
        merged[key] = value
    # Prefer existing telegraph_url when present; otherwise take new (usually None).
    if existing.get("telegraph_url"):
        merged["telegraph_url"] = existing["telegraph_url"]
    elif new_event.get("telegraph_url"):
        merged["telegraph_url"] = new_event["telegraph_url"]
    else:
        merged["telegraph_url"] = existing.get("telegraph_url")
    return merged


def merge_points_summaries(
    existing_payload: dict,
    candidates: list[dict],
    *,
    cutoff: date,
    update_window_days: int = 30,
    today: date | None = None,
    max_entries: int = 0,
) -> tuple[dict, dict[str, Any]]:
    """Merge candidate event reports into the site JSON.

    candidates: list of event dicts with slug, start_date, end_date, divisions…
    max_entries: keep at most N post_date blocks (0 = no truncate). Default 0 so
    historical site blocks are never dropped by a pipeline refresh.
    """
    today = today or date.today()
    run_post_date = post_date_today(today)
    payload = deepcopy(existing_payload) if existing_payload else {"summaries": []}
    summaries = list(payload.get("summaries") or [])
    by_slug = flatten_events_by_slug({"summaries": summaries})

    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    new_block_events: list[dict] = []

    for candidate in candidates:
        slug = (candidate.get("slug") or "").strip()
        start = _parse_iso(candidate.get("start_date"))
        end = _parse_iso(candidate.get("end_date")) or start
        if not slug or not start:
            skipped.append(slug or candidate.get("name") or "?")
            continue

        if slug in by_slug:
            existing = by_slug[slug]["event"]
            # Outside update window: leave untouched.
            if end and end < today - timedelta(days=update_window_days):
                skipped.append(slug)
                continue
            bi = by_slug[slug]["block_index"]
            ei = by_slug[slug]["event_index"]
            merged_event = _preserve_unknown_fields(existing, candidate)
            # Never rewrite historical post_date / slug.
            merged_event["slug"] = slug
            summaries[bi]["events"][ei] = merged_event
            summaries[bi]["events_count"] = len(summaries[bi]["events"])
            updated.append(slug)
            by_slug[slug]["event"] = merged_event
            continue

        # New entity: only after cutoff and with content.
        if start < cutoff:
            skipped.append(slug)
            continue
        if not candidate.get("divisions"):
            skipped.append(slug)
            continue

        event = deepcopy(candidate)
        event["slug"] = slug
        new_block_events.append(event)
        created.append(slug)

    if new_block_events:
        # Append into today's block, or prepend a new block.
        same_idx = next(
            (
                i
                for i, s in enumerate(summaries)
                if (s.get("post_date") or "").strip() == run_post_date
            ),
            None,
        )
        if same_idx is None:
            summaries.insert(
                0,
                {
                    "post_date": run_post_date,
                    "events_count": len(new_block_events),
                    "events": new_block_events,
                },
            )
        else:
            # Merge new events into the existing same-day block (incremental).
            existing_events = list(summaries[same_idx].get("events") or [])
            existing_slugs = {
                (e.get("slug") or "").strip() for e in existing_events
            }
            for ev in new_block_events:
                if ev["slug"] not in existing_slugs:
                    existing_events.append(ev)
            summaries[same_idx]["events"] = existing_events
            summaries[same_idx]["events_count"] = len(existing_events)
            if same_idx != 0:
                summaries.insert(0, summaries.pop(same_idx))

    summaries.sort(
        key=lambda s: _post_date_sort_key(s.get("post_date") or ""),
        reverse=True,
    )
    if max_entries > 0:
        summaries = summaries[:max_entries]

    payload["summaries"] = summaries
    report = {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "created_count": len(created),
        "updated_count": len(updated),
        "post_date": run_post_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return payload, report


def write_summaries(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
