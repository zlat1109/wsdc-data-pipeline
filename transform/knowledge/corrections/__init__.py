"""Load declarative correction YAML files from transform/knowledge/corrections/."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

CORRECTIONS_DIR = Path(__file__).resolve().parent


def iter_correction_files() -> list[Path]:
    return sorted(CORRECTIONS_DIR.glob("*.yaml")) + sorted(CORRECTIONS_DIR.glob("*.yml"))


def load_corrections() -> list[dict[str, Any]]:
    """Return parsed correction docs (requires PyYAML)."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load corrections; pip install pyyaml"
        ) from exc

    out: list[dict[str, Any]] = []
    for path in iter_correction_files():
        if path.name.lower() == "readme.md":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not doc:
            continue
        if not isinstance(doc, dict):
            raise ValueError(f"{path.name}: expected mapping at root")
        doc["_path"] = str(path.name)
        out.append(doc)
    return out


def active_corrections(*, kind: str | None = None) -> list[dict[str, Any]]:
    rows = load_corrections()
    active = [r for r in rows if str(r.get("status", "active")) == "active"]
    if kind:
        active = [r for r in active if r.get("kind") == kind]
    return active


def _parse_iso_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def stale_corrections(*, today: date | None = None) -> list[dict[str, Any]]:
    """Active corrections whose ``expires`` date is in the past."""
    today = today or date.today()
    stale: list[dict[str, Any]] = []
    for row in active_corrections():
        expires = _parse_iso_date(row.get("expires"))
        if expires is not None and expires < today:
            stale.append(row)
    return stale


def result_role_rule(correction_id: str) -> dict[str, Any] | None:
    """Return ``applies`` payload for an active result_role correction id."""
    for row in active_corrections(kind="result_role"):
        if row.get("id") == correction_id:
            applies = row.get("applies") or {}
            if not isinstance(applies, dict):
                raise ValueError(f"{correction_id}: applies must be a mapping")
            return {
                "id": correction_id,
                "event_id": applies.get("event_id"),
                "event_year": applies.get("event_year"),
                "event_name_substrings": tuple(
                    str(s).lower() for s in (applies.get("event_name_substrings") or ())
                ),
                "division_keys": frozenset(
                    str(s).lower() for s in (applies.get("division_keys") or ())
                ),
                "_path": row.get("_path"),
            }
    return None


def edition_date_repairs() -> dict[tuple[int, int, int], tuple[date, date]]:
    """Map (event_id, year, month) → (start, end) from active edition_date YAMLs."""
    out: dict[tuple[int, int, int], tuple[date, date]] = {}
    for row in active_corrections(kind="edition_date"):
        applies = row.get("applies") or {}
        repairs = applies.get("repairs") or []
        if not isinstance(repairs, list):
            raise ValueError(f"{row.get('id')}: applies.repairs must be a list")
        for item in repairs:
            if not isinstance(item, dict):
                continue
            eid = int(item["event_id"])
            year = int(item["event_year"])
            month = int(item["event_month"])
            start = _parse_iso_date(item.get("start"))
            end = _parse_iso_date(item.get("end"))
            if start is None or end is None:
                raise ValueError(
                    f"{row.get('id')}: repair {eid}/{year}-{month:02d} needs start+end"
                )
            out[(eid, year, month)] = (start, end)
    return out


def edition_date_repair_fills(
    *,
    scraped_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Payloads for ``upsert_edition_calendar_dates`` from YAML repairs."""
    from datetime import timezone

    now = scraped_at or datetime.now(timezone.utc)
    fills: list[dict[str, Any]] = []
    for (eid, year, month), (start, end) in sorted(edition_date_repairs().items()):
        fills.append(
            {
                "event_id": eid,
                "event_year": year,
                "event_month": month,
                "planned_start_date": start,
                "planned_end_date": end,
                "calendar_status": "scheduled",
                "date_source": "knowledge_correction",
                "source_fingerprint": f"corrections:edition_date:{eid}:{year}:{month}",
                "calendar_title": None,
                "url": None,
                "match_via": "knowledge_corrections_yaml",
                "scraped_at": now,
                "updated_at": now,
            }
        )
    return fills
