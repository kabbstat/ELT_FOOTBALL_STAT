-- Test: Ensure halftime scores are not greater than fulltime scores

SELECT 
    match_id,
    halftime_home_score,
    fulltime_home_score,
    halftime_away_score,
    fulltime_away_score
FROM {{ ref('fact_matches') }}
WHERE halftime_home_score > fulltime_home_score
   OR halftime_away_score > fulltime_away_score
