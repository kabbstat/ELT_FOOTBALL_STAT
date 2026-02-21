-- Test: Ensure matches have valid scores
-- Scores should not be negative

SELECT 
    match_id,
    fulltime_home_score,
    fulltime_away_score
FROM {{ ref('fact_matches') }}
WHERE fulltime_home_score < 0 
   OR fulltime_away_score < 0
