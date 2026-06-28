#!/usr/bin/env python3
"""Reconcile open history.dancer_roles_history with core.dancer_roles (divisions only).

Usage:
    python scripts/reconcile_roles_history.py --dry-run
    python scripts/reconcile_roles_history.py --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

DIVISION_SIG = """
core.dancer_roles_division_sig(
    {prefix}dominate_role,
    {prefix}dominate_required,
    {prefix}dominate_allowed,
    {prefix}non_dominate_role,
    {prefix}non_dominate_required,
    {prefix}non_dominate_allowed,
    {prefix}non_dominate_recommended,
    {prefix}non_dominate_role_highest_level_points,
    {prefix}non_dominate_role_highest_level
)
"""


def _sig(prefix: str) -> str:
    return DIVISION_SIG.format(prefix=prefix)


STALE_COUNT_SQL = f"""
SELECT count(*)
FROM history.dancer_roles_history h
LEFT JOIN core.dancer_roles c ON c.dancer_id = h.dancer_id
WHERE h.valid_to IS NULL
  AND (
      c.dancer_id IS NULL
      OR {_sig("h.")} IS DISTINCT FROM {_sig("c.")}
  )
"""

MISSING_COUNT_SQL = f"""
SELECT count(*)
FROM core.dancer_roles c
WHERE NOT EXISTS (
    SELECT 1 FROM history.dancer_roles_history h
    WHERE h.valid_to IS NULL
      AND h.dancer_id = c.dancer_id
      AND {_sig("h.")} = {_sig("c.")}
)
"""

CLOSE_STALE_SQL = f"""
UPDATE history.dancer_roles_history h
SET valid_to = %(today)s
FROM core.dancer_roles c
WHERE h.valid_to IS NULL
  AND h.dancer_id = c.dancer_id
  AND {_sig("h.")} IS DISTINCT FROM {_sig("c.")}
"""

CLOSE_ORPHAN_SQL = """
UPDATE history.dancer_roles_history h
SET valid_to = %(today)s
WHERE h.valid_to IS NULL
  AND NOT EXISTS (SELECT 1 FROM core.dancer_roles c WHERE c.dancer_id = h.dancer_id)
"""

INSERT_MISSING_SQL = f"""
INSERT INTO history.dancer_roles_history (
    dancer_id, dancer_name, dominate_role, dominate_required, dominate_allowed,
    non_dominate_role, non_dominate_required, non_dominate_allowed,
    non_dominate_recommended, non_dominate_role_highest_level_points,
    non_dominate_role_highest_level, valid_from, valid_to, run_id
)
SELECT
    c.dancer_id,
    d.dancer_name,
    c.dominate_role,
    c.dominate_required,
    c.dominate_allowed,
    c.non_dominate_role,
    c.non_dominate_required,
    c.non_dominate_allowed,
    c.non_dominate_recommended,
    c.non_dominate_role_highest_level_points,
    c.non_dominate_role_highest_level,
    %(today)s,
    NULL,
    %(run_id)s
FROM core.dancer_roles c
JOIN core.dancers d ON d.dancer_id = c.dancer_id
WHERE NOT EXISTS (
    SELECT 1 FROM history.dancer_roles_history h
    WHERE h.valid_to IS NULL
      AND h.dancer_id = c.dancer_id
      AND {_sig("h.")} = {_sig("c.")}
)
"""
