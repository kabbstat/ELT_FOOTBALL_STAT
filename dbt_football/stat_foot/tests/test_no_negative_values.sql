-- Test: no negative market values
-- Market values should always be >= 0

SELECT *
FROM {{ ref('stg_team_values') }}
WHERE market_value_eur < 0
