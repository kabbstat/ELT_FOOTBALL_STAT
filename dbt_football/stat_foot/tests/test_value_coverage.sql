-- Test: value coverage
-- At least 80% of teams with matches should have market values assigned

WITH match_teams AS (
    SELECT DISTINCT home_team_name AS team_name FROM {{ ref('fact_matches_full') }}
    UNION
    SELECT DISTINCT away_team_name AS team_name FROM {{ ref('fact_matches_full') }}
),

stats AS (
    SELECT
        COUNT(*) AS total_teams,
        SUM(CASE WHEN tv.team_name IS NOT NULL THEN 1 ELSE 0 END) AS with_values
    FROM match_teams mt
    LEFT JOIN {{ ref('stg_team_values') }} tv
        ON LOWER(TRIM(mt.team_name)) = LOWER(TRIM(tv.team_name))
)

SELECT *
FROM stats
WHERE total_teams > 0
  AND (with_values::DECIMAL / total_teams) < 0.80
