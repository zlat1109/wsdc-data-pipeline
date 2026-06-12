"""Update WSDC ID watermark after a successful load."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from wsdc_id_probe import scan_ids_above_watermark  # noqa: E402


def refresh_watermark(conn, run_id: int) -> int:
    """Scan from MAX(core.dancers) and store live max on parse_runs."""
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(dancer_id), 0) FROM core.dancers")
        anchor = int(cur.fetchone()[0])

    session = requests.Session()
    result = scan_ids_above_watermark(session, anchor)
    watermark = result.live_max_id

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE history.parse_runs
            SET max_dancer_id_watermark = %s,
                probe_details = COALESCE(probe_details, '{}'::jsonb)
                    || jsonb_build_object(
                        'post_load_watermark', %s,
                        'post_load_live_max', %s
                    )
            WHERE run_id = %s
            """,
            (watermark, anchor, watermark, run_id),
        )
    conn.commit()
    return watermark
