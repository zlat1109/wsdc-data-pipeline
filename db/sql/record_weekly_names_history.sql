-- Record dancer display-name changes (staging vs core) before full core refresh.
-- Identity: dancer_id. Tracked attribute: dancer_name only (competitive history is separate).
--
-- Same-day re-entry: PK is (dancer_id, valid_from). Closing an open interval that
-- already starts on change_date and inserting again collides. Update in place;
-- only close older opens.

WITH staging_norm AS (
    SELECT
        s.dancer_id::int AS dancer_id,
        COALESCE(
            NULLIF(TRIM(s.dancer_name), ''),
            d.dancer_name
        ) AS dancer_name,
        COALESCE(NULLIF(TRIM(s.update_date), '')::date, CURRENT_DATE) AS change_date
    FROM staging.dancer_role_info s
    LEFT JOIN core.dancers d ON d.dancer_id = s.dancer_id::int
    WHERE s.dancer_id ~ '^\d+$'
),
staging_sig AS (
    SELECT
        *,
        md5(COALESCE(dancer_name, '')) AS sig
    FROM staging_norm
    WHERE dancer_name IS NOT NULL
),
current_names AS (
    SELECT
        d.dancer_id,
        md5(COALESCE(d.dancer_name, '')) AS sig
    FROM core.dancers d
    WHERE d.dancer_name IS NOT NULL
),
changed AS (
    SELECT sn.*
    FROM staging_sig sn
    LEFT JOIN current_names cn ON cn.dancer_id = sn.dancer_id
    WHERE cn.dancer_id IS NULL OR cn.sig IS DISTINCT FROM sn.sig
),
upd_same_day AS (
    UPDATE history.dancer_names_history h
    SET dancer_name = c.dancer_name,
        run_id = %(run_id)s
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
      AND h.valid_from = c.change_date
    RETURNING h.dancer_id
),
close_old AS (
    UPDATE history.dancer_names_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
      AND h.valid_from < c.change_date
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_names_history (
    dancer_id, dancer_name, valid_from, valid_to, run_id
)
SELECT
    c.dancer_id, c.dancer_name, c.change_date, NULL, %(run_id)s
FROM changed c
WHERE NOT EXISTS (
    SELECT 1 FROM upd_same_day u WHERE u.dancer_id = c.dancer_id
)
ON CONFLICT (dancer_id, valid_from) DO UPDATE
SET dancer_name = EXCLUDED.dancer_name,
    valid_to = NULL,
    run_id = EXCLUDED.run_id;
