-- Competition Results must survive weekly promote_core TRUNCATE … CASCADE.
--
-- Incident 2026-10-26: after successful load_id=3 (cr_round_results≈512k),
-- promote_core truncated core.dancers / core.events (CASCADE). Postgres then
-- truncated every table with an FK *into* those relations — including
-- core.cr_round_results (dancer_id) and core.cr_editions (edition_id →
-- event_editions → events). core.cr_loads survived (nothing truncated it),
-- leaving audit rows with empty data tables.
--
-- Same class of bug as competitions/schedule calendar FKs (see promote_core.sql
-- and migrations 025/031). Soft references only; integrity stays in
-- transform/competition_results/conflicts.py + quality checks.

ALTER TABLE core.cr_round_results
    DROP CONSTRAINT IF EXISTS cr_round_results_dancer_id_fkey;

ALTER TABLE core.cr_round_results
    DROP CONSTRAINT IF EXISTS cr_round_results_partner_dancer_id_fkey;

ALTER TABLE core.cr_editions
    DROP CONSTRAINT IF EXISTS cr_editions_edition_id_fkey;

COMMENT ON COLUMN core.cr_round_results.dancer_id IS
    'Soft FK to core.dancers — no DB FK (promote_core TRUNCATE CASCADE).';

COMMENT ON COLUMN core.cr_round_results.partner_dancer_id IS
    'Soft FK to core.dancers — no DB FK (promote_core TRUNCATE CASCADE).';

COMMENT ON COLUMN core.cr_editions.edition_id IS
    'Soft FK to core.event_editions — no DB FK (promote_core TRUNCATE CASCADE). '
    'Nulled on promote; rematch via load_competition_results.py --apply.';
