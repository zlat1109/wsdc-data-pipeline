"""Preprocess WSDC CSVs with full audit log: before / applied / manual review."""

from __future__ import annotations

from typing import Any

import pandas as pd

from transform.data_preprocessing import (
    dedupe_result_rows,
    normalize_dates,
    normalize_results_dates,
    standardize_result,
)
from transform.geography import normalize_geography
from transform.geography.resolve import (
    consolidate_location_ids,
    dedupe_location_info,
    resolve_result_location_ids,
)
from transform.knowledge import (
    EVENT_LOCATION_EXACT_CORRECTIONS,
    EVENT_LOCATION_SUBSTRING_CORRECTIONS,
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    LOCATION_ID_MERGE_MAP,
    SINGAPORE_CANONICAL_LOCATION_ID,
    apply_event_location_patches,
    apply_event_name_year_splits,
    backfill_empty_result_event_locations,
    event_location_patches,
    force_result_locations_from_event_name_overrides,
)
from transform.knowledge.merge_map import apply_merge_event_id_map
from transform.normalize import normalize_division, normalize_level
from transform.preprocess_tracker import PreprocessTracker
from transform.quality_audit import (
    QualityFinding,
    mark_new_findings,
    run_audit,
    strip_event_year,
    YEAR_SUFFIX_RE,
)


def _apply_mapping(
    df: pd.DataFrame,
    column: str,
    mapping: dict[str, str],
    *,
    table: str,
    rule_id: str,
    tracker: PreprocessTracker,
    source: str = "known_map",
) -> pd.DataFrame:
    if column not in df.columns:
        return df
    series = df[column].astype(str).str.strip()
    for from_val, to_val in mapping.items():
        mask = series == from_val
        count = int(mask.sum())
        if count:
            tracker.record(rule_id, table, column, from_val, to_val, count, source)
            df.loc[mask, column] = to_val
    return df


def _apply_auto_strip_event_year(
    df: pd.DataFrame,
    column: str,
    *,
    table: str,
    tracker: PreprocessTracker,
) -> pd.DataFrame:
    """Strip trailing year from event name (known pattern; year lives in event_year column)."""
    if column not in df.columns:
        return df
    series = df[column].astype(str).str.strip()
    for raw in series.unique():
        if pd.isna(raw):
            continue
        raw = str(raw).strip()
        if not raw or raw == "nan":
            continue
        if raw in EVENT_NAME_NORMALIZATION:
            continue
        if not YEAR_SUFFIX_RE.search(raw):
            continue
        stripped = strip_event_year(raw)
        if stripped == raw:
            continue
        mask = series == raw
        count = int(mask.sum())
        tracker.record(
            "AUTO_STRIP_EVENT_YEAR",
            table,
            column,
            raw,
            stripped,
            count,
            "auto_pattern",
        )
        df.loc[mask, column] = stripped
    return df


def _apply_event_corrections_tracked(df: pd.DataFrame, tracker: PreprocessTracker) -> pd.DataFrame:
    table = "dancers_results_info"
    df = df.copy()

    df = _apply_auto_strip_event_year(df, "event_name", table=table, tracker=tracker)
    df = _apply_mapping(
        df,
        "event_name",
        EVENT_NAME_NORMALIZATION,
        table=table,
        rule_id="EVENT_NAME_NORMALIZATION",
        tracker=tracker,
    )
    before_year = df["event_name"].astype(str) if "event_name" in df.columns else None
    df = apply_event_name_year_splits(df)
    if before_year is not None and "event_name" in df.columns:
        changed = before_year != df["event_name"].astype(str)
        if changed.any():
            for from_val in before_year[changed].unique():
                to_val = df.loc[changed & (before_year == from_val), "event_name"].astype(str).iloc[0]
                count = int((changed & (before_year == from_val)).sum())
                tracker.record(
                    "EVENT_NAME_YEAR_SPLIT",
                    table,
                    "event_name",
                    str(from_val),
                    str(to_val),
                    count,
                    "known_map",
                )
    df = apply_merge_event_id_map(df, tracker=tracker)

    if "event_competition" in df.columns:
        original = df["event_competition"].astype(str)
        df["event_competition"] = df["event_competition"].apply(normalize_division)
        changed = original != df["event_competition"].astype(str)
        for from_val in original[changed].astype(str).unique():
            to_rows = df.loc[changed & (original.astype(str) == from_val), "event_competition"]
            if to_rows.empty:
                continue
            to_val = str(to_rows.iloc[0])
            count = int((changed & (original.astype(str) == from_val)).sum())
            tracker.record(
                "DIVISION_NORMALIZATION",
                table,
                "event_competition",
                from_val,
                to_val,
                count,
                "known_map",
            )

    if "event_name" in df.columns and "event_location" in df.columns:
        for name, location in EVENT_NAME_LOCATION_OVERRIDES.items():
            mask = df["event_name"].astype(str).str.strip() == name
            count = int(mask.sum())
            if count:
                tracker.record(
                    "EVENT_NAME_LOCATION_OVERRIDE",
                    table,
                    "event_location",
                    f"(when event_name={name})",
                    location,
                    count,
                    "known_map",
                )
                df.loc[mask, "event_location"] = location

    if "event_location" in df.columns:
        df = _apply_mapping(
            df,
            "event_location",
            EVENT_LOCATION_EXACT_CORRECTIONS,
            table=table,
            rule_id="EVENT_LOCATION_EXACT",
            tracker=tracker,
        )
        for old, new in EVENT_LOCATION_SUBSTRING_CORRECTIONS:
            col = df["event_location"].astype(str)
            mask = col.str.contains(old, regex=False, na=False)
            count = int(mask.sum())
            if count:
                tracker.record(
                    "EVENT_LOCATION_SUBSTRING",
                    table,
                    "event_location",
                    old,
                    new,
                    count,
                    "substring",
                )
                df.loc[mask, "event_location"] = col[mask].str.replace(old, new, regex=False)

    return normalize_results_dates(df)


def _apply_geography_tracked(df: pd.DataFrame, tracker: PreprocessTracker) -> pd.DataFrame:
    before = df.copy()
    out = normalize_geography(df.copy(), tracker=tracker)
    for idx in before.index:
        for col in ("event_location", "event_location_standardized"):
            if col not in before.columns or col not in out.columns:
                continue
            old = str(before.at[idx, col]).strip() if pd.notna(before.at[idx, col]) else ""
            new = str(out.at[idx, col]).strip() if pd.notna(out.at[idx, col]) else ""
            if old and new and old != new:
                tracker.location_string_replacements[old.upper()] = new
    return out


def _apply_events_wsdc_tracked(df: pd.DataFrame, tracker: PreprocessTracker) -> pd.DataFrame:
    table = "events_wsdc"
    df = df.copy()
    name_col = "name" if "name" in df.columns else "event_name"
    if name_col not in df.columns:
        return df
    df = _apply_auto_strip_event_year(df, name_col, table=table, tracker=tracker)
    df = _apply_mapping(
        df,
        name_col,
        EVENT_NAME_NORMALIZATION,
        table=table,
        rule_id="EVENT_NAME_NORMALIZATION",
        tracker=tracker,
    )
    before_year = df[name_col].astype(str)
    df = apply_event_name_year_splits(df)
    changed = before_year != df[name_col].astype(str)
    if changed.any():
        for from_val in before_year[changed].unique():
            to_val = df.loc[changed & (before_year == from_val), name_col].astype(str).iloc[0]
            count = int((changed & (before_year == from_val)).sum())
            tracker.record(
                "EVENT_NAME_YEAR_SPLIT",
                table,
                name_col,
                str(from_val),
                str(to_val),
                count,
                "known_map",
            )
    if "location" in df.columns:
        df = _apply_mapping(
            df,
            "location",
            EVENT_LOCATION_EXACT_CORRECTIONS,
            table=table,
            rule_id="EVENT_LOCATION_EXACT",
            tracker=tracker,
        )
    return normalize_dates(df)


def preprocess_with_log(data: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], PreprocessTracker]:
    """Apply notebook-style normalizations and record every rule hit."""
    tracker = PreprocessTracker()
    result: dict[str, pd.DataFrame] = {}

    if "location_info" in data:
        result["location_info"] = _apply_geography_tracked(data["location_info"], tracker)

    if "events_wsdc" in data:
        result["events_wsdc"] = _apply_events_wsdc_tracked(data["events_wsdc"], tracker)

    if "dancers_results_info" in data:
        df = data["dancers_results_info"].copy()
        if "event_result" in df.columns:
            df["event_result_standardized"] = df["event_result"].apply(standardize_result)
        result["dancers_results_info"] = _apply_event_corrections_tracked(df, tracker)

    if "location_info" in result and "dancers_results_info" in result:
        before = result["location_info"]
        patched = apply_event_location_patches(before, result["dancers_results_info"])
        for event_id, fixes in event_location_patches().items():
            for col, val in fixes.items():
                if col not in patched.columns or col not in before.columns:
                    continue
                changed = before[col].astype(str) != patched[col].astype(str)
                count = int(changed.sum())
                if count:
                    tracker.record(
                        "EVENT_LOCATION_BY_EVENT_ID",
                        "location_info",
                        col,
                        f"event_id={event_id}",
                        str(val),
                        count,
                        "event_id_fix",
                    )
        result["location_info"] = patched

        results_for_resolve = result["dancers_results_info"]
        before_loc_text_empty = (
            results_for_resolve["event_location"].map(lambda v: str(v).strip() == "").sum()
            if "event_location" in results_for_resolve.columns
            else len(results_for_resolve)
        )
        results_for_resolve = backfill_empty_result_event_locations(results_for_resolve)
        after_loc_text_empty = (
            results_for_resolve["event_location"].map(lambda v: str(v).strip() == "").sum()
            if "event_location" in results_for_resolve.columns
            else 0
        )
        loc_text_filled = int(before_loc_text_empty) - int(after_loc_text_empty)
        if loc_text_filled:
            tracker.record(
                "BACKFILL_EVENT_LOCATION",
                "dancers_results_info",
                "event_location",
                "(empty)",
                "from KNOWN_EVENT_METADATA",
                loc_text_filled,
                "event_id_fix",
            )
        result["dancers_results_info"] = results_for_resolve

        before_missing = (
            result["dancers_results_info"]["location_id"].map(
                lambda v: str(v).strip() == ""
            ).sum()
            if "location_id" in result["dancers_results_info"].columns
            else 0
        )
        resolved_results, resolved_locations = resolve_result_location_ids(
            result["dancers_results_info"], result["location_info"]
        )
        after_missing = (
            resolved_results["location_id"].map(lambda v: str(v).strip() == "").sum()
        )
        filled = int(before_missing) - int(after_missing)
        new_locations = len(resolved_locations) - len(result["location_info"])
        if filled:
            tracker.record(
                "RESOLVE_LOCATION_ID",
                "dancers_results_info",
                "location_id",
                "(empty)",
                f"from event_location ({new_locations} new locations)",
                filled,
                "location_id_fix",
            )
        # Force remap wrong shared location_ids (e.g. Sweden events → Wailea).
        resolved_results, forced = force_result_locations_from_event_name_overrides(
            resolved_results, resolved_locations
        )
        if forced:
            tracker.record(
                "EVENT_NAME_LOCATION_ID_FORCE",
                "dancers_results_info",
                "location_id",
                "wrong shared location_id",
                "from EVENT_NAME_LOCATION_OVERRIDES",
                forced,
                "location_id_fix",
            )
        before_merge = (
            resolved_results["location_id"].astype(str).str.strip().isin(
                set(LOCATION_ID_MERGE_MAP.keys())
            ).sum()
            if "location_id" in resolved_results.columns
            else 0
        )
        merged_results, merged_locations = consolidate_location_ids(
            resolved_results, resolved_locations
        )
        after_merge = (
            merged_results["location_id"].astype(str).str.strip().isin(
                set(LOCATION_ID_MERGE_MAP.keys())
            ).sum()
            if "location_id" in merged_results.columns
            else 0
        )
        merged_rows = int(before_merge) - int(after_merge)
        if merged_rows:
            tracker.record(
                "CONSOLIDATE_LOCATION_ID",
                "dancers_results_info",
                "location_id",
                "duplicate Singapore ids",
                f"→ {SINGAPORE_CANONICAL_LOCATION_ID}",
                merged_rows,
                "location_id_fix",
            )
        deduped_results, deduped_locations, loc_merged = dedupe_location_info(
            merged_results, merged_locations
        )
        if loc_merged:
            tracker.record(
                "DEDUPE_LOCATION_INFO",
                "location_info",
                "location_id",
                "duplicate canonical place",
                "lowest location_id per city",
                loc_merged,
                "location_id_fix",
            )
        result["dancers_results_info"] = deduped_results
        result["location_info"] = _apply_geography_tracked(deduped_locations, tracker)

    if "dancers_results_info" in result:
        deduped, dropped = dedupe_result_rows(result["dancers_results_info"])
        if dropped:
            tracker.record(
                "DEDUPE_RESULT_ROWS",
                "dancers_results_info",
                "*",
                "duplicate row",
                "keep first",
                dropped,
                "dedupe",
            )
        result["dancers_results_info"] = deduped

    if "dancer_role_info" in data:
        df = data["dancer_role_info"].copy()
        for col in [
            "dominate_required",
            "dominate_allowed",
            "non_dominate_required",
            "non_dominate_allowed",
        ]:
            if col in df.columns:
                original = df[col].copy()
                df[col] = df[col].apply(normalize_level)
                changed = original.astype(str) != df[col].astype(str)
                for from_val in original[changed].astype(str).unique():
                    to_rows = df.loc[changed & (original.astype(str) == from_val), col]
                    if to_rows.empty:
                        continue
                    to_val = str(to_rows.iloc[0])
                    count = int((changed & (original.astype(str) == from_val)).sum())
                    tracker.record(
                        "LEVEL_NORMALIZATION",
                        "dancer_role_info",
                        col,
                        from_val,
                        to_val,
                        count,
                        "known_map",
                    )
        result["dancer_role_info"] = df

    for key, df in data.items():
        if key not in result:
            result[key] = df.copy()

    return result, tracker


def build_combined_report(
    raw_data: dict[str, pd.DataFrame],
    processed_data: dict[str, pd.DataFrame],
    tracker: PreprocessTracker,
    *,
    previous_fingerprints: set[str] | None = None,
    previous_event_names: set[str] | None = None,
    source: str = "local",
    run_id: int | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    before_findings = run_audit(raw_data, previous_event_names=None)
    manual_findings = run_audit(processed_data, previous_event_names=previous_event_names)

    prev_fps = previous_fingerprints or set()
    mark_new_findings(manual_findings, prev_fps)

    applied = tracker.to_dict_list()
    manual_review = [f.to_dict() for f in manual_findings]
    for item in manual_review:
        item["requires_manual_review"] = True

    event_names: list[str] = []
    if "dancers_results_info" in processed_data:
        df = processed_data["dancers_results_info"]
        if "event_name" in df.columns:
            event_names = sorted(df["event_name"].dropna().astype(str).str.strip().unique().tolist())

    new_manual = sum(1 for f in manual_findings if f.is_new)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "run_id": run_id,
        "summary": {
            "before_findings_count": len(before_findings),
            "applied_rules_count": len(applied),
            "applied_rows_touched": tracker.total_rows_touched(),
            "manual_review_count": len(manual_review),
            "manual_review_new_count": new_manual,
        },
        "before_processing": {
            "description": "Issues detected in raw CSV before any normalization",
            "findings": [f.to_dict() for f in before_findings],
        },
        "applied_normalizations": {
            "description": "Known rules and auto-patterns applied (notebook maps + year strip)",
            "rules": applied,
        },
        "manual_review_required": {
            "description": "Remaining issues after processing — need human decision / new rules",
            "findings": manual_review,
        },
        "event_names_snapshot": event_names,
    }
