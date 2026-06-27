"""Build Tableau analytics CSVs from exported role history.

Ported from archive/legacy_notebooks/WSDC_Points_parser_API_optimized_local.ipynb:
- divisional_structure.csv (all roles; column type_options)
- divisional_structure_only_dominate_role.csv (dominate role only; column type)
- dancer_transitions.csv (weekly snapshot delta vs previous full parse)
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from transform.normalize import normalize_division, normalize_role

logger = logging.getLogger(__name__)

DIVISIONAL_STRUCTURE = "divisional_structure.csv"
DIVISIONAL_STRUCTURE_DOMINATE = "divisional_structure_only_dominate_role.csv"
DANCER_TRANSITIONS = "dancer_transitions.csv"

DERIVED_FILENAMES = (
    DIVISIONAL_STRUCTURE,
    DIVISIONAL_STRUCTURE_DOMINATE,
    DANCER_TRANSITIONS,
)

TRANSITION_COLUMNS = [
    "Update Date",
    "Previous Division",
    "Currently Division",
    "Transition Type",
    "Dancer Role",
    "Dancer ID",
    "Dancer Name",
]

TRANSITION_DEDUP_KEYS = [
    "Update Date",
    "Dancer ID",
    "Dancer Role",
    "Transition Type",
    "Previous Division",
    "Currently Division",
]

FULL_SNAPSHOT_MIN_COVERAGE = 0.5


def _required_or_allowed(source_column: str) -> str:
    return "required" if "required" in source_column else "allowed"


def _normalize_date_value(value: object) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _normalize_date_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    out[column] = out[column].map(_normalize_date_value)
    return out.dropna(subset=[column])


def _prepare_role_history(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared["dancer_id"] = pd.to_numeric(prepared["dancer_id"], errors="coerce")
    prepared = prepared.dropna(subset=["dancer_id"])
    prepared["dancer_id"] = prepared["dancer_id"].astype(int)
    if "update_date" not in prepared.columns:
        prepared["update_date"] = date.today().isoformat()
    prepared = _normalize_date_column(prepared, "update_date")
    prepared = prepared.sort_values(["dancer_id", "update_date"])
    return prepared.drop_duplicates(subset=["dancer_id", "update_date"], keep="last")


def load_role_source(output_dir: Path) -> pd.DataFrame:
    changed_path = output_dir / "changed_dancer_role_info.csv"
    current_path = output_dir / "dancer_role_info.csv"

    if changed_path.exists():
        changed = pd.read_csv(changed_path, low_memory=False)
        if "update_date" in changed.columns and changed["update_date"].notna().any():
            return _prepare_role_history(changed)

    if current_path.exists():
        current = pd.read_csv(current_path, low_memory=False)
        current["update_date"] = date.today().isoformat()
        return _prepare_role_history(current)

    raise FileNotFoundError(
        "Need changed_dancer_role_info.csv or dancer_role_info.csv in output directory"
    )


def _melt_role_block(
    df: pd.DataFrame,
    *,
    role_column: str,
    required_column: str,
    allowed_column: str,
    type_column: str,
) -> pd.DataFrame:
    subset = df[df[role_column].notna()].copy()
    if subset.empty:
        return pd.DataFrame()

    melted = pd.melt(
        subset,
        id_vars=["dancer_id", "update_date", role_column],
        value_vars=[required_column, allowed_column],
        var_name="_source_type",
        value_name="division",
    )
    melted[type_column] = melted["_source_type"].map(_required_or_allowed)
    melted = melted.drop(columns=["_source_type"])
    melted = melted.rename(columns={role_column: "role"})
    melted["role"] = melted["role"].map(normalize_role)
    melted["division"] = melted["division"].map(normalize_division)
    melted = melted[melted["division"].notna() & melted["update_date"].notna()]
    return melted[["dancer_id", "update_date", "division", "role", type_column]]


def build_divisional_structure(
    role_df: pd.DataFrame,
    *,
    dominate_only: bool = False,
) -> pd.DataFrame:
    if role_df.empty:
        return pd.DataFrame()

    type_column = "type" if dominate_only else "type_options"
    frames: list[pd.DataFrame] = []

    dominate = _melt_role_block(
        role_df,
        role_column="dominate_role",
        required_column="dominate_required",
        allowed_column="dominate_allowed",
        type_column=type_column,
    )
    if not dominate.empty:
        frames.append(dominate)

    if not dominate_only:
        non_dominate = _melt_role_block(
            role_df,
            role_column="non_dominate_role",
            required_column="non_dominate_required",
            allowed_column="non_dominate_allowed",
            type_column=type_column,
        )
        if not non_dominate.empty:
            frames.append(non_dominate)

    if not frames:
        return pd.DataFrame()

    melted = pd.concat(frames, ignore_index=True)
    aggregated = (
        melted.groupby(["update_date", "division", "role", type_column], dropna=False)
        .agg(count_dancer=("dancer_id", "count"))
        .reset_index()
    )
    return aggregated.sort_values(["update_date", "division", "role", type_column]).reset_index(
        drop=True
    )


def _align_type_column(existing: pd.DataFrame, type_column: str) -> pd.DataFrame:
    if type_column == "type_options" and "type" in existing.columns and "type_options" not in existing.columns:
        return existing.rename(columns={"type": "type_options"})
    if type_column == "type" and "type_options" in existing.columns and "type" not in existing.columns:
        return existing.rename(columns={"type_options": "type"})
    return existing


def _merge_snapshot_aggregates(
    existing_path: Path,
    new_df: pd.DataFrame,
    *,
    type_column: str,
) -> tuple[pd.DataFrame, int]:
    """Append snapshot rows with dates newer than baseline max (never backfill gaps)."""
    if new_df.empty:
        if existing_path.exists():
            return pd.read_csv(existing_path, low_memory=False), 0
        return new_df, 0

    new_df = _normalize_date_column(new_df.copy(), "update_date")

    if not existing_path.exists():
        return new_df, len(new_df)

    existing = _align_type_column(pd.read_csv(existing_path, low_memory=False), type_column)
    existing = _normalize_date_column(existing, "update_date")

    existing_dates = set(existing["update_date"].unique())
    append_df = new_df[~new_df["update_date"].isin(existing_dates)]
    if existing_dates:
        max_existing = max(existing_dates)
        append_df = append_df[append_df["update_date"] > max_existing]

    if append_df.empty:
        return existing.sort_values(
            ["update_date", "division", "role", type_column]
        ).reset_index(drop=True), 0

    combined = pd.concat([existing, append_df], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["update_date", "division", "role", type_column],
        keep="last",
    )
    combined = combined.sort_values(
        ["update_date", "division", "role", type_column]
    ).reset_index(drop=True)
    return combined, len(append_df)


def _previous_full_snapshot_frame(
    changed_df: pd.DataFrame,
    current_date: str,
    *,
    current_count: int,
) -> pd.DataFrame:
    """Previous global parse snapshot (legacy notebook: full backup CSV)."""
    changed = _prepare_role_history(changed_df)
    counts = changed.groupby("update_date").size()
    prior_dates = sorted(d for d in counts.index if d < current_date)
    if not prior_dates or not current_count:
        return pd.DataFrame()

    threshold = int(current_count * FULL_SNAPSHOT_MIN_COVERAGE)
    eligible = [(snapshot_date, int(counts[snapshot_date])) for snapshot_date in prior_dates if counts[snapshot_date] >= threshold]
    if not eligible:
        logger.warning(
            "No previous full snapshot before %s with >= %s rows; skipping transitions",
            current_date,
            threshold,
        )
        return pd.DataFrame()

    snapshot_date, snapshot_count = max(eligible, key=lambda item: item[1])
    snapshot = changed[changed["update_date"] == snapshot_date].copy()
    logger.info(
        "Using previous full snapshot %s (%s dancers, threshold %s)",
        snapshot_date,
        snapshot_count,
        threshold,
    )
    return snapshot


def build_dancer_transitions_snapshot(
    current_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    *,
    update_date: str,
) -> pd.DataFrame:
    """Compare two full role snapshots (legacy notebook / weekly parse delta)."""
    if current_df.empty or previous_df.empty:
        return pd.DataFrame(columns=TRANSITION_COLUMNS)

    current = current_df.copy()
    previous = previous_df.copy()
    current["dancer_id"] = pd.to_numeric(current["dancer_id"], errors="coerce")
    previous["dancer_id"] = pd.to_numeric(previous["dancer_id"], errors="coerce")

    merged = current.merge(previous, on="dancer_id", how="left", suffixes=("_curr", "_prev"))
    transitions: list[dict[str, object]] = []
    role_specs = (
        ("dominate", "dominate_role"),
        ("non_dominate", "non_dominate_role"),
    )

    for _, row in merged.iterrows():
        dancer_id = row.get("dancer_id")
        if pd.isna(dancer_id):
            continue

        dancer_id = int(dancer_id)
        dancer_name = row.get("dancer_name_curr") or row.get("dancer_name", "")

        for prefix, role_column in role_specs:
            role_value = row.get(f"{role_column}_curr")
            if pd.isna(role_value) or not str(role_value).strip():
                continue

            dancer_role = normalize_role(str(role_value).strip()) or str(role_value).strip()

            for field, label in (("required", "required"), ("allowed", "allowed")):
                prev_val = normalize_division(row.get(f"{prefix}_{field}_prev"))
                curr_val = normalize_division(row.get(f"{prefix}_{field}_curr"))

                if prev_val == curr_val or (prev_val is None and curr_val is None):
                    continue

                transitions.append(
                    {
                        "Update Date": update_date,
                        "Previous Division": prev_val or "—",
                        "Currently Division": curr_val or "—",
                        "Transition Type": label,
                        "Dancer Role": dancer_role,
                        "Dancer ID": dancer_id,
                        "Dancer Name": dancer_name,
                    }
                )

    if not transitions:
        return pd.DataFrame(columns=TRANSITION_COLUMNS)

    result = pd.DataFrame(transitions)
    return result.sort_values(
        ["Update Date", "Dancer ID", "Dancer Role", "Transition Type"]
    ).reset_index(drop=True)


def _merge_transitions(existing_path: Path, new_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if new_df.empty:
        if existing_path.exists():
            return pd.read_csv(existing_path, low_memory=False), 0
        return new_df, 0

    new_df = _normalize_date_column(new_df.copy(), "Update Date")

    if not existing_path.exists():
        return new_df, len(new_df)

    existing = pd.read_csv(existing_path, low_memory=False)
    if "Update Date" in existing.columns:
        existing = _normalize_date_column(existing, "Update Date")

    existing_dates = set(existing["Update Date"].unique())
    append_df = new_df[~new_df["Update Date"].isin(existing_dates)]
    if append_df.empty:
        return existing.sort_values(
            ["Update Date", "Dancer ID", "Dancer Role", "Transition Type"]
        ).reset_index(drop=True), 0

    combined = pd.concat([existing, append_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=TRANSITION_DEDUP_KEYS, keep="last")
    combined = combined.sort_values(
        ["Update Date", "Dancer ID", "Dancer Role", "Transition Type"]
    ).reset_index(drop=True)
    return combined, len(append_df)


def build_derived_analytics_exports(output_dir: Path) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    role_history = load_role_source(output_dir)

    divisional_new = build_divisional_structure(role_history, dominate_only=False)
    divisional_dominate_new = build_divisional_structure(role_history, dominate_only=True)

    divisional_path = output_dir / DIVISIONAL_STRUCTURE
    divisional_dominate_path = output_dir / DIVISIONAL_STRUCTURE_DOMINATE
    transitions_path = output_dir / DANCER_TRANSITIONS

    divisional_final, divisional_added = _merge_snapshot_aggregates(
        divisional_path,
        divisional_new,
        type_column="type_options",
    )
    divisional_dominate_final, dominate_added = _merge_snapshot_aggregates(
        divisional_dominate_path,
        divisional_dominate_new,
        type_column="type",
    )

    transitions_new = pd.DataFrame(columns=TRANSITION_COLUMNS)
    transitions_added = 0
    current_path = output_dir / "dancer_role_info.csv"
    changed_path = output_dir / "changed_dancer_role_info.csv"
    if current_path.exists() and changed_path.exists():
        current = pd.read_csv(current_path, low_memory=False)
        changed = pd.read_csv(changed_path, low_memory=False)
        current_dates = [
            d
            for d in (_normalize_date_value(v) for v in current.get("update_date", []))
            if d
        ]
        if current_dates:
            current_date = sorted(current_dates)[-1]
            existing_dates: set[str] = set()
            if transitions_path.exists():
                existing = pd.read_csv(transitions_path, low_memory=False)
                existing_dates = {
                    d
                    for d in (_normalize_date_value(v) for v in existing.get("Update Date", []))
                    if d
                }

            if current_date not in existing_dates:
                previous = _previous_full_snapshot_frame(
                    changed,
                    current_date,
                    current_count=len(current),
                )
                transitions_new = build_dancer_transitions_snapshot(
                    current,
                    previous,
                    update_date=current_date,
                )
            else:
                logger.info(
                    "Skipping dancer_transitions for %s (already in baseline)",
                    current_date,
                )

    transitions_final, transitions_added = _merge_transitions(transitions_path, transitions_new)

    exports = {
        DIVISIONAL_STRUCTURE: divisional_final,
        DIVISIONAL_STRUCTURE_DOMINATE: divisional_dominate_final,
        DANCER_TRANSITIONS: transitions_final,
    }

    logger.info(
        "Derived export append: divisional +%s, dominate +%s, transitions +%s",
        divisional_added,
        dominate_added,
        transitions_added,
    )

    counts: dict[str, int] = {}
    for filename, frame in exports.items():
        out_path = output_dir / filename
        frame.to_csv(out_path, index=False)
        counts[filename] = len(frame)
    return counts
