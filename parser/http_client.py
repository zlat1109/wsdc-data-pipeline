"""HTTP client for WSDC lookup API (no Selenium)."""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

import requests

from .config import Config


class WSDCHttpClient:
    """Fetch dancer JSON via lookup2020/find (same path as the working notebook).

    Thread-safe: the CSRF token is shared across threads behind a lock so a pool
    of workers can reuse one client without racing on token refresh.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.session = requests.Session()
        self._token: str | None = None
        self._token_lock = threading.Lock()

    def get_token(self, force_refresh: bool = False) -> str:
        with self._token_lock:
            if self._token and not force_refresh:
                return self._token
            response = self.session.get(
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

        for attempt in range(max_retries):
            token = self.get_token(force_refresh=attempt > 0)
            try:
                response = self.session.post(
                    self.config.LOOKUP_URL,
                    data={"num": dancer_id, "_token": token},
                    headers=self.config.CONTESTER_HEADERS,
                    verify=self.config.VERIFY_SSL,
                    timeout=self.config.TIMEOUT,
                )
                if response.status_code in (403, 429):
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
        return None
