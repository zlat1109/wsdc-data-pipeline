#!/usr/bin/env python3
"""Generate markdown schema fragments from migrations and export.py.

Usage:
    python scripts/generate_schema_docs.py
    python scripts/generate_schema_docs.py --live
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "database" / "_generated"

OPTIONAL_EXPORT_VIEWS = frozenset(
    {"export.results_by_event", "export.dancers_results_with_name"}
)

OPTIONAL_EXPORT_LABELS: dict[str, str] = {
    "export.results_by_event": "No (`--include-results-by-event`)",
    "export.dancers_results_with_name": "No (`--include-results-with-name`)",
}

CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+\.\w+)\s*\((.*?)\);",
    re.DOTALL | re.IGNORECASE,
)
CREATE_VIEW_RE = re.compile(
    r"CREATE(?:\s+OR\s+REPLACE)?\s+VIEW\s+(\w+\.\w+)\s+AS",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(
    r"COMMENT ON (?:TABLE|VIEW)\s+(\w+\.\w+)\s+IS\s+'([^']*)'",
    re.IGNORECASE,
)


def export_default_label(view: str) -> str:
    if view.startswith("derived."):
        return "Yes (post-export)"
    return OPTIONAL_EXPORT_LABELS.get(view, "Yes")


def parse_migrations() -> tuple[dict[str, list[str]], dict[str, str], dict[str, str]]:
    tables: dict[str, list[str]] = {}
    views: set[str] = set()
    comments: dict[str, str] = {}

    for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.sql")):
        text = path.read_text(encoding="utf-8")
        for m in COMMENT_RE.finditer(text):
            comments[m.group(1).lower()] = m.group(2)
        for m in CREATE_VIEW_RE.finditer(text):
            views.add(m.group(1).lower())
        for m in CREATE_TABLE_RE.finditer(text):
            fq = m.group(1).lower()
            body = m.group(2)
            cols: list[str] = []
            for line in body.splitlines():
                line = line.strip().rstrip(",")
                if not line or line.upper().startswith(
                    ("PRIMARY", "UNIQUE", "CONSTRAINT", "CHECK", "FOREIGN", "CREATE INDEX")
                ):
                    continue
                if line.upper().startswith("INSERT INTO"):
                    break
                col = line.split()[0] if line.split() else ""
                if col and col not in ("CONSTRAINT", "UNIQUE", "PRIMARY"):
                    cols.append(col)
            if cols:
                tables[fq] = cols

    view_dict = {v: [] for v in sorted(views)}
    return tables, view_dict, comments


def parse_export_map() -> list[tuple[str, str]]:
    export_py = PROJECT_ROOT / "export.py"
    text = export_py.read_text(encoding="utf-8")
    pairs: list[tuple[str, str]] = []
    for dict_name in ("LEGACY_EXPORTS", "EVENT_CATALOG_EXPORTS", "HISTORY_EXPORTS", "OPTIONAL_EXPORTS"):
        block_m = re.search(rf"{dict_name}:\s*dict\[str,\s*str\]\s*=\s*\{{(.*?)\}}", text, re.DOTALL)
        if not block_m:
            continue
        block = block_m.group(1)
        for line in block.splitlines():
            m = re.search(r'"(export\.\w+)"\s*:\s*"([^"]+)"', line)
            if m:
                pairs.append((m.group(1), m.group(2)))

    derived_m = re.search(r"DERIVED_EXPORTS:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)", text, re.DOTALL)
    if derived_m:
        for m in re.finditer(r'"([^"]+\.csv)"', derived_m.group(1)):
            pairs.append((f"derived.{m.group(1).replace('.csv', '')}", m.group(1)))
    return pairs


def fetch_live_columns() -> dict[str, list[tuple[str, str]]]:
    sys.path.insert(0, str(PROJECT_ROOT / "db"))
    from connection import connect  # noqa: E402

    live: dict[str, list[tuple[str, str]]] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema || '.' || table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema IN ('staging', 'core', 'history', 'export')
                ORDER BY 1, ordinal_position
                """
            )
            for schema_table, col, dtype in cur.fetchall():
                key = schema_table.lower()
                live.setdefault(key, []).append((col, dtype))
    return live


def render_tables_md(
    tables: dict[str, list[str]],
    comments: dict[str, str],
    live: dict | None,
) -> str:
    lines = ["# Generated tables", "", "[auto] Regenerate with `python scripts/generate_schema_docs.py`", ""]
    for fq in sorted(tables):
        lines.append(f"## {fq}")
        if fq in comments:
            lines.append(f"\n{comments[fq]}\n")
        lines.append("| Column | Migration parse | Live type |")
        lines.append("|--------|-----------------|-----------|")
        live_cols = {c: t for c, t in live.get(fq, [])} if live else {}
        for col in tables[fq]:
            dtype = live_cols.get(col, "—")
            lines.append(f"| {col} | text/PK/FK | {dtype} |")
        lines.append("")
    return "\n".join(lines)


def render_views_md(views: dict[str, list[str]], comments: dict[str, str]) -> str:
    lines = ["# Generated views", "", "[auto] Regenerate with `python scripts/generate_schema_docs.py`", ""]
    for fq in sorted(views):
        lines.append(f"## {fq}")
        if fq in comments:
            lines.append(f"\n{comments[fq]}\n")
        lines.append("")
    return "\n".join(lines)


def render_export_map_md(pairs: list[tuple[str, str]]) -> str:
    lines = [
        "# Generated export map",
        "",
        "[auto] Regenerate with `python scripts/generate_schema_docs.py`",
        "",
        "| View | CSV | Default export |",
        "|------|-----|----------------|",
    ]
    for view, csv in pairs:
        lines.append(f"| `{view}` | `{csv}` | {export_default_label(view)} |")
    lines.append("")
    return "\n".join(lines)


def generate_fragments(*, live: bool = False) -> dict[str, str]:
    """Return {filename: markdown} for docs/database/_generated/."""
    tables, views, comments = parse_migrations()
    pairs = parse_export_map()
    live_cols = fetch_live_columns() if live else None
    return {
        "tables.md": render_tables_md(tables, comments, live_cols),
        "views.md": render_views_md(views, comments),
        "export_map.md": render_export_map_md(pairs),
    }


def write_export_map_md(pairs: list[tuple[str, str]]) -> None:
    (OUTPUT_DIR / "export_map.md").write_text(render_export_map_md(pairs), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Query information_schema for column types")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fragments = generate_fragments(live=args.live)
    for name, content in fragments.items():
        (OUTPUT_DIR / name).write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_DIR}/tables.md, views.md, export_map.md")


if __name__ == "__main__":
    main()
