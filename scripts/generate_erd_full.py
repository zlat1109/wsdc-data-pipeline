#!/usr/bin/env python3
"""Regenerate full-column warehouse ERD assets from db/migrations.

Writes:
  docs/assets/wsdc_warehouse_full.mmd
  docs/assets/erd-explorer-full.html
  docs/database/erd-columns.md

Usage:
  python scripts/generate_erd_full.py
"""

from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "db" / "migrations"
ASSETS = ROOT / "docs" / "assets"
DOCS_DB = ROOT / "docs" / "database"

TYPE_MAP = {
    "integer": "int",
    "int": "int",
    "bigint": "bigint",
    "smallint": "int",
    "numeric": "numeric",
    "double": "float",
    "real": "float",
    "boolean": "bool",
    "bool": "bool",
    "text": "text",
    "varchar": "text",
    "character": "text",
    "date": "date",
    "timestamptz": "timestamptz",
    "timestamp": "timestamp",
    "jsonb": "jsonb",
    "json": "json",
    "uuid": "uuid",
    "serial": "int",
    "bigserial": "bigint",
}

HISTORY = {
    "parse_runs",
    "dancer_points_history",
    "dancer_roles_history",
    "dancer_names_history",
    "events_list_runs",
    "events_list_changes",
}

SOFT_DROP = {
    ("edition_calendar_dates", "event_id"),
    ("scheduled_events", "location_id"),
    ("events_list_current", "location_id"),
}

SOFT_RELS = [
    ("events", "edition_calendar_dates", "event_id soft"),
    ("events", "events_list_current", "canonical_event_id soft"),
    ("locations", "events_list_current", "location_id soft"),
    ("locations", "scheduled_events", "location_id soft"),
    ("event_editions", "results", "edition grain"),
    ("event_editions", "edition_division_tiers", "edition grain"),
    ("event_editions", "edition_location_baseline", "edition grain"),
]


def norm_type(raw: str) -> str:
    r = raw.lower().strip()
    for k, v in TYPE_MAP.items():
        if r.startswith(k):
            return v
    return re.sub(r"[^a-z0-9_]", "", r.split("(")[0]) or "text"


def default_parent_col(pt: str, ccol: str) -> str:
    defaults = {
        "events": "event_id",
        "dancers": "dancer_id",
        "locations": "location_id",
        "levels": "level",
        "rules_editions": "rules_version",
        "parse_runs": "run_id",
        "events_list_runs": "run_id",
    }
    return defaults.get(pt, ccol)


def parse_migrations() -> tuple[
    OrderedDict[str, list[tuple[str, str]]],
    dict[str, set[str]],
    list[tuple[str, str, str, str]],
]:
    tables: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()
    pks: dict[str, set[str]] = {}
    fks: list[tuple[str, str, str, str]] = []

    create_re = re.compile(
        r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+(core|history)\.(\w+)\s*\((.*?)\);",
        re.I | re.S,
    )
    # One ALTER can list several ADD COLUMN clauses (comma-separated).
    alter_block_re = re.compile(
        r"ALTER TABLE\s+(core|history)\.(\w+)\s+(.*?);",
        re.I | re.S,
    )
    add_col_re = re.compile(
        r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+(\w+)\s+(\S+)",
        re.I,
    )
    inline_fk_re = re.compile(
        r"(\w+)\s+[^\n,]*?\bREFERENCES\s+(?:core|history)\.(\w+)\s*(?:\((\w+)\))?",
        re.I,
    )
    table_pk_re = re.compile(r"PRIMARY KEY\s*\(([^)]+)\)", re.I)

    def ensure_col(tname: str, col: str, typ: str) -> None:
        tables.setdefault(tname, [])
        pks.setdefault(tname, set())
        existing = {c for c, _ in tables[tname]}
        if col not in existing:
            tables[tname].append((col, norm_type(typ)))

    for path in sorted(MIG.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for m in create_re.finditer(text):
            tname, body = m.group(2), m.group(3)
            cols: list[tuple[str, str]] = []
            pk_set: set[str] = set()
            for line in body.splitlines():
                raw = line.strip().rstrip(",")
                if not raw or raw.startswith("--"):
                    continue
                up = raw.upper()
                if up.startswith(
                    ("PRIMARY KEY", "UNIQUE", "CONSTRAINT", "CHECK", "FOREIGN KEY")
                ):
                    tpk = table_pk_re.search(raw)
                    if tpk:
                        for c in tpk.group(1).split(","):
                            pk_set.add(c.strip().strip('"'))
                    continue
                col_m = re.match(r'^"?(\w+)"?\s+(\w+(?:\([^)]*\))?)', raw)
                if not col_m:
                    continue
                col, typ = col_m.group(1), col_m.group(2)
                if col.upper() in {
                    "PRIMARY",
                    "UNIQUE",
                    "CONSTRAINT",
                    "CHECK",
                    "FOREIGN",
                }:
                    continue
                cols.append((col, norm_type(typ)))
                if re.search(r"\bPRIMARY KEY\b", raw, re.I):
                    pk_set.add(col)
                for fk in inline_fk_re.finditer(raw):
                    ccol, pt, pcol = fk.group(1), fk.group(2), fk.group(3)
                    fks.append(
                        (tname, ccol, pt, pcol or default_parent_col(pt, ccol))
                    )
            if tname not in tables:
                tables[tname] = cols
                pks[tname] = pk_set
            else:
                existing = {c for c, _ in tables[tname]}
                for c, t in cols:
                    if c not in existing:
                        tables[tname].append((c, t))
                pks[tname] |= pk_set

        for m in alter_block_re.finditer(text):
            tname, body = m.group(2), m.group(3)
            for add in add_col_re.finditer(body):
                col, typ = add.group(1), add.group(2).rstrip(",")
                ensure_col(tname, col, typ)
                # FK may be on the same ADD COLUMN fragment
                frag = body[add.start() : add.end() + 120]
                for fk in inline_fk_re.finditer(frag):
                    ccol, pt, pcol = fk.group(1), fk.group(2), fk.group(3)
                    fks.append(
                        (tname, ccol, pt, pcol or default_parent_col(pt, ccol))
                    )

    return tables, pks, fks


def build_erd(
    tables: OrderedDict[str, list[tuple[str, str]]],
    pks: dict[str, set[str]],
    fks: list[tuple[str, str, str, str]],
) -> tuple[str, set[tuple[str, str]]]:
    hard_fks: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for x in fks:
        if (x[0], x[1]) in SOFT_DROP:
            continue
        if x not in seen and x[0] in tables and x[2] in tables:
            seen.add(x)
            hard_fks.append(x)
    fk_col_set = {(t, c) for t, c, _, _ in hard_fks}

    lines = ["erDiagram"]
    for child, ccol, parent, _pcol in hard_fks:
        lines.append(f'  {parent} ||--o{{ {child} : "{ccol}"')
    for parent, child, label in SOFT_RELS:
        if child in tables and parent in tables:
            lines.append(f'  {parent} ||--o{{ {child} : "{label}"')
    for tname, cols in tables.items():
        lines.append(f"  {tname} {{")
        for col, typ in cols:
            flags = []
            if col in pks.get(tname, set()):
                flags.append("PK")
            if (tname, col) in fk_col_set:
                flags.append("FK")
            flag = (" " + ", ".join(flags)) if flags else ""
            lines.append(f"    {typ} {col}{flag}")
        lines.append("  }")
    return "\n".join(lines) + "\n", fk_col_set


def write_inventory(
    tables: OrderedDict[str, list[tuple[str, str]]],
    pks: dict[str, set[str]],
    fk_col_set: set[tuple[str, str]],
) -> None:
    inv = [
        "# Full column inventory",
        "",
        "Source: `db/migrations/*.sql` (DDL applied to Supabase).",
        f"Tables: **{len(tables)}**. Interactive map: [full ERD explorer](../assets/erd-explorer-full.html).",
        "Compact map (keys only): [ERD explorer](../assets/erd-explorer.html).",
        "Regenerate: `python scripts/generate_erd_full.py`.",
        "",
    ]
    for tname, cols in tables.items():
        schema = "history" if tname in HISTORY else "core"
        inv.append(f"## `{schema}.{tname}`")
        inv.append("")
        inv.append("| Column | Type | Keys |")
        inv.append("|--------|------|------|")
        for col, typ in cols:
            flags = []
            if col in pks.get(tname, set()):
                flags.append("PK")
            if (tname, col) in fk_col_set:
                flags.append("FK")
            inv.append(f"| `{col}` | `{typ}` | {', '.join(flags) or '—'} |")
        inv.append("")
    (DOCS_DB / "erd-columns.md").write_text("\n".join(inv), encoding="utf-8")


def write_explorer(erd: str) -> None:
    template = (ASSETS / "erd-explorer.html").read_text(encoding="utf-8")
    html = template
    html = html.replace(
        "WSDC warehouse ERD — interactive", "WSDC warehouse ERD — full columns"
    )
    html = html.replace(
        "<h1>WSDC warehouse ERD</h1>", "<h1>WSDC warehouse ERD (full columns)</h1>"
    )
    html = html.replace(
        "core + history · migrations 001–034 · pan / zoom like a model editor",
        "all columns · core + history · pan / zoom · use Fit",
    )
    html = html.replace('href="./wsdc_warehouse.dbml"', 'href="./wsdc_warehouse_full.mmd"')
    html = html.replace(">DBML</a>", ">MMD</a>")
    html = html.replace(
        "<strong>Hubs:</strong> dancers · events · locations<br />\n"
        "      Edition key: <code>(event_id, year, month)</code><br />\n"
        "      Soft links (no FK): calendar dates, schedule ↔ locations",
        "<strong>Full columns</strong> from migrations<br />\n"
        '      Compact: <a href="./erd-explorer.html">erd-explorer.html</a><br />\n'
        "      Soft links: calendar / schedule geo",
    )
    html2, n = re.subn(
        r"const ERD = `[\s\S]*?`\.trim\(\);",
        "const ERD = `\n" + erd.replace("`", "\\`") + "`.trim();",
        html,
        count=1,
    )
    if n != 1:
        raise SystemExit("Failed to inject ERD into erd-explorer.html template")
    (ASSETS / "erd-explorer-full.html").write_text(html2, encoding="utf-8")


def main() -> int:
    tables, pks, fks = parse_migrations()
    # Smoke: multi-ADD COLUMN ALTERs must not drop trailing columns.
    required = {
        "event_editions": {
            "start_date",
            "end_date",
            "date_source",
            "calendar_status",
            "event_occurred",
        },
        "parse_runs": {"max_dancer_id_watermark", "new_dancer_ids", "probe_details"},
        "scheduled_events": {"location_id", "location_source"},
        "events_list_current": {"location_id", "location_source"},
        "tier_definitions": {"finalist_max_place"},
    }
    missing: list[str] = []
    for tname, cols in required.items():
        have = {c for c, _ in tables.get(tname, [])}
        for col in sorted(cols - have):
            missing.append(f"{tname}.{col}")
    if missing:
        raise SystemExit("Missing expected columns from migrations: " + ", ".join(missing))

    erd, fk_col_set = build_erd(tables, pks, fks)
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "wsdc_warehouse_full.mmd").write_text(erd, encoding="utf-8")
    write_explorer(erd)
    write_inventory(tables, pks, fk_col_set)
    ncols = sum(len(c) for c in tables.values())
    print(f"tables={len(tables)} columns={ncols}")
    print("wrote docs/assets/wsdc_warehouse_full.mmd")
    print("wrote docs/assets/erd-explorer-full.html")
    print("wrote docs/database/erd-columns.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
