#!/usr/bin/env python3
"""Probe WSDC API for data changes (guardian dancer fingerprints).

Compares a combined hash of sample dancer responses against the latest
probe_hash stored in history.parse_runs. Exits 0 and prints 'changed' when
an update is detected, 'unchanged' otherwise.

Usage:
    python scripts/check_updates.py
    python scripts/check_updates.py --write-hash   # store hash without triggering
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# Representative dancer IDs across the registry range.
GUARDIAN_IDS = [1, 42, 311, 619, 5000, 10000, 26410, 27000]

TOKEN_URL = "https://points.worldsdc.com/lookup2020"
LOOKUP_URL = "https://points.worldsdc.com/lookup2020"
AUTocomplete_URL = "https://points.worldsdc.com/lookup/autocomplete?q="

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WSDCDataPipeline/1.0; +https://github.com/zlat1109/wsdc-data-pipeline)"
    ),
    "Accept": "application/json, text/html, */*",
}


def get_csrf_token(session: requests.Session) -> str:
    response = session.get(TOKEN_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    match = re.search(r'name="_token" value="(.*?)"', response.text)
    if not match:
        raise RuntimeError("CSRF token not found on WSDC lookup page")
    return match.group(1)


def fetch_dancer_payload(session: requests.Session, token: str, dancer_id: int) -> dict | list:
    response = session.post(
        LOOKUP_URL,
        data={"num": dancer_id, "_token": token},
        headers={
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def compute_probe_hash(session: requests.Session) -> str:
    token = get_csrf_token(session)
    parts: list[str] = []
    for dancer_id in GUARDIAN_IDS:
        try:
            payload = fetch_dancer_payload(session, token, dancer_id)
            parts.append(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 — probe should continue
            parts.append(f"error:{dancer_id}:{exc}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest


def get_last_probe_hash(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT probe_hash
            FROM history.parse_runs
            WHERE probe_hash IS NOT NULL
            ORDER BY run_id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return row[0] if row else None


def record_probe(conn, probe_hash: str, changed: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO history.parse_runs (source, status, probe_hash, finished_at)
            VALUES ('github-actions', %s, %s, %s)
            """,
            (
                "skipped" if not changed else "running",
                probe_hash,
                datetime.now(timezone.utc),
            ),
        )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-hash",
        action="store_true",
        help="Always persist probe hash to parse_runs",
    )
    args = parser.parse_args()

    session = requests.Session()
    probe_hash = compute_probe_hash(session)
    print(f"probe_hash={probe_hash}")

    with connect() as conn:
        last_hash = get_last_probe_hash(conn)
        changed = last_hash is None or last_hash != probe_hash
        print(f"last_hash={last_hash or '(none)'}")
        print("changed" if changed else "unchanged")

        if args.write_hash or changed:
            record_probe(conn, probe_hash, changed)

    # Exit code 0 always; GitHub Actions reads stdout keyword.
    if changed:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
