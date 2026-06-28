-- Record dancer display-name changes (staging vs core) before full core refresh.
-- Identity: dancer_id. Tracked attribute: dancer_name only (competitive history is separate).

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
close_old AS (
    UPDATE history.dancer_names_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_names_history (
    dancer_id, dancer_name, valid_from, valid_to, run_id
)
SELECT
    dancer_id, dancer_name, change_date, NULL, %(run_id)s
FROM changed;
