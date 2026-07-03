"""Schedule helpers for check-updates probe runs."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")

# Evening cron is 20:00 Europe/Madrid (18:00 UTC in summer). GitHub Actions may slip.
_FRIDAY_FINAL_MIN_HOUR = 17


def is_friday_final_probe(now: datetime | None = None) -> bool:
    """True on the last scheduled Friday probe (evening slot, Europe/Madrid).

    ``PROBE_SLOT`` env (set by check-updates.yml from cron):
    - ``evening`` — Friday fallback enabled on any Friday run in that slot
    - ``morning`` — never treat as final Friday probe
    - unset — Friday and local hour >= 17 (manual runs / workflow_dispatch)
    """
    now = now or datetime.now(MADRID_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=MADRID_TZ)
    else:
        now = now.astimezone(MADRID_TZ)
    if now.weekday() != 4:
        return False

    slot = os.getenv("PROBE_SLOT", "").strip().lower()
    if slot == "evening":
        return True
    if slot == "morning":
        return False
    return now.hour >= _FRIDAY_FINAL_MIN_HOUR
