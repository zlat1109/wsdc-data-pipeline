"""HTTP client for WSDC lookup API (no Selenium)."""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

import requests

from .config import Config


class RateLimitError(RuntimeError):
    """WSDC API returned 403/429 after all retries."""


class WSDCHttpClient:
    """Fetch dancer JSON via lookup2020/find (same path as the working notebook).

    Thread-safe for concurrent cloud_parse workers: each thread gets its own
    requests.Session; CSRF token refresh is serialized behind a lock.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self._token: str | None = None
        self._token_lock = threading.Lock()
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            self._local.session = session
        return session

    def get_token(self, force_refresh: bool = False) -> str:
        with self._token_lock:
            if self._token and not force_refresh:
                return self._token
            response = self._session().get(
                self.config.TOKEN_URL,
                headers=self.config.TOKEN_HEADERS,
                verify=self.config.VERIFY_SSL,
                timeout=self.config.TIMEOUT,
            )
            response.raise_for_status()
            match = re.search(r'name="_token" value="(.*?)"', response.text)
            if not match:
                raise RuntimeError("CSRF token not found on lookup2020 page")
            self._token = match.group(1)
            return self._token

    def fetch_dancer(self, dancer_id: int) -> dict[str, Any] | None:
        delay = float(os.getenv("PARSE_REQUEST_DELAY", "0.3"))
        max_retries = self.config.MAX_RETRIES
        last_status: int | None = None

        for attempt in range(max_retries):
            token = self.get_token(force_refresh=attempt > 0)
            try:
                response = self._session().post(
                    self.config.LOOKUP_URL,
                    data={"num": dancer_id, "_token": token},
                    headers=self.config.CONTESTER_HEADERS,
                    verify=self.config.VERIFY_SSL,
                    timeout=self.config.TIMEOUT,
                )
                if response.status_code in (403, 429):
                    last_status = response.status_code
                    time.sleep(2 ** attempt)
                    continue
                # 404 = dancer id does not exist; permanent, do not retry.
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
                if not data:
                    return None
                if delay:
                    time.sleep(delay)
                return data
            except requests.RequestException:
                if attempt >= max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        if last_status in (403, 429):
            raise RateLimitError(
                f"WSDC API rate-limited (HTTP {last_status}) "
                f"for dancer_id={dancer_id} after {max_retries} retries"
            )
        return None
