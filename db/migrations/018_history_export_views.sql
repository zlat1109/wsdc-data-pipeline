-- History export views: drop-in replacement for the old workflow's changed_*.csv
-- files (same column contract) so existing Tableau Public workbooks keep working.
-- Source is the SCD2 history tables; each version row becomes one snapshot row
-- with update_date = valid_from (changes only, not every weekly snapshot).

-- changed_dancer_points_info.csv (6 columns, old-laptop order)
CREATE OR REPLACE VIEW export.changed_dancer_points_info AS
SELECT
    dancer_id,
    role,
    dance,
    level,
    total_points,
    valid_from AS update_date
FROM history.dancer_points_history
ORDER BY dancer_id, role, dance, level, valid_from;

-- changed_dancer_role_info.csv (12 columns, old-laptop order)
CREATE OR REPLACE VIEW export.changed_dancer_role_info AS
SELECT
    dancer_id,
    dancer_name,
    dominate_role,
    dominate_required,
    dominate_allowed,
    non_dominate_role,
    non_dominate_required,
    non_dominate_allowed,
    valid_from AS update_date,
    non_dominate_role_highest_level_points,
    non_dominate_role_highest_level,
    non_dominate_recommended
FROM history.dancer_roles_history
ORDER BY dancer_id, valid_from;
