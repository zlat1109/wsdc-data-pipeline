#!/usr/bin/env python3
"""Smoke-test WSDC endpoints from current network (local or GitHub Actions).

Checks whether points.worldsdc.com blocks the runner IP for:
  1. Autocomplete GET (used by check_updates probe)
  2. Lookup page GET + CSRF token (parser prerequisite)
  3. Lookup POST JSON (full parser HTTP path)
  4. Optional burst of autocomplete calls (rate-limit probe)

Exit 0 if all required checks pass; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import requests

AUTocomplete_URL = "https://points.worldsdc.com/lookup/autocomplete?q="
TOKEN_URL = "https://points.worldsdc.com/lookup2020"
# Working endpoint from the proven notebook parser (POST to bare /lookup2020 returns 405)
LOOKUP_URL = "https://points.worldsdc.com/lookup2020/find"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://points.worldsdc.com/lookup2020",
    "X-Requested-With": "XMLHttpRequest",
}

POST_HEADERS = {
    **BROWSER_HEADERS,
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Origin": "https://points.worldsdc.com",
}


def _print(label: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}: {detail}", flush=True)


def check_autocomplete(session: requests.Session, dancer_id: int) -> tuple[bool, str]:
    try:
        response = session.get(
            f"{AUTocomplete_URL}{dancer_id}",
            headers=BROWSER_HEADERS,
            timeout=30,
        )
        detail = f"HTTP {response.status_code}, {len(response.text)} bytes"
        if response.status_code != 200:
            return False, detail
        data = json.loads(response.text)
        found = any(item.get("wscid") == dancer_id for item in data)
        return found, detail + (", dancer found" if found else ", dancer missing")
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_token(session: requests.Session) -> tuple[bool, str, str | None]:
    try:
        response = session.get(TOKEN_URL, headers=BROWSER_HEADERS, timeout=30)
        detail = f"HTTP {response.status_code}, {len(response.text)} bytes"
        if response.status_code != 200:
            return False, detail, None
        match = re.search(r'name="_token" value="(.*?)"', response.text)
        if not match:
            return False, detail + ", CSRF token not found", None
        token = match.group(1)
        return True, detail + f", token={token[:8]}...", token
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), None


def check_lookup_post(
    session: requests.Session, token: str, dancer_id: int
) -> tuple[bool, str]:
    try:
        response = session.post(
            LOOKUP_URL,
            data={"num": dancer_id, "_token": token},
            headers=POST_HEADERS,
            timeout=30,
        )
        detail = f"HTTP {response.status_code}, {len(response.text)} bytes"
        if response.status_code == 405:
            return False, detail + " (Method Not Allowed — POST blocked?)"
        if response.status_code == 403:
            return False, detail + " (Forbidden — IP blocked?)"
        if response.status_code == 429:
            return False, detail + " (Too Many Requests — rate limited)"
        if response.status_code != 200:
            return False, detail
        try:
            data = response.json()
        except json.JSONDecodeError:
            snippet = response.text[:120].replace("\n", " ")
            return False, detail + f", not JSON: {snippet!r}"
        if not data:
            return False, detail + ", empty JSON"
        return True, detail + f", keys={list(data.keys())[:5]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def burst_autocomplete(session: requests.Session, start_id: int, count: int) -> tuple[bool, str]:
    ok = 0
    blocked = 0
    for offset in range(count):
        dancer_id = start_id + offset
        try:
            response = session.get(
                f"{AUTocomplete_URL}{dancer_id}",
                headers=BROWSER_HEADERS,
                timeout=20,
            )
            if response.status_code in (403, 429):
                blocked += 1
            elif response.status_code == 200:
                ok += 1
        except Exception:
            blocked += 1
        time.sleep(0.05)
    detail = f"{ok}/{count} OK, {blocked} blocked/errors"
    return blocked == 0, detail


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dancer-id", type=int, default=27136)
    parser.add_argument("--burst", type=int, default=20, help="Autocomplete burst size (0=skip)")
    args = parser.parse_args()

    session = requests.Session()
    all_ok = True

    ok, detail = check_autocomplete(session, args.dancer_id)
    _print("autocomplete", ok, detail)
    all_ok &= ok

    ok, detail, token = check_token(session)
    _print("lookup_page+csrf", ok, detail)
    all_ok &= ok

    if token:
        ok, detail = check_lookup_post(session, token, args.dancer_id)
        _print("lookup_post", ok, detail)
        all_ok &= ok
    else:
        _print("lookup_post", False, "skipped (no CSRF token)")
        all_ok = False

    if args.burst > 0:
        ok, detail = burst_autocomplete(session, args.dancer_id, args.burst)
        _print(f"autocomplete_burst x{args.burst}", ok, detail)
        all_ok &= ok

    print("overall=" + ("pass" if all_ok else "fail"), flush=True)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
