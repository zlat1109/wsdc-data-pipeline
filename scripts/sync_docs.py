#!/usr/bin/env python3
"""Sync auto-maintained documentation from code and migrations.

Updates marked sections in docs/ and regenerates docs/database/_generated/*.

Usage:
    python scripts/sync_docs.py           # write changes
    python scripts/sync_docs.py --check   # exit 1 if anything would change
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "docs"
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

MARKER_START = "<!-- docs-sync:"
MARKER_END = "<!-- /docs-sync:"


def _replace_block(path: Path, block_id: str, body: str) -> bool:
    text = path.read_text(encoding="utf-8")
    start = f"{MARKER_START}{block_id} -->"
    end = f"{MARKER_END}{block_id} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Missing docs-sync markers '{block_id}' in {path}")
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    new_text = pattern.sub(replacement, text, count=1)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def _migration_summary(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and len(stripped) > 2:
            return stripped[2:].strip()
    slug = path.stem.split("_", 1)[-1].replace("_", " ")
    return slug


def build_migration_index_table() -> str:
    rows = ["| File | Summary |", "|------|---------|"]
    for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.sql")):
        rows.append(f"| `{path.name}` | {_migration_summary(path)} |")
    return "\n".join(rows)


def build_export_map_table() -> str:
    import importlib.util

    path = PROJECT_ROOT / "scripts" / "generate_schema_docs.py"
    spec = importlib.util.spec_from_file_location("generate_schema_docs", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pairs = mod.parse_export_map()
    mod.write_export_map_md(pairs)

    optional_flags = {
        "export.results_by_event": "No (`--include-results-by-event`)",
        "export.dancers_results_with_name": "No (`--include-results-with-name`)",
    }
    lines = [
        "| View | CSV file | In default export |",
        "|------|----------|-------------------|",
    ]
    for view, csv in pairs:
        if view.startswith("derived."):
            default = "Yes (post-export)"
        elif view in optional_flags:
            default = optional_flags[view]
        else:
            default = "Yes"
        lines.append(f"| `{view}` | `{csv}` | {default} |")
    return "\n".join(lines)


def build_core_quality_checks_table() -> str:
    sys.path.insert(0, str(PROJECT_ROOT / "db"))
    from quality_checks import CORE_CHECKS  # noqa: E402

    lines = [
        "| Check | Target | Meaning |",
        "|-------|--------|---------|",
    ]
    for check in CORE_CHECKS:
        lines.append(f"| `{check.name}` | 0 | {check.description} |")
    return "\n".join(lines)


def build_extended_quality_checks_table() -> str:
    sys.path.insert(0, str(PROJECT_ROOT / "db"))
    from quality_checks import EXTENDED_CHECKS  # noqa: E402

    lines = [
        "| Extended check | Historical problem |",
        "|----------------|-------------------|",
    ]
    for check in EXTENDED_CHECKS:
        lines.append(f"| `{check.name}` | {check.description} |")
    return "\n".join(lines)


def run_generate_schema_docs() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "generate_schema_docs.py")],
        cwd=PROJECT_ROOT,
        check=True,
    )


def sync_all() -> list[str]:
    changed: list[str] = []

    run_generate_schema_docs()
    changed.append("docs/database/_generated/")

    if _replace_block(DOCS / "database" / "migrations.md", "migration-index", build_migration_index_table()):
        changed.append("docs/database/migrations.md")

    if _replace_block(DOCS / "database" / "export-views.md", "export-map", build_export_map_table()):
        changed.append("docs/database/export-views.md")

    if _replace_block(
        DOCS / "operations" / "quality-monitoring.md",
        "core-quality-checks",
        build_core_quality_checks_table(),
    ):
        changed.append("docs/operations/quality-monitoring.md")

    if _replace_block(
        DOCS / "operations" / "quality-monitoring.md",
        "extended-quality-checks",
        build_extended_quality_checks_table(),
    ):
        changed.append("docs/operations/quality-monitoring.md")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if sync would modify tracked files (for CI)",
    )
    args = parser.parse_args()

    watch_paths = [
        "docs/database/_generated",
        "docs/database/migrations.md",
        "docs/database/export-views.md",
        "docs/operations/quality-monitoring.md",
    ]

    if args.check:
        sync_all()
        diff = subprocess.run(
            ["git", "diff", "--quiet", "--", *watch_paths],
            cwd=PROJECT_ROOT,
        )
        if diff.returncode != 0:
            show = subprocess.run(
                ["git", "diff", "--stat", "--", *watch_paths],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            print("Documentation is out of sync. Run: python scripts/sync_docs.py", file=sys.stderr)
            if show.stdout:
                print(show.stdout, file=sys.stderr)
            return 1
        print("Documentation sync check passed.")
        return 0

    changed = sync_all()
    unique = sorted(set(changed))
    print("Synced:", ", ".join(unique) if unique else "no marker sections changed")
    print("Regenerated docs/database/_generated/*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
