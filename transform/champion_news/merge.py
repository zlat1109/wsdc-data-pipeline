"""Merge Champion News entities into champion_news.json by slug."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PRESERVE_FIELDS = ("notes", "overrides")


def post_date_today(today: date | None = None) -> str:
    d = today or date.today()
    return d.strftime("%d-%m-%Y")


def _post_date_sort_key(post_date: str) -> tuple[int, int, int]:
    try:
        d, m, y = post_date.strip().split("-")
        return (int(y), int(m), int(d))
    except Exception:
        return (0, 0, 0)


def load_champion_news(path: Path) -> dict:
    if not path.exists():
        return {"summaries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"summaries": []}
    if not isinstance(payload.get("summaries"), list):
        payload["summaries"] = []
    return payload


def write_champion_news(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def flatten_by_slug(payload: dict) -> dict[str, dict]:
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


def _preserve_manual(existing: dict, candidate: dict) -> dict:
    merged = deepcopy(candidate)
    for field in PRESERVE_FIELDS:
        if field in existing and existing[field] not in (None, "", {}, []):
            merged[field] = deepcopy(existing[field])
    return merged


def merge_champion_news(
    existing_payload: dict,
    candidates: list[dict],
    *,
    today: date | None = None,
) -> tuple[dict, dict[str, Any]]:
    """Merge candidate transition cards into site JSON.

    New slugs are created. Existing slugs are updated (path refresh) while
    preserving notes/overrides.
    """
    today = today or date.today()
    run_post_date = post_date_today(today)
    payload = deepcopy(existing_payload) if existing_payload else {"summaries": []}
    summaries = list(payload.get("summaries") or [])
    by_slug = flatten_by_slug({"summaries": summaries})

    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    new_block_events: list[dict] = []

    for candidate in candidates:
        slug = (candidate.get("slug") or "").strip()
        if not slug:
            skipped.append("?")
            continue

        if slug in by_slug:
            existing = by_slug[slug]["event"]
            bi = by_slug[slug]["block_index"]
            ei = by_slug[slug]["event_index"]
            merged_event = _preserve_manual(existing, candidate)
            merged_event["slug"] = slug
            summaries[bi]["events"][ei] = merged_event
            summaries[bi]["events_count"] = len(summaries[bi]["events"])
            updated.append(slug)
            by_slug[slug]["event"] = merged_event
            continue

        event = deepcopy(candidate)
        event["slug"] = slug
        new_block_events.append(event)
        created.append(slug)

    if new_block_events:
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
            existing_events = list(summaries[same_idx].get("events") or [])
            existing_slugs = {(e.get("slug") or "").strip() for e in existing_events}
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
