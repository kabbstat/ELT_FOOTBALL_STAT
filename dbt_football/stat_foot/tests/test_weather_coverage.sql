-- Test: weather coverage
-- At least 50% of finished matches should have weather data
-- (relaxed threshold since weather data may not be available for all cities)

WITH stats AS (
    SELECT
        COUNT(*) AS total_matches,
        SUM(CASE WHEN temperature_celsius IS NOT NULL THEN 1 ELSE 0 END) AS with_weather
    FROM {{ ref('fact_matches_full') }}
    WHERE status = 'FINISHED'
)

SELECT *
FROM stats
WHERE total_matches > 0
  AND (with_weather::DECIMAL / total_matches) < 0.50
