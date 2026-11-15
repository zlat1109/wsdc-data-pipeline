-- @docs-summary: export.cr_skill_entrants — largest-round L/F from CR for calendar fallback
-- Consumer waterfall: dump competitions_best exact → this CSV → tier ~ → unique scored.
-- Not a core truth table: read-only aggregate over matched core.cr_* only.

CREATE OR REPLACE VIEW export.cr_skill_entrants AS
WITH role_round_counts AS (
    SELECT
        e.edition_id,
        d.level,
        rr.role,
        r.round,
        count(*)::int AS n
    FROM core.cr_editions e
    JOIN core.cr_divisions d
      ON d.cr_edition_id = e.cr_edition_id
    JOIN core.cr_rounds r
      ON r.cr_division_id = d.cr_division_id
    JOIN core.cr_round_results rr
      ON rr.cr_round_id = r.cr_round_id
    WHERE e.match_status = 'matched'
      AND e.edition_id IS NOT NULL
      AND d.category = 'skill'
      AND d.level IN (
          'Newcomer',
          'Novice',
          'Intermediate',
          'Advanced',
          'All-Star',
          'Champion'
      )
      AND rr.role IN ('Leader', 'Follower')
    GROUP BY e.edition_id, d.level, rr.role, r.round
),
role_max AS (
    SELECT
        edition_id,
        level,
        role,
        max(n) AS entrants
    FROM role_round_counts
    GROUP BY edition_id, level, role
),
pivoted AS (
    SELECT
        edition_id,
        level,
        max(entrants) FILTER (WHERE role = 'Leader') AS leader_count,
        max(entrants) FILTER (WHERE role = 'Follower') AS follower_count
    FROM role_max
    GROUP BY edition_id, level
)
SELECT
    p.edition_id,
    ed.event_id,
    ed.event_year,
    ed.event_month,
    p.level,
    p.leader_count,
    p.follower_count
FROM pivoted p
JOIN core.event_editions ed ON ed.edition_id = p.edition_id;

COMMENT ON VIEW export.cr_skill_entrants IS
    'Matched CR skill JJ: largest-round Leader/Follower counts per edition×level. '
    'Used by L2/growth when dump competitions_best cannot form an exact headcount.';
