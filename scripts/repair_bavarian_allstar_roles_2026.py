#!/usr/bin/env python3
"""Deprecated one-off: moved to archive/repair_scripts/repair_bavarian_allstar_roles_2026.py

Prefer declarative corrections under transform/knowledge/corrections/ and
quality gates. Run the archived script only as a temporary DB bridge.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ARCH = Path(__file__).resolve().parents[1] / "archive" / "repair_scripts" / "repair_bavarian_allstar_roles_2026.py"
print(
    f"WARNING: {Path(__file__).name} is archived. "
    f"Prefer transform/knowledge/corrections/. Running {ARCH} …",
    file=sys.stderr,
)
sys.argv[0] = str(ARCH)
runpy.run_path(str(ARCH), run_name="__main__")
