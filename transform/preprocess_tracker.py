"""Track normalization rules applied during preprocessing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AppliedRule:
    rule_id: str
    table: str
    column: str
    from_value: str
    to_value: str
    rows_affected: int
    source: str  # known_map | auto_pattern | location_id_fix | city_fix | substring

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreprocessTracker:
    rules: list[AppliedRule] = field(default_factory=list)

    def record(
        self,
        rule_id: str,
        table: str,
        column: str,
        from_value: str,
        to_value: str,
        rows_affected: int,
        source: str,
    ) -> None:
        if rows_affected <= 0:
            return
        self.rules.append(
            AppliedRule(
                rule_id=rule_id,
                table=table,
                column=column,
                from_value=str(from_value),
                to_value=str(to_value),
                rows_affected=int(rows_affected),
                source=source,
            )
        )

    def merge(self, other: PreprocessTracker) -> None:
        self.rules.extend(other.rules)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.rules]

    def total_rows_touched(self) -> int:
        return sum(r.rows_affected for r in self.rules)
