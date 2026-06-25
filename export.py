#!/usr/bin/env python3
"""Export Tableau-compatible CSV files from Supabase export.* views.

Usage:
    python export.py
    python export.py --output-dir ./data
    python export.py --include-results-by-event
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data"

# Legacy Tableau contract (unchanged column layout)
LEGACY_EXPORTS: dict[str, str] = {
    "export.dancers_points_info": "dancers_points_info.csv",
    "export.dancer_role_info": "dancer_role_info.csv",
    "export.dancers_results_info": "dancers_results_info.csv",
    "export.location_info": "location_info.csv",
    "export.events_wsdc": "events_wsdc.csv",
}

# Event-centric catalog for Tableau Public (join on event_id / edition_id)
EVENT_CATALOG_EXPORTS: dict[str, str] = {
    "export.event_catalog": "event_catalog.csv",
    "export.event_editions": "event_editions.csv",
    "export.scheduled_events": "scheduled_events.csv",
}

# SCD2 history as drop-in changed_*.csv (same contract as old-laptop workflow)
HISTORY_EXPORTS: dict[str, str] = {
    "export.changed_dancer_points_info": "changed_dancer_points_info.csv",
    "export.changed_dancer_role_info": "changed_dancer_role_info.csv",
}

# Denormalized results + event context (~47 MB); optional — join in Tableau instead
OPTIONAL_EXPORTS: dict[str, str] = {
    "export.results_by_event": "results_by_event.csv",
}

# Backward-compatible alias for tests and imports
EXPORTS: dict[str, str] = {**LEGACY_EXPORTS, **EVENT_CATALOG_EXPORTS, **HISTORY_EXPORTS}


def build_export_map(*, include_results_by_event: bool = False) -> dict[str, str]:
    exports = {**LEGACY_EXPORTS, **EVENT_CATALOG_EXPORTS, **HISTORY_EXPORTS}
    if include_results_by_event:
        exports.update(OPTIONAL_EXPORTS)
    return exports


def export_view(conn, view: str, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with conn.cursor() as cur:
        with cur.copy(
            f"COPY (SELECT * FROM {view}) TO STDOUT WITH (FORMAT csv, HEADER true)"
        ) as copy:
            chunks = []
            while data := copy.read():
                chunks.append(bytes(data))
            payload = b"".join(chunks)
    out_path.write_bytes(payload)
    lines = payload.count(b"\n")
    return max(lines - 1, 0)


def main() -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "db"))
    from connection import connect  # noqa: E402

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for exported CSV files",
    )
    parser.add_argument(
        "--include-results-by-event",
        action="store_true",
        help="Also export results_by_event.csv (~47 MB denormalized join)",
    )
    args = parser.parse_args()

    exports = build_export_map(include_results_by_event=args.include_results_by_event)

    print(f"Export directory: {args.output_dir}")

    with connect() as conn:
        for view, filename in exports.items():
            out_path = args.output_dir / filename
            rows = export_view(conn, view, out_path)
            print(f"  {filename}: {rows} rows -> {out_path}")

    print("\nExport complete.")


if __name__ == "__main__":
    main()
