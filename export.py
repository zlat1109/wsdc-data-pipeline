#!/usr/bin/env python3
"""Export Tableau-compatible CSV files from Supabase export.* views.

Usage:
    python export.py
    python export.py --output-dir ./data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# View -> output filename (Tableau Public contract)
EXPORTS: dict[str, str] = {
    "export.dancers_points_info": "dancers_points_info.csv",
    "export.dancer_role_info": "dancer_role_info.csv",
    "export.dancers_results_info": "dancers_results_info.csv",
    "export.location_info": "location_info.csv",
    "export.events_wsdc": "events_wsdc.csv",
}


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for exported CSV files",
    )
    args = parser.parse_args()

    print(f"Export directory: {args.output_dir}")

    with connect() as conn:
        for view, filename in EXPORTS.items():
            out_path = args.output_dir / filename
            rows = export_view(conn, view, out_path)
            print(f"  {filename}: {rows} rows -> {out_path}")

    print("\nExport complete.")


if __name__ == "__main__":
    main()
