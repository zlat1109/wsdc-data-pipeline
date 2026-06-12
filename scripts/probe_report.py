"""Build and serialize check-updates probe reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from event_coverage import EventCoverageResult
from wsdc_id_probe import ScanResult


@dataclass
class ProbeReport:
    ready: bool
    watermark: int
    live_max_id: int
    approx_new_ids: int
    new_ids_sample_count: int
    new_dancers_sample: list[dict[str, Any]] = field(default_factory=list)
    weekend_snapshot: str | None = None
    weekend_start: str | None = None
    weekend_end: str | None = None
    pending_events: list[str] = field(default_factory=list)
    matched_events: dict[str, str] = field(default_factory=dict)
    missing_events: list[str] = field(default_factory=list)
    already_in_db_events: list[str] = field(default_factory=list)
    coverage_dancers_scanned: int = 0
    no_pending: bool = False
    checked_at: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def changed(self) -> bool:
        return self.ready

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_probe_report(
    scan: ScanResult,
    coverage: EventCoverageResult | None,
    *,
    ready: bool,
    already_in_db: list[str] | None = None,
    no_pending: bool = False,
    snapshot_name: str | None = None,
    weekend_start: date | None = None,
    weekend_end: date | None = None,
) -> ProbeReport:
    return ProbeReport(
        ready=ready,
        watermark=scan.watermark,
        live_max_id=scan.live_max_id,
        approx_new_ids=max(scan.live_max_id - scan.watermark, 0),
        new_ids_sample_count=len(scan.new_ids),
        new_dancers_sample=scan.new_dancers[:10],
        weekend_snapshot=snapshot_name,
        weekend_start=weekend_start.isoformat() if weekend_start else None,
        weekend_end=weekend_end.isoformat() if weekend_end else None,
        pending_events=list(coverage.expected) if coverage else [],
        matched_events=dict(coverage.matched) if coverage else {},
        missing_events=list(coverage.missing) if coverage else [],
        already_in_db_events=list(already_in_db or []),
        coverage_dancers_scanned=coverage.dancers_scanned if coverage else 0,
        no_pending=no_pending,
    )
