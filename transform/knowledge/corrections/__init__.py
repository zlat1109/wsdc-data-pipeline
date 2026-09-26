"""Load declarative correction YAML files from transform/knowledge/corrections/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

CORRECTIONS_DIR = Path(__file__).resolve().parent


def iter_correction_files() -> list[Path]:
    return sorted(CORRECTIONS_DIR.glob("*.yaml")) + sorted(CORRECTIONS_DIR.glob("*.yml"))


def load_corrections() -> list[dict[str, Any]]:
    """Return parsed correction docs (requires PyYAML if available)."""
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
