"""load.py imports db/ modules by bare name; scripts/ must never shadow them."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# scripts/ has CLI wrappers with the same module names as their db/ counterparts.
SHADOWED = ("build_edition_tiers", "build_event_catalog")


def test_db_modules_win_after_watermark_import():
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(PROJECT_ROOT / 'db')!r});"
        "import watermark;"
        f"import {', '.join(SHADOWED)};"
        + ";".join(f"print({name}.__file__)" for name in SHADOWED)
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    resolved = proc.stdout.strip().splitlines()
    assert len(resolved) == len(SHADOWED)
    for path in resolved:
        assert Path(path).parent.name == "db", f"{path} shadows the db/ module"
