"""WSDC dancer ID probing via autocomplete API (same method as the parser notebook)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import requests

CHECK_URL = os.getenv(
    "CHECK_CONTESTERS_URL",
    "https://points.worldsdc.com/lookup/autocomplete?q=",
)
CHECK_HEADERS = {
    "Referer": "https://points.worldsdc.com/lookup2020",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


@dataclass
class ScanResult:
    watermark: int
    live_max_id: int
    new_ids: list[int] = field(default_factory=list)
    new_dancers: list[dict] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.live_max_id > self.watermark


def check_id_exists(session: requests.Session, dancer_id: int, retries: int = 2) -> bool:
    for attempt in range(retries + 1):
        try:
            response = session.get(
                f"{CHECK_URL}{dancer_id}",
                headers=CHECK_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            data = json.loads(response.text)
            return any(item.get("wscid") == dancer_id for item in data)
        except Exception:
            if attempt >= retries:
                return False
            time.sleep(0.5)
    return False


def get_dancer_autocomplete(session: requests.Session, dancer_id: int) -> dict | None:
    try:
        response = session.get(
            f"{CHECK_URL}{dancer_id}",
            headers=CHECK_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        data = json.loads(response.text)
        for item in data:
            if item.get("wscid") == dancer_id:
                return item
    except Exception:
        return None
    return None


def _coarse_upper_bound(
    session: requests.Session,
    anchor: int,
    coarse_step: int,
    safety_limit: int,
    delay: float,
) -> int:
    last_found = anchor
    probe = anchor + coarse_step
    while probe < safety_limit:
        if check_id_exists(session, probe):
            last_found = probe
            probe += coarse_step
            time.sleep(delay)
        else:
            break
    return last_found


def _linear_tail_max(
    session: requests.Session,
    start_id: int,
    max_misses: int,
    safety_limit: int,
    delay: float,
) -> int:
    """+1 scan from start_id until consecutive misses; return highest ID found."""
    live_max = start_id
    dancer_id = start_id
    misses = 0
    while misses < max_misses and dancer_id < safety_limit:
        dancer_id += 1
        if check_id_exists(session, dancer_id):
            live_max = dancer_id
            misses = 0
        else:
            misses += 1
        time.sleep(delay)
    return live_max


def scan_ids_above_watermark(
    session: requests.Session,
    watermark: int,
    max_consecutive_misses: int | None = None,
    delay: float | None = None,
) -> ScanResult:
    """Detect updates by comparing live max dancer ID to watermark.

    Uses coarse jumps (step 100) to approach the live max, then a short linear
    tail (~100 + max_misses API calls). Does NOT scan every ID between watermark
    and live max — matching the rule "new IDs appeared above last known max".
    """
    max_misses = max_consecutive_misses or int(os.getenv("PROBE_MAX_MISSES", "5"))
    scan_delay = delay if delay is not None else float(os.getenv("PROBE_SCAN_DELAY", "0.05"))
    coarse_step = int(os.getenv("PROBE_COARSE_STEP", "100"))
    safety_limit = int(os.getenv("PROBE_SAFETY_LIMIT", "100000"))

    coarse_high = _coarse_upper_bound(
        session, watermark, coarse_step, safety_limit, scan_delay
    )
    live_max = _linear_tail_max(
        session, coarse_high, max_misses, safety_limit, scan_delay
    )

    new_ids: list[int] = []
    new_dancers: list[dict] = []
    if live_max > watermark:
        # Report sample of newest IDs (not full range — can be 1000+ after busy weekends)
        sample_start = max(watermark + 1, live_max - 19)
        new_ids = list(range(sample_start, live_max + 1))
        for dancer_id in reversed(new_ids[-10:]):
            info = get_dancer_autocomplete(session, dancer_id)
            if info:
                new_dancers.append(info)

    return ScanResult(
        watermark=watermark,
        live_max_id=live_max,
        new_ids=new_ids,
        new_dancers=list(reversed(new_dancers)),
    )
