-- Test: Ensure match dates are reasonable (not in future, not too old)

SELECT 
    match_id,
    match_date
FROM {{ ref('fact_matches') }}
WHERE match_date > CURRENT_DATE + INTERVAL '30 days'
   OR match_date < '2020-01-01'
