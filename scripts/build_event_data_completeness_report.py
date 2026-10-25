#!/usr/bin/env python3
"""Build the WSDC Event Data Registry: WSDC public results vs Competition Results.

Inputs stay local (Competition Results parquet, MySQL dump TSVs, Results Form
scoring CSV); only the rendered HTML is published, to the analytics site at
``internal/event-data-registry.html`` (unlisted, noindex).

    python scripts/build_event_data_completeness_report.py \\
        --cr-path ~/Downloads/"Competition Results"/results.parquet \\
        --site-repo ~/.cursor/wsdc-analytics-repo
"""

from __future__ import annotations

import argparse
import csv
import os
import html as H
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_ROOT))

from transform.competitions_from_dump import (  # noqa: E402
    DUMP_DIVISION_ID_TO_LEVEL,
    EditionKeyRow,
    build_ce_to_edition_id,
    parse_optional_int,
)
from transform.dump_edition_dates import (  # noqa: E402
    canonical_event_id,
    load_competitionevents_tsv,
    parse_date,
)
from transform.results_form_match import match_forms  # noqa: E402

OUT = PROJECT_ROOT / "data" / "quality_reports"
FORMS = OUT / "wsdc_results_form_scoring.csv"
COMP_TSV = PROJECT_ROOT / "dumps" / "competitions_wcs.tsv"
CE_TSV = PROJECT_ROOT / "dumps" / "competitionevents_dates.tsv"
EDITIONS_CSV = PROJECT_ROOT / "data" / "event_editions.csv"
SITE_PAGE = Path("internal") / "event-data-registry.html"

SKILL_DUMP = {"Newcomer", "Novice", "Intermediate", "Advanced", "All-Star", "Champion"}
SKILL_DUMP_IDS = {i for i, n in DUMP_DIVISION_ID_TO_LEVEL.items() if n in SKILL_DUMP}

MONTHS = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

KNOWN = {
    "scoringdance",
    "eepro",
    "danceconvention",
    "worlddanceregistry",
    "countrydancedirector",
    "stepright",
    "swingwars",
    "swingdirector",
    "danceplace",
    "paper",
    "callback",
    "eventmanagement",
    "immediatescoring",
    "net2order",
    "waviisoft",
    "swingchallenge",
    "swingdancer",
}
DISPLAY = {
    "scoringdance": "scoring.dance",
    "eepro": "EEPro",
    "danceconvention": "Dance Convention",
    "worlddanceregistry": "World Dance Registry",
    "countrydancedirector": "CountryDanceDirector",
    "stepright": "Step Right",
    "swingwars": "SwingWars",
    "swingdirector": "SwingDirector",
    "danceplace": "Dance Place",
    "net2order": "Net2Order",
    "swingdancer": "SwingDancer",
    "swingchallenge": "Swing Challenge",
    "waviisoft": "Waviisoft",
    "immediatescoring": "Immediate Scoring",
    "eventmanagement": "Event Management",
    "callback": "Callback",
    "paper": "Paper",
}

# Age / fun / non–skill-level labels for the "Other divs" tooltip.
# Prefer these over leftover raw strings when sorting the tip.
SIDE_LABEL_ORDER = [
    "Masters",
    "Sophisticated",
    "Strictly Newcomer",
    "Strictly Newcomer/Novice",
    "Strictly Novice",
    "Strictly Intermediate",
    "Strictly Advanced",
    "Strictly All-Stars",
    "Strictly Champions",
    "Strictly Masters",
    "Strictly Sophisticated",
    "Strictly Generational",
    "Strictly Open",
    "Strictly",
    "Switch J&J",
    "All American",
    "All European",
    "Rising Star",
    "Hi-Low J&J",
    "Crossover J&J",
    "Invitational J&J",
    "Pro-Am Strictly",
    "Pro-Am",
    "Routine/Showcase",
    "Solo",
]

_SIDE_ROUND_TAIL = re.compile(
    r"(?is)[\s\-_/|]*"
    r"(?:prelim(?:inary)?s?|semis?|finals?|finalists?|round\s*\d+|r\d+)\b.*$"
)
_SIDE_SKIP = {
    "wsdc_pointed_leveled",
    "wsdc_pointed_other",
    "wsdc_event_other",
    "non_wsdc_event",
    "jack & jill",
    "jack&jill",
    "j&j",
    "jack & jill wcs",
    "jack & jill wsdc",
}


def normalize_side_label(raw: str) -> str:
    """Collapse messy CR raw_division into a short age/fun label."""
    t = re.sub(r"\s+", " ", clean(raw))
    if not t:
        return ""
    core = _SIDE_ROUND_TAIL.sub("", t).strip(" -_/|")
    core = re.sub(
        r"(?i)\b(round\s*\d+|leaders?|followers?|follows?)\b", "", core
    )
    core = re.sub(r"\s+", " ", core).strip(" -_/|")
    cl = core.lower()
    if not cl or cl in _SIDE_SKIP:
        return ""

    if "all american" in cl or "all-american" in cl:
        return "All American"
    if "all european" in cl or "all-european" in cl:
        return "All European"
    if "rising star" in cl:
        return "Rising Star"
    if "switch" in cl:
        return "Switch J&J"
    if re.search(r"\bhi(gh)?[-/ ]?lo(w)?\b", cl):
        return "Hi-Low J&J"
    if "crossover" in cl:
        return "Crossover J&J"
    if "invitational" in cl and "jack" in cl:
        return "Invitational J&J"
    if "sophisticated" in cl and "strictly" not in cl:
        return "Sophisticated"
    if re.search(r"\bmasters?\b", cl) and "strictly" not in cl and "pro" not in cl:
        return "Masters"
    if "pro am" in cl or "pro-am" in cl or "proam" in cl:
        return "Pro-Am Strictly" if "strictly" in cl else "Pro-Am"
    if "strictly" in cl:
        for token, label in (
            ("new/nov", "Newcomer/Novice"),
            ("newcomer", "Newcomer"),
            ("novice", "Novice"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("all star", "All-Stars"),
            ("all-star", "All-Stars"),
            ("allstar", "All-Stars"),
            ("champion", "Champions"),
            ("masters", "Masters"),
            ("master", "Masters"),
            ("sophisticated", "Sophisticated"),
            ("generational", "Generational"),
            ("open", "Open"),
        ):
            if token in cl:
                return f"Strictly {label}"
        return "Strictly"
    if any(x in cl for x in ("routine", "showcase", "cabaret", "team")):
        return "Routine/Showcase"
    if "solo" in cl:
        return "Solo"
    # Drop pure skill-level / misbucketed WSDC JJ leftovers
    if re.search(
        r"(?i)\b(newcomer|novice|intermediate|advanced|all[-\s]?stars?|champions?)\b",
        cl,
    ) and re.search(r"(?i)jack|j&j|jill", cl):
        # Allow known fun JJ variants only (already handled above)
        if not any(
            x in cl
            for x in (
                "strictly",
                "switch",
                "american",
                "european",
                "rising",
                "hi-low",
                "crossover",
                "invitational",
                "masters",
                "sophisticated",
                "junior",
                "lindy",
                "rat race",
                "wild",
                "mixed",
                "take the lead",
            )
        ):
            return ""
    if cl in {
        "newcomer",
        "novice",
        "intermediate",
        "advanced",
        "all-star",
        "all-stars",
        "champion",
        "champions",
    }:
        return ""
    if cl.startswith("wsdc "):
        return ""
    # Avoid commas — tip list is joined with " · "
    return core.replace(",", " /")


def format_side_labels(raw_blob: str) -> str:
    """Normalize a |||-joined raw_division blob → sorted ' · ' list."""
    labels: set[str] = set()
    for part in str(raw_blob or "").split("|||"):
        lab = normalize_side_label(part)
        if lab:
            labels.add(lab)
    if not labels:
        return ""
    # Drop bare "Strictly" if we already have leveled Strictly *
    if "Strictly" in labels and any(
        x.startswith("Strictly ") for x in labels
    ):
        labels.discard("Strictly")
    ranked = [x for x in SIDE_LABEL_ORDER if x in labels]
    ranked.extend(sorted(labels - set(SIDE_LABEL_ORDER)))
    return " · ".join(ranked)


def clean(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"", "nan", "none", "null"} else s


def esc(x) -> str:
    s = clean(x)
    return "—" if not s else H.escape(s)


def fmt_num(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        return f"{int(x):,}"
    except Exception:
        return esc(x)


def _fmt_divs(items: set[str]) -> str:
    if not items:
        return "—"
    order = [
        "Newcomer",
        "Novice",
        "Intermediate",
        "Advanced",
        "All-Stars",
        "Champions",
    ]
    ranked = [d for d in order if d in items]
    ranked.extend(sorted(items - set(order)))
    return ", ".join(ranked)


def tip_for(
    label: str,
    state: str,
    have: set[str],
    universe: set[str],
    *,
    empty_msg: str,
) -> str:
    """Human tip: what is present / missing for this checklist cell."""
    if state == "full":
        return f"{label}: complete for all skill-level divisions ({_fmt_divs(universe) or 'all present'})."
    if state == "none":
        if universe:
            return f"{label}: none. Missing: {_fmt_divs(universe)}."
        return empty_msg
    # partial
    missing = universe - have
    parts = [f"{label}: partial."]
    if have:
        parts.append(f"Have: {_fmt_divs(have)}.")
    if missing:
        parts.append(f"Missing: {_fmt_divs(missing)}.")
    return " ".join(parts)


def check_html(state: str, tip: str) -> str:
    mark = "✓" if state != "none" else "–"
    # Custom hover tooltip (native title is easy to miss / delayed)
    return (
        f'<span class="tip-wrap chk-wrap">'
        f'<span class="chk {state}" tabindex="0">{mark}</span>'
        f'<span class="tip tip-hover" role="tooltip">{H.escape(tip)}</span>'
        f"</span>"
    )


def split_set(s) -> set[str]:
    if s is None or (isinstance(s, float) and pd.isna(s)) or not str(s).strip():
        return set()
    return {x for x in str(s).split("|") if x}


def completeness_score(row) -> int:
    """Higher = more complete checklist (full=2, partial=1, none=0)."""
    score = 0
    # Callbacks omitted: in CR they match Prelims for every edition (same skill-level coverage).
    for col in ("chk_prelims", "chk_judges", "chk_partners"):
        state = row.get(col) or "none"
        score += {"full": 2, "partial": 1, "none": 0}.get(state, 0)
    return score


def flags_for(row) -> dict[str, str]:
    universe = split_set(row.get("skill_divs"))
    prelim = split_set(row.get("prelim_divs"))
    judge = split_set(row.get("judge_divs"))
    finals = split_set(row.get("final_divs"))
    partner = split_set(row.get("partner_divs"))

    # Prelims: a skill division whose final was scraped but has no prelim round
    # is finals-only (field too small) — not a data gap. A division known only
    # from WSDC public results was not scraped at all — that is a real gap.
    scraped_finals = split_set(row.get("scraped_final_divs"))
    missing_prelim = universe - prelim
    finals_only_divs = missing_prelim & scraped_finals
    unexplained_prelim = missing_prelim - scraped_finals
    if not universe or not prelim:
        p_state = "none"
        tip_prelims = tip_for(
            "Prelims",
            "none",
            prelim,
            universe,
            empty_msg="Prelims: no skill-level prelim data.",
        )
    elif not unexplained_prelim:
        p_state = "full"
        if finals_only_divs:
            tip_prelims = (
                f"Prelims: complete. Have prelims: {_fmt_divs(prelim)}. "
                f"Finals-only (no prelim round — likely not held): "
                f"{_fmt_divs(finals_only_divs)}."
            )
        else:
            tip_prelims = tip_for(
                "Prelims",
                "full",
                prelim,
                universe,
                empty_msg="Prelims: no skill-level prelim data.",
            )
    else:
        p_state = "partial"
        tip_prelims = f"Prelims: partial. Have: {_fmt_divs(prelim)}."
        if finals_only_divs:
            tip_prelims += (
                f" Finals-only (likely not held): {_fmt_divs(finals_only_divs)}."
            )
        if unexplained_prelim:
            tip_prelims += (
                f" Not in scoring data (WSDC public final only): "
                f"{_fmt_divs(unexplained_prelim)}."
            )

    if not universe or not judge:
        j_state = "none"
    elif judge >= universe:
        j_state = "full"
    else:
        j_state = "partial"

    # Partners: "full" only with prelims (definitive who-danced-with-whom).
    # Without prelims, points can at best place top scorers — F-only finalists
    # cannot be paired — so never green; at most yellow (partial).
    has_prelims = bool(prelim)
    if not finals or not partner:
        part_state = "none"
        tip_partners = "Final partners: none — need prelims (or point placings) to pair leaders/followers."
    elif has_prelims and partner >= finals:
        part_state = "full"
        tip_partners = tip_for(
            "Final partners",
            "full",
            partner,
            finals,
            empty_msg="Final partners: no skill-level finals with partner links.",
        )
    elif has_prelims:
        part_state = "partial"
        tip_partners = tip_for(
            "Final partners",
            "partial",
            partner,
            finals,
            empty_msg="Final partners: no skill-level finals with partner links.",
        )
    else:
        # No prelims: points-inferred at best (top 3/5), not all finalists
        part_state = "partial"
        tip_partners = (
            "Final partners: partial — no prelims. "
            "Without round results, pairs can only be inferred for point placings "
            "(not F-only finalists). Have: "
            f"{_fmt_divs(partner) or 'some'}."
        )

    return {
        "chk_prelims": p_state,
        "chk_judges": j_state,
        "chk_partners": part_state,
        "tip_prelims": tip_prelims,
        "tip_judges": tip_for(
            "Judge marks",
            j_state,
            judge,
            universe,
            empty_msg="Judge marks: none for skill-level rounds.",
        ),
        "tip_partners": tip_partners,
    }


def cr_software_keys(sources_blob) -> list[str]:
    """Known scoring platforms listed in Competition Results ``source``."""
    return [
        p.strip().lower()
        for p in clean(sources_blob).split(",")
        if p.strip().lower() in KNOWN
    ]


def resolve_software(
    *,
    cr_known: list[str],
    form_sw: str = "",
) -> tuple[str, str, str]:
    """Decide display name / confidence / note for Scoring software.

    Priority:
    1. Scraped Competition Results ``source`` (platform prelims came from).
    2. Else Results Form for this edition.
    3. Else empty → UI shows ``No data — needs verification``.
    Form never overrides a CR scrape.
    """
    form_sw = (form_sw or "").strip().lower()
    if form_sw and form_sw not in KNOWN:
        form_sw = ""

    if cr_known:
        cr_disp = " / ".join(DISPLAY.get(p, p) for p in cr_known)
        return cr_disp, "confirmed", "Competition Results source"

    if form_sw:
        return DISPLAY.get(form_sw, form_sw), "confirmed", "Results Form"

    return "", "needs_verification", ""


def load_competitions(path: Path):
    rows = []
    with path.open(encoding="utf-8") as fh:
        for rec in csv.DictReader(fh, delimiter="\t"):
            rows.append(
                {
                    "competitionevent_id": int(rec["competitionevent_id"]),
                    "dancetype_id": int(rec["dancetype_id"]),
                    "division_id": int(rec["division_id"]),
                    "leader_count": parse_optional_int(rec.get("leader_count")),
                    "follower_count": parse_optional_int(rec.get("follower_count")),
                }
            )
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--cr-path",
        type=Path,
        default=os.environ.get("CR_RESULTS_PATH"),
        help="Competition Results results.parquet (env CR_RESULTS_PATH)",
    )
    parser.add_argument("--forms", type=Path, default=FORMS, help="Results Form scoring CSV")
    parser.add_argument("--competitions-tsv", type=Path, default=COMP_TSV)
    parser.add_argument("--competitionevents-tsv", type=Path, default=CE_TSV)
    parser.add_argument("--out-dir", type=Path, default=OUT, help="local CSV + HTML output")
    parser.add_argument(
        "--site-repo",
        type=Path,
        help=f"analytics site checkout; also writes <site-repo>/{SITE_PAGE}",
    )
    args = parser.parse_args(argv)
    if not args.cr_path:
        parser.error("--cr-path or CR_RESULTS_PATH is required")
    args.cr_path = Path(args.cr_path).expanduser()
    return args


def main(argv: list[str] | None = None) -> int:
    import duckdb  # local-only CR parquet reader; not a CI test dep

    args = parse_args(argv)
    cr_path = args.cr_path
    if not cr_path.exists():
        raise SystemExit(f"Missing Competition Results parquet: {cr_path}")
    for p in (args.forms, args.competitions_tsv, args.competitionevents_tsv):
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    print("Loading editions…")
    ed = pd.read_csv(EDITIONS_CSV, dtype=str)
    ed["edition_id"] = ed["edition_id"].astype(int)
    ed["event_id"] = ed["event_id"].astype(int)
    ed["event_year"] = ed["event_year"].astype(int)
    ed["event_month"] = ed["event_month"].astype(int)
    ed["unique_dancers"] = pd.to_numeric(ed["unique_dancers"], errors="coerce")

    print("CR aggregates…")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{cr_path}')")

    cr_ed = con.sql(
        """
WITH month_map AS (
  SELECT * FROM (VALUES
    ('January',1),('February',2),('March',3),('April',4),('May',5),('June',6),
    ('July',7),('August',8),('September',9),('October',10),('November',11),('December',12)
  ) AS t(mon_name, m)
),
base AS (
  SELECT
    event_edition_id,
    CAST(wsdc_event_id AS INT) AS raw_event_id,
    regexp_extract(event_edition_id, 'wsdc:\\d+:(\\w+) (\\d+)', 1) AS mon_name,
    CAST(regexp_extract(event_edition_id, 'wsdc:\\d+:(\\w+) (\\d+)', 2) AS INT) AS filing_year,
    MIN(event_edition_date) AS cr_start,
    ANY_VALUE(event_edition_name) AS cr_name,
    string_agg(DISTINCT NULLIF(source,''), ', ') AS sources,
    BOOL_OR(result_from_other_source) AS has_scrape
  FROM r
  WHERE starts_with(event_edition_id, 'wsdc:')
    AND wsdc_event_id IS NOT NULL AND wsdc_event_id <> ''
  GROUP BY 1,2,3,4
)
SELECT b.*, mm.m AS filing_month
FROM base b LEFT JOIN month_map mm USING (mon_name)
"""
    ).df()

    cr_ed["canonical_event_id"] = [
        canonical_event_id(int(a), str(b or ""))
        for a, b in zip(cr_ed.raw_event_id, cr_ed.cr_name)
    ]

    metrics = con.sql(
        """
WITH skill AS (
  SELECT *
  FROM r
  WHERE starts_with(event_edition_id, 'wsdc:')
    AND competition_bucket = 'wsdc_pointed_leveled'
    AND wsdc_division IN ('Newcomer','Novice','Intermediate','Advanced','All-Stars','Champions')
),
divs AS (
  SELECT event_edition_id, wsdc_division AS div FROM skill GROUP BY 1,2
),
prelim_divs AS (
  SELECT event_edition_id, wsdc_division AS div FROM skill WHERE round = 'prelim' GROUP BY 1,2
),
judge_divs AS (
  SELECT event_edition_id, wsdc_division AS div
  FROM skill
  WHERE judge_marks IS NOT NULL AND CAST(judge_marks AS VARCHAR) <> ''
  GROUP BY 1,2
),
final_divs AS (
  SELECT event_edition_id, wsdc_division AS div FROM skill WHERE round = 'final' GROUP BY 1,2
),
scraped_final_divs AS (
  SELECT event_edition_id, wsdc_division AS div
  FROM skill WHERE round = 'final' AND result_from_other_source GROUP BY 1,2
),
partner_divs AS (
  SELECT event_edition_id, wsdc_division AS div
  FROM skill
  WHERE round = 'final'
    AND partner_identity IS NOT NULL AND partner_identity <> '' AND partner_identity <> 'redacted'
  GROUP BY 1,2
),
first_round AS (
  SELECT event_edition_id, SUM(tc) AS first_round_size
  FROM (
    SELECT DISTINCT event_edition_id, wsdc_division, role, total_competitors AS tc
    FROM skill WHERE round = 'prelim' AND total_competitors IS NOT NULL
  ) t
  GROUP BY 1
),
scrape_finals AS (
  SELECT event_edition_id,
    COUNT(DISTINCT identity) FILTER (
      WHERE identity IS NOT NULL AND identity <> 'redacted' AND round = 'final'
    ) AS scrape_finals
  FROM skill GROUP BY 1
),
side AS (
  -- Age / fun / strictly etc. live mainly in raw_division (wsdc_division
  -- is only filled for Masters/Sophisticated). Normalize later in Python.
  SELECT event_edition_id,
    string_agg(DISTINCT raw_division, '|||' ORDER BY raw_division) AS side_raw
  FROM r
  WHERE starts_with(event_edition_id, 'wsdc:')
    AND result_from_other_source
    AND competition_bucket IN ('wsdc_pointed_other', 'wsdc_event_other')
    AND raw_division IS NOT NULL AND TRIM(raw_division) <> ''
  GROUP BY 1
)
SELECT
  d.event_edition_id,
  (SELECT string_agg(div, '|' ORDER BY div) FROM divs x WHERE x.event_edition_id = d.event_edition_id) AS skill_divs,
  (SELECT string_agg(div, '|' ORDER BY div) FROM prelim_divs x WHERE x.event_edition_id = d.event_edition_id) AS prelim_divs,
  (SELECT string_agg(div, '|' ORDER BY div) FROM judge_divs x WHERE x.event_edition_id = d.event_edition_id) AS judge_divs,
  (SELECT string_agg(div, '|' ORDER BY div) FROM final_divs x WHERE x.event_edition_id = d.event_edition_id) AS final_divs,
  (SELECT string_agg(div, '|' ORDER BY div) FROM scraped_final_divs x WHERE x.event_edition_id = d.event_edition_id) AS scraped_final_divs,
  (SELECT string_agg(div, '|' ORDER BY div) FROM partner_divs x WHERE x.event_edition_id = d.event_edition_id) AS partner_divs,
  fr.first_round_size,
  sf.scrape_finals,
  side.side_raw,
  BOOL_OR(s.round = 'prelim' AND s.result_from_other_source) AS has_any_prelim
FROM (SELECT DISTINCT event_edition_id FROM skill) d
LEFT JOIN first_round fr USING (event_edition_id)
LEFT JOIN scrape_finals sf USING (event_edition_id)
LEFT JOIN side USING (event_edition_id)
LEFT JOIN skill s ON s.event_edition_id = d.event_edition_id
GROUP BY 1, fr.first_round_size, sf.scrape_finals, side.side_raw
"""
    ).df()

    flag_rows = []
    for _, row in metrics.iterrows():
        f = flags_for(row)
        f["event_edition_id"] = row["event_edition_id"]
        f["first_round_size"] = row.get("first_round_size")
        f["scrape_finals"] = row.get("scrape_finals")
        f["side_divisions"] = format_side_labels(row.get("side_raw"))
        f["has_any_prelim"] = bool(row.get("has_any_prelim"))
        flag_rows.append(f)
    mf = pd.DataFrame(flag_rows)
    for tip_col in ("tip_prelims", "tip_judges", "tip_partners"):
        if tip_col not in mf.columns:
            mf[tip_col] = ""

    cr_full = cr_ed.merge(mf, on="event_edition_id", how="left")
    cr_full["has_any_prelim"] = cr_full["has_any_prelim"].fillna(False)
    cr_full = cr_full.sort_values(
        ["has_any_prelim", "first_round_size"], ascending=[False, False]
    )
    cr_best = cr_full.groupby(
        ["canonical_event_id", "filing_year", "filing_month"], as_index=False
    ).first()

    print("Matching editions…")
    comp = ed.merge(
        cr_best,
        how="left",
        left_on=["event_id", "event_year", "event_month"],
        right_on=["canonical_event_id", "filing_year", "filing_month"],
    )

    def row_status(r):
        if pd.isna(r.get("event_edition_id")):
            return "no_cr"
        if bool(r.get("has_any_prelim")):
            return "has_prelims"
        if bool(r.get("has_scrape")):
            return "scrape_no_prelim"
        return "wsdc_finals_only"

    comp["status"] = comp.apply(row_status, axis=1)
    for c in ["chk_prelims", "chk_judges", "chk_partners"]:
        comp[c] = comp[c].fillna("none")
    tip_defaults = {
        "tip_prelims": "Prelims: no skill-level prelim data.",
        "tip_judges": "Judge marks: none for skill-level rounds.",
        "tip_partners": "Final partners: no skill-level finals with partner links.",
    }
    for tip_col, default in tip_defaults.items():
        if tip_col not in comp.columns:
            comp[tip_col] = default
        else:
            comp[tip_col] = comp[tip_col].fillna(default)
    comp["completeness_score"] = comp.apply(completeness_score, axis=1)

    print("Dump entries…")
    dump_events = load_competitionevents_tsv(args.competitionevents_tsv)
    comps = load_competitions(args.competitions_tsv)
    editions_rows = []
    for r in ed.itertuples():
        editions_rows.append(
            EditionKeyRow(
                edition_id=int(r.edition_id),
                event_id=int(r.event_id),
                event_year=int(r.event_year),
                event_month=int(r.event_month),
                start_date=parse_date(r.start_date),
                end_date=parse_date(r.end_date),
                event_name=str(r.event_name or ""),
            )
        )
    ce_map = build_ce_to_edition_id(dump_events, editions_rows)
    dump_entries: dict[int, int] = {}
    for c in comps:
        if int(c["dancetype_id"]) != 1:
            continue
        if int(c["division_id"]) not in SKILL_DUMP_IDS:
            continue
        eid = ce_map.get(c["competitionevent_id"])
        if eid is None:
            continue
        lc = c["leader_count"] or 0
        fc = c["follower_count"] or 0
        dump_entries[eid] = dump_entries.get(eid, 0) + int(lc) + int(fc)

    comp["dump_entries"] = comp["edition_id"].map(dump_entries)
    comp["scored_finalists"] = comp["unique_dancers"]

    print("Software…")
    forms = pd.read_csv(args.forms, usecols=["form_year_folder", "event_name", "event_dates", "scoring_software"])
    cr_edition_names = dict(
        con.sql(
            """
SELECT event_edition_id, list(DISTINCT event_edition_name)
FROM r WHERE starts_with(event_edition_id, 'wsdc:') GROUP BY 1
"""
        ).fetchall()
    )
    extra_names = {
        int(e): cr_edition_names.get(c, [])
        for e, c in zip(comp["edition_id"], comp["event_edition_id"])
        if isinstance(c, str)
    }
    forms_m = match_forms(forms, ed, extra_names)
    forms_ok = forms_m[forms_m["m_ok"]].copy()
    forms_ok["edition_id"] = forms_ok["m_edition_id"].astype(int)
    forms_ok["sw"] = forms_ok["scoring_software"].map(clean)
    forms_ok = forms_ok[forms_ok["sw"].isin(KNOWN)]
    form_by_ed = forms_ok.groupby("edition_id").first()

    # Software priority: CR scrape → this edition's Form → needs verification.
    soft_name, soft_conf, soft_note = [], [], []
    for _, r in comp.iterrows():
        eid = int(r.edition_id)
        form_sw = ""
        if eid in form_by_ed.index:
            sw = clean(form_by_ed.loc[eid].get("sw"))
            if sw in KNOWN:
                form_sw = sw
        name, conf, note = resolve_software(
            cr_known=cr_software_keys(r.get("sources")),
            form_sw=form_sw,
        )
        soft_name.append(name)
        soft_conf.append(conf)
        soft_note.append(note)

    comp["soft_name"] = soft_name
    comp["soft_conf"] = soft_conf
    comp["soft_note"] = soft_note
    comp["is_dc"] = comp["sources"].fillna("").str.contains("danceconvention", case=False)

    summary = (
        comp.groupby("event_year")
        .agg(
            public_results=("edition_id", "count"),
            in_cr=("event_edition_id", lambda s: int(s.notna().sum())),
            with_prelims=("status", lambda s: int((s == "has_prelims").sum())),
            # Judges: any coverage (full or partial).
            with_judges=(
                "chk_judges",
                lambda s: int(s.isin(["full", "partial"]).sum()),
            ),
            # Other divs: age / fun / strictly present in Competition Results.
            with_other_divs=(
                "side_divisions",
                lambda s: int(s.fillna("").astype(str).str.strip().ne("").sum()),
            ),
            finals_only=("status", lambda s: int((s == "wsdc_finals_only").sum())),
            scrape_no_prelim=("status", lambda s: int((s == "scrape_no_prelim").sum())),
            form_software=("soft_conf", lambda s: int((s == "confirmed").sum())),
        )
        .reset_index()
        .rename(columns={"event_year": "year"})
    )
    n_pub = summary["public_results"].replace(0, pd.NA)
    summary["pct_prelims"] = (100.0 * summary["with_prelims"] / n_pub).round(1)
    summary["pct_judges"] = (100.0 * summary["with_judges"] / n_pub).round(1)
    summary["pct_other_divs"] = (100.0 * summary["with_other_divs"] / n_pub).round(1)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    comp.to_csv(out_dir / "event_data_completeness_by_event.csv", index=False)
    summary.to_csv(out_dir / "event_data_completeness_by_year.csv", index=False)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    years = sorted(comp.event_year.unique(), reverse=True)

    def soft_html(r) -> str:
        conf = r.soft_conf
        name = clean(r.soft_name)
        note = clean(r.soft_note)
        if conf == "needs_verification" or not name:
            return '<span class="soft needs">No data — needs verification</span>'
        if conf == "conflict":
            return (
                f'<span class="soft needs" title="{H.escape(note)}">'
                f"Needs verification: {H.escape(name)}</span>"
            )
        return (
            f'<span class="soft confirmed" title="{H.escape(note)}">'
            f"Confirmed: {H.escape(name)}</span>"
        )

    def side_html(r) -> str:
        side = clean(r.get("side_divisions"))
        if not side:
            return "—"
        items = [x.strip() for x in side.split(" · ") if x.strip()]
        if not items:
            return "—"
        tip = "Other divisions (age / fun / strictly): " + " · ".join(items)
        return (
            f'<span class="tip-wrap side-wrap">'
            f'<button type="button" class="side-btn" aria-expanded="false">yes</button>'
            f'<span class="tip tip-click" role="tooltip" hidden>{H.escape(tip)}</span>'
            f"</span>"
        )

    def dc_badge(r) -> str:
        if not bool(r.get("is_dc")):
            return ""
        return (
            ' <span class="badge dc" title="Dance Convention may redact '
            'competitor names">DC redact</span>'
        )

    def event_rows(sub) -> str:
        parts = []
        for _, r in sub.iterrows():
            mon = MONTHS[int(r.event_month)]
            parts.append(
                "<tr>"
                f"<td>{mon}</td>"
                f'<td class="num">{int(r.event_id)}</td>'
                f"<td>{esc(r.event_name)}{dc_badge(r)}</td>"
                f"<td>{esc(r.start_date)}</td>"
                f'<td class="num">{fmt_num(r.scored_finalists)}</td>'
                f'<td class="c">{check_html(r.chk_prelims, clean(r.tip_prelims))}</td>'
                f'<td class="c">{check_html(r.chk_judges, clean(r.tip_judges))}</td>'
                f'<td class="c">{check_html(r.chk_partners, clean(r.tip_partners))}</td>'
                f"<td>{side_html(r)}</td>"
                f"<td>{soft_html(r)}</td>"
                "</tr>"
            )
        return "\n".join(parts) or '<tr><td colspan="10">—</td></tr>'

    table_head = """<thead><tr>
              <th>Month</th><th>ID</th><th>Event</th><th>Start</th>
              <th class="num">Scored finalists</th>
              <th class="c">Prelims</th><th class="c">Judges</th>
              <th class="c">Partners</th>
              <th>Other divs</th><th>Software</th>
            </tr></thead>"""

    year_nav = " · ".join(f'<a href="#y{int(y)}">{int(y)}</a>' for y in years)
    year_sections = []
    for y in years:
        y = int(y)
        df = comp[comp.event_year == y]
        n = len(df)
        n_ok = int((df.status == "has_prelims").sum())
        pct = round(100 * n_ok / n, 1) if n else 0
        with_p = df[df.status == "has_prelims"].copy()
        with_p = with_p.sort_values(
            ["completeness_score", "event_month", "event_name"],
            ascending=[False, True, True],
        )
        without = df[df.status != "has_prelims"].sort_values(
            ["status", "event_month", "event_name"]
        )
        year_sections.append(
            f"""
    <section id="y{y}" class="year">
      <h2>{y} <span class="meta">{n_ok}/{n} with skill-level prelims ({pct}%)</span></h2>
      <div class="col">
        <h3 class="ok">With prelims — {len(with_p)}</h3>
        <p class="hint">Sorted by checklist completeness (full first).
        Hover a checklist mark for Have / Missing divisions.
        Click <em>yes</em> under Other divs for age / strictly / switch / fun.</p>
        <table>
          {table_head}
          <tbody>{event_rows(with_p)}</tbody>
        </table>
      </div>
      <details class="col no-prelims">
        <summary><h3 class="no">No prelims — {len(without)}</h3></summary>
        <table>
          {table_head}
          <tbody>{event_rows(without)}</tbody>
        </table>
      </details>
    </section>
"""
        )

    sum_rows = []
    for _, r in summary.sort_values("year", ascending=False).iterrows():
        yy = int(r.year)
        sum_rows.append(
            f'<tr><td><a href="#y{yy}">{yy}</a></td>'
            f'<td class="num">{int(r.public_results)}</td>'
            f'<td class="num ok">{int(r.with_prelims)}</td>'
            f'<td class="num">{r.pct_prelims}%</td>'
            f'<td class="num ok">{int(r.with_judges)}</td>'
            f'<td class="num">{r.pct_judges}%</td>'
            f'<td class="num ok">{int(r.with_other_divs)}</td>'
            f'<td class="num">{r.pct_other_divs}%</td>'
            f'<td class="num">{int(r.form_software)}</td></tr>'
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<title>WSDC Event Data Registry — Public results vs Competition Results</title>
<style>
:root {{
  --bg:#f7f6f3; --ink:#1a1a18; --muted:#5c5a55; --line:#e0ddd6;
  --ok:#1b6e3a; --ok-bg:#e7f5ec; --no:#8a3b2a;
  --partial:#8a6a1a; --partial-bg:#f7f1dd; --none:#9a9890; --link:#1a5f8a;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;
  background:var(--bg); color:var(--ink); line-height:1.45; }}
header {{ padding:1.5rem; border-bottom:1px solid var(--line); background:#fff; }}
header h1 {{ margin:0 0 .4rem; font-size:1.35rem; font-weight:650; }}
header p {{ margin:.3rem 0; color:var(--muted); max-width:74rem; font-size:.95rem; }}
.wrap {{ padding:1rem 1.5rem 3rem; max-width:1480px; margin:0 auto; }}
.legend {{ display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin:1rem 0 .25rem; }}
.nav {{ display:flex; flex-wrap:wrap; gap:.35rem .65rem; margin:.75rem 0 0; font-size:.9rem; }}
.nav a {{ color:var(--link); text-decoration:none; }}
table {{ width:100%; border-collapse:collapse; font-size:.78rem; background:#fff; border:1px solid var(--line); }}
th, td {{ padding:.28rem .4rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
th {{ background:#f0eee8; font-weight:600; position:sticky; top:0; z-index:1; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.c, th.c {{ text-align:center; }}
.chk {{ display:inline-flex; width:1.15rem; height:1.15rem; align-items:center; justify-content:center;
  border-radius:3px; font-weight:700; font-size:.75rem; cursor:help; }}
.chk.full {{ background:var(--ok-bg); color:var(--ok); }}
.chk.partial {{ background:var(--partial-bg); color:var(--partial); }}
.chk.none {{ background:#eceae4; color:var(--none); }}
.tip-wrap {{ position:relative; display:inline-block; }}
/* Fixed so tips are not clipped by .col overflow:auto */
.tip {{
  position:fixed; z-index:1000; display:none;
  min-width:12rem; max-width:28rem;
  padding:.45rem .55rem; border-radius:4px; border:1px solid var(--line);
  background:#1a1a18; color:#f7f6f3; font-size:.72rem; font-weight:500;
  line-height:1.35; text-align:left; white-space:normal;
  box-shadow:0 4px 14px rgba(0,0,0,.22); pointer-events:none;
}}
.tip.is-open {{ display:block; }}
.side-btn {{
  background:none; border:none; padding:0; margin:0; cursor:pointer;
  font:inherit; font-weight:600; color:var(--link);
  border-bottom:1px dotted var(--link);
}}
.side-btn:hover {{ color:var(--ink); }}
.tip-click[hidden] {{ display:none !important; }}
.soft {{ display:inline-block; font-size:.72rem; font-weight:600; padding:.1rem .35rem; border-radius:3px; }}
.soft.confirmed {{ background:var(--ok-bg); color:var(--ok); }}
.soft.likely {{ background:var(--partial-bg); color:var(--partial); }}
.soft.needs {{ background:#eceae4; color:var(--none); }}
.soft-note {{ font-size:.7rem; color:var(--muted); font-weight:500; }}
.badge.dc {{ display:inline-block; font-size:.65rem; padding:.05rem .3rem; border-radius:3px;
  background:#e8eef6; color:#2a4a6a; font-weight:600; margin-left:.25rem; }}
section.year {{ margin:2rem 0; padding-top:.5rem; border-top:2px solid var(--line); }}
section.year h2 {{ margin:0 0 .75rem; font-size:1.2rem; }}
section.year h2 .meta {{ color:var(--muted); font-weight:500; font-size:.95rem; margin-left:.4rem; }}
h3.ok {{ color:var(--ok); }} h3.no {{ color:var(--no); }}
.col {{ min-width:0; overflow:auto; max-height:75vh; border:1px solid var(--line);
  background:#fff; margin-bottom:1rem; }}
.col h3 {{ position:sticky; top:0; background:#fff; padding:.5rem .6rem; margin:0;
  border-bottom:1px solid var(--line); z-index:2; }}
details.no-prelims > summary {{ list-style:none; cursor:pointer; }}
details.no-prelims > summary::-webkit-details-marker {{ display:none; }}
details.no-prelims > summary h3::before {{ content:"▸ "; }}
details.no-prelims[open] > summary h3::before {{ content:"▾ "; }}
.hint {{ margin:0; padding:.35rem .6rem; font-size:.72rem; color:var(--muted);
  background:#faf9f6; border-bottom:1px solid var(--line); }}
.col table {{ border:none; }}
.summary table {{ max-width:72rem; }}
td.ok {{ color:var(--ok); font-weight:600; }}
</style>
</head>
<body>
<header>
  <h1>WSDC Event Data Registry — Public results vs Competition Results</h1>
  <p><strong>WSDC public results</strong> = finals and points as published by WSDC.
  <strong>Competition Results</strong> = extended round-level data (prelims, judges, final partners)
  from scoring platforms.
  Partners are <em>full</em> only when prelims exist (who danced with whom);
  without prelims, at most <em>partial</em> (point placings only).</p>
  <p><strong>Dance Convention:</strong> competitors may hide their names (redacted).
  Events sourced from DC are marked <span class="badge dc">DC redact</span> — prelim rows can look complete while some people are missing.</p>
  <p>  Checklist = <em>skill-level</em> Jack &amp; Jill only (Newcomer→Champions).
  Prelims: a division whose final was scraped but has no prelim round counts as
  finals-only (likely not held), not as missing data. A division known only from
  WSDC public results (not in scoring data) is a gap.
  Other divs (Masters, Sophisticated, Strictly, Switch, All American, …):
  click <em>yes</em> for the list from Competition Results.
  Generated {stamp}.</p>
  <p><strong>Software</strong> priority:
  <span class="soft confirmed">Confirmed</span> = Competition Results scrape source
  (platform prelims came from); if not scraped — this edition's Results Form;
  otherwise <span class="soft needs">No data — needs verification</span>.</p>
  <div class="legend">
    <span class="chk full">✓</span> Full
    <span class="chk partial">✓</span> Partial
    <span class="chk none">–</span> None
  </div>
  <nav class="nav">Years: {year_nav}</nav>
</header>
<div class="wrap">
  <section class="summary">
    <h2>Summary by year</h2>
    <table>
      <thead>
        <tr>
          <th>Year</th>
          <th class="num">WSDC public results</th>
          <th class="num">With prelims</th>
          <th class="num">%</th>
          <th class="num">With judges</th>
          <th class="num">%</th>
          <th class="num">With other divs</th>
          <th class="num">%</th>
          <th class="num">Software confirmed</th>
        </tr>
      </thead>
      <tbody>
        {"".join(sum_rows)}
      </tbody>
    </table>
  </section>
  {"".join(year_sections)}
</div>
<script>
(function () {{
  function placeTip(anchor, tip) {{
    var r = anchor.getBoundingClientRect();
    tip.style.left = "0px";
    tip.style.top = "0px";
    tip.classList.add("is-open");
    tip.hidden = false;
    var tw = tip.offsetWidth;
    var th = tip.offsetHeight;
    var left = r.left + r.width / 2 - tw / 2;
    var top = r.top - th - 8;
    if (top < 8) top = r.bottom + 8;
    if (left < 8) left = 8;
    if (left + tw > window.innerWidth - 8) left = window.innerWidth - tw - 8;
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }}
  function hideTip(tip) {{
    if (!tip) return;
    tip.classList.remove("is-open");
    tip.hidden = true;
  }}
  function closeSide(except) {{
    document.querySelectorAll(".side-wrap .tip-click").forEach(function (t) {{
      if (t !== except) {{
        hideTip(t);
        var b = t.parentElement && t.parentElement.querySelector(".side-btn");
        if (b) b.setAttribute("aria-expanded", "false");
      }}
    }});
  }}
  /* Checklist: hover / focus tooltip */
  document.querySelectorAll(".chk-wrap").forEach(function (wrap) {{
    var chk = wrap.querySelector(".chk");
    var tip = wrap.querySelector(".tip-hover");
    if (!chk || !tip) return;
    function show() {{ placeTip(chk, tip); }}
    function hide() {{ hideTip(tip); }}
    wrap.addEventListener("mouseenter", show);
    wrap.addEventListener("mouseleave", hide);
    chk.addEventListener("focus", show);
    chk.addEventListener("blur", hide);
  }});
  /* Side divs: click tooltip */
  document.addEventListener("click", function (e) {{
    var btn = e.target.closest(".side-btn");
    if (btn) {{
      e.preventDefault();
      e.stopPropagation();
      var tip = btn.parentElement.querySelector(".tip-click");
      var willOpen = tip.hidden || !tip.classList.contains("is-open");
      closeSide(tip);
      if (willOpen) {{
        placeTip(btn, tip);
        btn.setAttribute("aria-expanded", "true");
      }} else {{
        hideTip(tip);
        btn.setAttribute("aria-expanded", "false");
      }}
      return;
    }}
    if (!e.target.closest(".side-wrap")) closeSide(null);
  }});
  document.addEventListener("keydown", function (e) {{
    if (e.key === "Escape") closeSide(null);
  }});
  window.addEventListener("scroll", function () {{ closeSide(null); }}, true);
}})();
</script>
</body>
</html>
"""
    targets = [out_dir / "event_data_registry.html"]
    if args.site_repo:
        targets.append(args.site_repo.expanduser() / SITE_PAGE)
    for html_path in targets:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(doc, encoding="utf-8")
        print(f"Wrote {html_path} ({html_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
