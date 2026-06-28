#!/usr/bin/env python3
"""Sync auto-maintained documentation from code and migrations.

Updates marked sections in docs/ and regenerates docs/database/_generated/*.

Usage:
    python scripts/sync_docs.py           # write changes
    python scripts/sync_docs.py --check   # exit 1 if anything would change (read-only)
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "docs"
GENERATED_DIR = DOCS / "database" / "_generated"
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

MARKER_START = "<!-- docs-sync:"
MARKER_END = "<!-- /docs-sync:"

DOCS_SUMMARY_RE = re.compile(r"^--\s*@docs-summary:\s*(.+)", re.IGNORECASE)

WATCH_PATHS = (
    "docs/database/_generated",
    "docs/database/migrations.md",
    "docs/database/export-views.md",
    "docs/operations/quality-monitoring.md",
)


def _escape_md_cell(value: str) -> str:
    return value.replace("|", r"\|")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_generate_schema_docs():
    return _load_module(
        "generate_schema_docs",
        PROJECT_ROOT / "scripts" / "generate_schema_docs.py",
    )


def _load_quality_checks():
    return _load_module(
        "quality_checks",
        PROJECT_ROOT / "db" / "quality_checks.py",
    )


def apply_block(text: str, block_id: str, body: str) -> str:
    start = f"{MARKER_START}{block_id} -->"
    end = f"{MARKER_END}{block_id} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"Missing docs-sync markers '{block_id}'")
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    return pattern.sub(replacement, text, count=1)


def _migration_summary(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        match = DOCS_SUMMARY_RE.match(line.strip())
        if match:
            return match.group(1).strip()

    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith("--") and len(stripped) > 2:
            paragraph.append(stripped[2:].strip())
        elif paragraph:
            break

    if paragraph:
        return " ".join(paragraph)

    slug = path.stem.split("_", 1)[-1].replace("_", " ")
    return slug


def build_migration_index_table() -> str:
    rows = ["| File | Summary |", "|------|---------|"]
    for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.sql")):
        summary = _escape_md_cell(_migration_summary(path))
        rows.append(f"| `{path.name}` | {summary} |")
    return "\n".join(rows)


def build_export_map_table(pairs: list[tuple[str, str]], gsd) -> str:
    lines = [
        "| View | CSV file | In default export |",
        "|------|----------|-------------------|",
    ]
    for view, csv in pairs:
        lines.append(f"| `{view}` | `{csv}` | {gsd.export_default_label(view)} |")
    return "\n".join(lines)


def build_core_quality_checks_table(checks) -> str:
    lines = [
        "| Check | Target | Meaning |",
        "|-------|--------|---------|",
    ]
    for check in checks.CORE_CHECKS:
        desc = _escape_md_cell(check.description)
        lines.append(f"| `{check.name}` | 0 | {desc} |")
    return "\n".join(lines)


def build_extended_quality_checks_table(checks) -> str:
    lines = [
        "| Extended check | Description |",
        "|----------------|-------------|",
    ]
    for check in checks.EXTENDED_CHECKS:
        desc = _escape_md_cell(check.description)
        lines.append(f"| `{check.name}` | {desc} |")
    return "\n".join(lines)


def compute_updates() -> dict[Path, str]:
    """Return absolute path -> desired file content (no disk writes)."""
    gsd = _load_generate_schema_docs()
    qc = _load_quality_checks()
    pairs = gsd.parse_export_map()

    updates: dict[Path, str] = {}
    for name, content in gsd.generate_fragments(live=False).items():
        updates[GENERATED_DIR / name] = content

    marker_jobs: tuple[tuple[Path, str, str], ...] = (
        (DOCS / "database" / "migrations.md", "migration-index", build_migration_index_table()),
        (
            DOCS / "database" / "export-views.md",
            "export-map",
            build_export_map_table(pairs, gsd),
        ),
        (
            DOCS / "operations" / "quality-monitoring.md",
            "core-quality-checks",
            build_core_quality_checks_table(qc),
        ),
        (
            DOCS / "operations" / "quality-monitoring.md",
            "extended-quality-checks",
            build_extended_quality_checks_table(qc),
        ),
    )

    marker_content: dict[Path, str] = {}
    for path, block_id, body in marker_jobs:
        if path not in marker_content:
            marker_content[path] = path.read_text(encoding="utf-8") if path.is_file() else ""
        marker_content[path] = apply_block(marker_content[path], block_id, body)

    updates.update(marker_content)
    return updates


def find_stale_paths(updates: dict[Path, str]) -> list[Path]:
    stale: list[Path] = []
    for path, desired in updates.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current != desired:
            stale.append(path)
    return stale


def apply_updates(updates: dict[Path, str]) -> list[Path]:
    changed: list[Path] = []
    for path, content in sorted(updates.items()):
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if sync would modify tracked files (read-only; no writes)",
    )
    args = parser.parse_args()

    updates = compute_updates()

    if args.check:
        stale = find_stale_paths(updates)
        if stale:
            rel_paths = [str(p.relative_to(PROJECT_ROOT)) for p in stale]
            print(
                "Documentation is out of sync. Run: python scripts/sync_docs.py",
                file=sys.stderr,
            )
            print("Stale files:", file=sys.stderr)
            for rel in rel_paths:
                print(f"  - {rel}", file=sys.stderr)
            return 1
        print("Documentation sync check passed.")
        return 0

    changed = apply_updates(updates)
    if changed:
        rel = [str(p.relative_to(PROJECT_ROOT)) for p in changed]
        print("Synced:", ", ".join(rel))
    else:
        print("Synced: no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
