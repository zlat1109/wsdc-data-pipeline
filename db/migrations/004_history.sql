-- History: run journal + SCD2 change tracking.
-- Replaces the old workflow's changed_*.csv files: instead of appending
-- snapshot rows to ever-growing CSVs, only actual changes are stored,
-- each as a validity interval [valid_from, valid_to).

CREATE TABLE IF NOT EXISTS history.parse_runs (
    run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    source          text NOT NULL,  -- 'github-actions' | 'local' | 'backfill'
    probe_hash      text,           -- fingerprint used by the update checker
    rows_results    int,
    rows_points     int,
    points_changed  int,
    dancers_added   int,
    status          text NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'success', 'failed', 'skipped'))
);

-- Points change history. Identity: (dancer_id, role, dance, level).
-- Tracked attribute: total_points. valid_to IS NULL = current version.
CREATE TABLE IF NOT EXISTS history.dancer_points_history (
    dancer_id    int  NOT NULL,
    role         text NOT NULL,
    dance        text NOT NULL,
    level        text NOT NULL,
    total_points int  NOT NULL,
    valid_from   date NOT NULL,
    valid_to     date,
    run_id       bigint REFERENCES history.parse_runs,
    PRIMARY KEY (dancer_id, role, dance, level, valid_from)
);

CREATE INDEX IF NOT EXISTS dancer_points_history_current_idx
    ON history.dancer_points_history (dancer_id) WHERE valid_to IS NULL;

-- Role summary change history. Identity: dancer_id.
-- Tracked attributes: the full dancer_roles row.
CREATE TABLE IF NOT EXISTS history.dancer_roles_history (
    dancer_id                              int  NOT NULL,
    dancer_name                            text,
    dominate_role                          text,
    dominate_required                      text,
    dominate_allowed                       text,
    non_dominate_role                      text,
    non_dominate_required                  text,
    non_dominate_allowed                   text,
    non_dominate_recommended               text,
    non_dominate_role_highest_level_points text,
    non_dominate_role_highest_level        text,
    valid_from                             date NOT NULL,
    valid_to                               date,
    run_id                                 bigint REFERENCES history.parse_runs,
    PRIMARY KEY (dancer_id, valid_from)
);

CREATE INDEX IF NOT EXISTS dancer_roles_history_current_idx
    ON history.dancer_roles_history (dancer_id) WHERE valid_to IS NULL;
