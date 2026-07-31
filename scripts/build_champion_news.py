#!/usr/bin/env python3
"""Build / merge Champion News entities into the analytics site JSON.

Usage:
    python scripts/build_champion_news.py \\
      --data-dir data --site-repo /tmp/wsdc-site \\
      --cutoff 2026-07-28 [--dry-run]

Writes static/data/champion_news.json under --site-repo (or --output).
Emits a machine-readable report to --report.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.champion_news import (  # noqa: E402
    build_champion_path,
    detect_transitions,
    load_champion_news,
    load_timeline_events,
    merge_champion_news,
    write_champion_news,
)

DEFAULT_CUTOFF = date(2026, 7, 28)
SITE_REL = Path("static/data/champion_news.json")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def enrich_with_paths(candidates: list[dict], data_dir: Path) -> list[dict]:
    timelines = load_timeline_events(data_dir)
    out: list[dict] = []
    for card in candidates:
        dancer_id = card["dancer_id"]
        role = card["role"]
        events = timelines.get((dancer_id, role), [])
        enriched = dict(card)
        enriched["path"] = build_champion_path(events)
        out.append(enriched)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument(
        "--site-repo",
        type=Path,
        default=None,
        help="Analytics site checkout; writes static/data/champion_news.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Explicit output path (overrides --site-repo default path)",
    )
    parser.add_argument(
        "--existing",
        type=Path,
        default=None,
        help="Existing champion_news.json to merge into (default: output path)",
    )
    parser.add_argument("--cutoff", type=_parse_date, default=DEFAULT_CUTOFF)
    parser.add_argument(
        "--today",
        type=_parse_date,
        default=None,
        help="Override 'today' for post_date (tests)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "quality_reports" / "champion_news_last.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.output:
        out_path = args.output
    elif args.site_repo:
        out_path = args.site_repo / SITE_REL
    else:
        out_path = PROJECT_ROOT / "data" / "champion_news.json"

    existing_path = args.existing or out_path
    existing = load_champion_news(existing_path)

    required = [
        "dancers_results_info.csv",
        "dancer_role_info.csv",
        "event_editions.csv",
    ]
    for name in required:
        if not (args.data_dir / name).exists():
            print(f"ERROR: missing {args.data_dir / name}", file=sys.stderr)
            return 1

    print(
        f"Building Champion News candidates from {args.data_dir} "
        f"(cutoff={args.cutoff.isoformat()})"
    )
    candidates = detect_transitions(args.data_dir, cutoff=args.cutoff)
    candidates = enrich_with_paths(candidates, args.data_dir)
    print(f"Candidates after cutoff: {len(candidates)}")

    payload, report = merge_champion_news(
        existing,
        candidates,
        today=args.today,
    )
    report["output"] = str(out_path)
    report["cutoff"] = args.cutoff.isoformat()
    report["candidate_count"] = len(candidates)
    report["dry_run"] = bool(args.dry_run)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Champion News: +{report['created_count']} created, "
        f"{report['updated_count']} updated, "
        f"{len(report['skipped'])} skipped"
    )
    for slug in report["created"][:20]:
        print(f"  + {slug}")
    if len(report["created"]) > 20:
        print(f"  ... +{len(report['created']) - 20} more")

    if args.dry_run:
        print(f"Dry run — not writing {out_path}")
        print(f"Report: {args.report}")
        return 0

    write_champion_news(out_path, payload)
    print(f"Wrote {out_path}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
