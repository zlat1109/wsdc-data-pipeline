"""WSDC Points Registry tier rules — source of truth for Chart 5 / competitor ranges.

Numbers are transcribed from public WSDC PDF editions (see ``source`` fields) and
cross-checked against observed placement-point vectors in ``core.results``.

Load into Supabase with ``scripts/load_tier_rules.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

# ---------------------------------------------------------------------------
# Editions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RulesEdition:
    rules_version: str
    valid_from: date
    valid_to: date | None  # None = still current
    tier_basis: str  # none | smaller_role | per_role
    min_role_competitors: int
    points_depth: int  # how many placements get non-finalist points (typically 5)
    source_url: str
    source: str
    inherits_from: str | None = None  # chart inheritance target
    notes: str = ""


RULES_EDITIONS: tuple[RulesEdition, ...] = (
    RulesEdition(
        rules_version="2002",
        valid_from=date(2002, 1, 1),
        valid_to=date(2004, 1, 3),
        tier_basis="none",
        min_role_competitors=5,
        points_depth=5,
        source_url="https://wsdc-analytics.github.io/static/rules/WSDC-Points-Registry-2002.pdf",
        source="pdf_page:WSDC-Points-Registry-2002.pdf#1",
        notes="Flat scale; no tiers. Finalists (beyond top 5) receive 1 point.",
    ),
    RulesEdition(
        rules_version="2004",
        valid_from=date(2004, 1, 4),
        valid_to=date(2006, 12, 31),
        tier_basis="none",
        min_role_competitors=5,
        points_depth=5,
        source_url="https://wsdc-analytics.github.io/static/rules/WSDC-Points-Registry-2004.pdf",
        source="pdf_page:WSDC-Points-Registry-2004.pdf#1",
        inherits_from="2002",
        notes="Same placement points as 2002; clarified finals-only and <5 couples rules.",
    ),
    RulesEdition(
        rules_version="2007",
        valid_from=date(2007, 1, 1),
        valid_to=date(2008, 12, 31),
        tier_basis="smaller_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "WSDC%20Points%20Registry%20Document_2007.pdf"
        ),
        source="pdf_page:WSDC Points Registry Document_2007.pdf#1",
        notes="First Tier system (1-3); counted by couples = min(leaders, followers).",
    ),
    RulesEdition(
        rules_version="2009",
        valid_from=date(2009, 1, 1),
        valid_to=date(2010, 12, 31),
        tier_basis="smaller_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "WSDC%20Points%20Registry%20Document_2009.pdf"
        ),
        source="pdf_page:WSDC Points Registry Document_2009.pdf#1",
        notes="Tier 1 reduced; Tier 3 increased. Still couples / smaller-role basis.",
    ),
    RulesEdition(
        rules_version="2011",
        valid_from=date(2011, 1, 1),
        valid_to=date(2015, 6, 30),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "WSDC%20Points%20Registry%20Document_2011.pdf"
        ),
        source="pdf_page:WSDC Points Registry Document_2011.pdf#1",
        inherits_from="2009",
        notes="Same chart as 2009; Tier now computed separately per role.",
    ),
    RulesEdition(
        rules_version="2015",
        valid_from=date(2015, 7, 1),
        valid_to=date(2017, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2015-WSDC-Registry-Event-Rules-Combined.pdf"
        ),
        source="pdf_page:2015-WSDC-Registry-Event-Rules-Combined.pdf#1",
        inherits_from="2009",
        notes="Combined Event Rules + Points Registry; Chart unchanged from 2009/2011.",
    ),
    RulesEdition(
        rules_version="2018",
        valid_from=date(2018, 1, 1),
        valid_to=date(2018, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2018-WSDC-Registry-Event-Rules-Combined.pdf"
        ),
        source="pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1",
        notes="Expanded to six Tiers; rebuilt Points Award per Tier chart.",
    ),
    RulesEdition(
        rules_version="2019",
        valid_from=date(2019, 1, 1),
        valid_to=date(2019, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2019-WSDC-Registry-Event-Rules-Combined.pdf"
        ),
        source="pdf_page:2019-WSDC-Registry-Event-Rules-Combined.pdf#1",
        inherits_from="2018",
    ),
    RulesEdition(
        rules_version="2020",
        valid_from=date(2020, 1, 1),
        valid_to=date(2021, 4, 30),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2020-WSDC-Registry-Event-Rules-Combined.pdf"
        ),
        source="pdf_page:2020-WSDC-Registry-Event-Rules-Combined.pdf#1",
        inherits_from="2018",
    ),
    RulesEdition(
        rules_version="2021-addendum",
        valid_from=date(2021, 5, 1),
        valid_to=date(2022, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url="https://wsdc-analytics.github.io/static/rules/2020-May-Addendum.pdf",
        source="pdf_page:2020-May-Addendum.pdf#1",
        inherits_from="2018",
        notes="COVID addendum (May 2021); Chart 5 unchanged.",
    ),
    RulesEdition(
        rules_version="2023.1D",
        valid_from=date(2023, 1, 1),
        valid_to=date(2023, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2023-Registry-Event-Rules_vFinal3b-2023.1D.pdf"
        ),
        source="pdf_page:2023-Registry-Event-Rules_vFinal3b-2023.1D.pdf#1",
        inherits_from="2018",
        notes="Merged Points + Event Rules; Chart identical to 2018 (label Chart 4/5).",
    ),
    RulesEdition(
        rules_version="2024.2B",
        valid_from=date(2024, 1, 1),
        valid_to=date(2024, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "2024-Registry-Event-Rules_v2024.2B.pdf"
        ),
        source="pdf_page:2024-Registry-Event-Rules_v2024.2B.pdf#1",
        inherits_from="2018",
    ),
    RulesEdition(
        rules_version="2025.1A",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url="https://wsdc-analytics.github.io/static/rules/wsdcrules.pdf",
        source="pdf_page:wsdcrules.pdf#1",
        inherits_from="2018",
    ),
    RulesEdition(
        rules_version="2026",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        tier_basis="per_role",
        min_role_competitors=5,
        points_depth=5,
        source_url=(
            "https://wsdc-analytics.github.io/static/rules/"
            "WSDC-Registry-Event-Rules-Jan-17-2026.pdf"
        ),
        source="pdf_page:WSDC-Registry-Event-Rules-Jan-17-2026.pdf#17",
        inherits_from="2018",
        notes="Chart 5: Points Awarded per Tier (identical numbers to 2018).",
    ),
)


# ---------------------------------------------------------------------------
# Tier definitions (competitor ranges + prelim rounds + finalist points)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierDefinition:
    rules_version: str
    tier: int  # 0 = flat pre-tier scale
    min_competitors: int
    max_competitors: int | None  # None = open-ended upper tier
    prelim_rounds: int
    finalist_points: int
    source: str
    # Highest place that still receives finalist_points (None = all remaining finalists / N/A)
    finalist_max_place: int | None = None


# Explicit charts (not inherited). Tier 0 used for flat pre-2007 scale.
_TIER_DEFINITIONS_EXPLICIT: tuple[TierDefinition, ...] = (
    # 2002 / 2004 flat — finalists thru ~10th get 1 pt
    TierDefinition("2002", 0, 5, None, 1, 1, "pdf_page:WSDC-Points-Registry-2002.pdf#1", 10),
    # 2007
    TierDefinition("2007", 1, 5, 15, 1, 0, "pdf_page:WSDC Points Registry Document_2007.pdf#1", None),
    TierDefinition("2007", 2, 16, 39, 2, 1, "pdf_page:WSDC Points Registry Document_2007.pdf#1", 10),
    TierDefinition("2007", 3, 40, None, 3, 1, "pdf_page:WSDC Points Registry Document_2007.pdf#1", None),
    # 2009 (also inherited by 2011, 2015)
    TierDefinition("2009", 1, 5, 15, 1, 0, "pdf_page:WSDC Points Registry Document_2009.pdf#1", None),
    TierDefinition("2009", 2, 16, 39, 2, 1, "pdf_page:WSDC Points Registry Document_2009.pdf#1", 10),
    TierDefinition("2009", 3, 40, None, 3, 1, "pdf_page:WSDC Points Registry Document_2009.pdf#1", None),
    # 2018 six-tier chart (inherited by 2019+ for 1-5; finalist depth from Chart 5)
    TierDefinition("2018", 1, 5, 10, 1, 0, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", None),
    TierDefinition("2018", 2, 11, 19, 2, 0, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", None),
    TierDefinition("2018", 3, 20, 39, 2, 1, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", 12),
    TierDefinition("2018", 4, 40, 79, 3, 1, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", 15),
    TierDefinition("2018", 5, 80, 129, 3, 2, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", 15),
    TierDefinition("2018", 6, 130, None, 4, 2, "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", 15),
)


# ---------------------------------------------------------------------------
# Placement points (0 = additional finalist award; 1..5 = Chart 5 places)
# ---------------------------------------------------------------------------

PLACEMENT_FINALIST = 0


@dataclass(frozen=True)
class TierPoints:
    rules_version: str
    tier: int
    placement: int  # 0 = additional finalist; 1..5 = place
    points: int
    source: str


def _points_rows(
    version: str,
    tier: int,
    pts: tuple[int, int, int, int, int],
    source: str,
    *,
    finalist_points: int,
) -> tuple[TierPoints, ...]:
    rows = [
        TierPoints(version, tier, place, value, source)
        for place, value in enumerate(pts, start=1)
    ]
    rows.append(TierPoints(version, tier, PLACEMENT_FINALIST, finalist_points, source))
    return tuple(rows)


_TIER_POINTS_EXPLICIT: tuple[TierPoints, ...] = (
    *_points_rows("2002", 0, (10, 6, 4, 3, 2), "pdf_page:WSDC-Points-Registry-2002.pdf#1", finalist_points=1),
    *_points_rows(
        "2007", 1, (8, 6, 4, 2, 1), "pdf_page:WSDC Points Registry Document_2007.pdf#1", finalist_points=0
    ),
    *_points_rows(
        "2007", 2, (10, 8, 6, 4, 2), "pdf_page:WSDC Points Registry Document_2007.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2007", 3, (12, 10, 8, 6, 4), "pdf_page:WSDC Points Registry Document_2007.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2009", 1, (5, 4, 3, 2, 1), "pdf_page:WSDC Points Registry Document_2009.pdf#1", finalist_points=0
    ),
    *_points_rows(
        "2009", 2, (10, 8, 6, 4, 2), "pdf_page:WSDC Points Registry Document_2009.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2009", 3, (15, 12, 10, 8, 6), "pdf_page:WSDC Points Registry Document_2009.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2018", 1, (3, 2, 1, 0, 0), "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", finalist_points=0
    ),
    *_points_rows(
        "2018", 2, (6, 4, 3, 2, 1), "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", finalist_points=0
    ),
    *_points_rows(
        "2018", 3, (10, 8, 6, 4, 2), "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2018", 4, (15, 12, 10, 8, 6), "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1", finalist_points=1
    ),
    *_points_rows(
        "2018",
        5,
        (20, 16, 14, 12, 10),
        "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1",
        finalist_points=2,
    ),
    *_points_rows(
        "2018",
        6,
        (25, 22, 18, 15, 12),
        "pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1",
        finalist_points=2,
    ),
)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _edition_map() -> dict[str, RulesEdition]:
    return {e.rules_version: e for e in RULES_EDITIONS}


def resolve_chart_version(rules_version: str) -> str:
    """Follow inherits_from until an explicit chart owner is found."""
    editions = _edition_map()
    seen: set[str] = set()
    current = rules_version
    while True:
        if current in seen:
            raise ValueError(f"inherits_from cycle involving {rules_version!r}")
        seen.add(current)
        ed = editions.get(current)
        if ed is None:
            raise KeyError(f"Unknown rules_version: {rules_version!r}")
        if ed.inherits_from is None:
            return current
        current = ed.inherits_from


def expanded_tier_definitions() -> tuple[TierDefinition, ...]:
    """Return definitions for every rules_version (inheritance expanded)."""
    by_owner: dict[str, list[TierDefinition]] = {}
    for row in _TIER_DEFINITIONS_EXPLICIT:
        by_owner.setdefault(row.rules_version, []).append(row)

    out: list[TierDefinition] = []
    for ed in RULES_EDITIONS:
        owner = resolve_chart_version(ed.rules_version)
        for row in by_owner[owner]:
            out.append(
                TierDefinition(
                    rules_version=ed.rules_version,
                    tier=row.tier,
                    min_competitors=row.min_competitors,
                    max_competitors=row.max_competitors,
                    prelim_rounds=row.prelim_rounds,
                    finalist_points=row.finalist_points,
                    source=row.source if owner == ed.rules_version else f"inherits:{owner}",
                    finalist_max_place=row.finalist_max_place,
                )
            )
    return tuple(out)


def expanded_tier_points() -> tuple[TierPoints, ...]:
    by_owner: dict[str, list[TierPoints]] = {}
    for row in _TIER_POINTS_EXPLICIT:
        by_owner.setdefault(row.rules_version, []).append(row)

    out: list[TierPoints] = []
    for ed in RULES_EDITIONS:
        owner = resolve_chart_version(ed.rules_version)
        for row in by_owner[owner]:
            out.append(
                TierPoints(
                    rules_version=ed.rules_version,
                    tier=row.tier,
                    placement=row.placement,
                    points=row.points,
                    source=row.source if owner == ed.rules_version else f"inherits:{owner}",
                )
            )
    return tuple(out)


# Public aliases used by loader / tests / docs
TIER_DEFINITIONS: tuple[TierDefinition, ...] = expanded_tier_definitions()
TIER_POINTS: tuple[TierPoints, ...] = expanded_tier_points()


def edition_for_date(as_of: date) -> RulesEdition | None:
    for ed in RULES_EDITIONS:
        if ed.valid_from <= as_of and (ed.valid_to is None or as_of <= ed.valid_to):
            return ed
    return None


def chart_vectors(rules_version: str) -> dict[int, tuple[int, int, int, int, int]]:
    """Map tier → (p1, p2, p3, p4, p5) for a rules_version (excludes finalist row)."""
    pts = [
        p
        for p in TIER_POINTS
        if p.rules_version == rules_version and p.placement >= 1
    ]
    by_tier: dict[int, dict[int, int]] = {}
    for p in pts:
        by_tier.setdefault(p.tier, {})[p.placement] = p.points
    return {
        tier: (vals[1], vals[2], vals[3], vals[4], vals[5])
        for tier, vals in by_tier.items()
    }


def finalist_points_for(rules_version: str, tier: int) -> int:
    for p in TIER_POINTS:
        if (
            p.rules_version == rules_version
            and p.tier == tier
            and p.placement == PLACEMENT_FINALIST
        ):
            return p.points
    return 0



def iter_year_coverage(start_year: int = 2002, end_year: int = 2026) -> Iterable[tuple[int, str]]:
    """Yield (year, rules_version) for mid-year coverage checks."""
    for year in range(start_year, end_year + 1):
        ed = edition_for_date(date(year, 7, 1))
        if ed is None:
            raise ValueError(f"No rules edition covers {year}-07-01")
        yield year, ed.rules_version
