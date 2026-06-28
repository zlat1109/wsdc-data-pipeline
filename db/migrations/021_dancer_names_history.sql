-- Identity history: display-name changes separate from competitive (points/divisions) history.

CREATE TABLE IF NOT EXISTS history.dancer_names_history (
    dancer_id    int  NOT NULL,
    dancer_name  text NOT NULL,
    valid_from   date NOT NULL,
    valid_to     date,
    run_id       bigint REFERENCES history.parse_runs,
    PRIMARY KEY (dancer_id, valid_from)
);

CREATE INDEX IF NOT EXISTS dancer_names_history_current_idx
    ON history.dancer_names_history (dancer_id) WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS dancer_names_history_run_id_idx
    ON history.dancer_names_history (run_id);

-- Manual alias map (maiden/married names, typos) — same pattern as core.event_aliases.
CREATE TABLE IF NOT EXISTS core.dancer_aliases (
    alias     text PRIMARY KEY,
    dancer_id int  NOT NULL REFERENCES core.dancers (dancer_id),
    source    text,
    notes     text
);

CREATE INDEX IF NOT EXISTS dancer_aliases_dancer_id_idx
    ON core.dancer_aliases (dancer_id);
