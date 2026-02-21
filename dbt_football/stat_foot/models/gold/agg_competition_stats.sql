{{ config(
    materialized='table',
    schema='gold'
) }}

SELECT 
    competition_code,
    competition_name,
    match_year,
    
    -- Match counts
    COUNT(DISTINCT match_id) AS total_matches,
    COUNT(DISTINCT home_team_id) + COUNT(DISTINCT away_team_id) AS total_teams,
    
    -- Goal statistics
    SUM(total_goals) AS total_goals,
    ROUND(AVG(total_goals), 2) AS avg_goals_per_match,
    MAX(total_goals) AS max_goals_in_match,
    MIN(total_goals) AS min_goals_in_match,
    
    -- Home advantage
    SUM(CASE WHEN winner = 'HOME_TEAM' THEN 1 ELSE 0 END) AS home_wins,
    SUM(CASE WHEN winner = 'AWAY_TEAM' THEN 1 ELSE 0 END) AS away_wins,
    SUM(CASE WHEN winner = 'DRAW' THEN 1 ELSE 0 END) AS draws,
    
    ROUND(100.0 * SUM(CASE WHEN winner = 'HOME_TEAM' THEN 1 ELSE 0 END) / COUNT(*), 1) AS home_win_percentage,
    ROUND(100.0 * SUM(CASE WHEN winner = 'AWAY_TEAM' THEN 1 ELSE 0 END) / COUNT(*), 1) AS away_win_percentage,
    ROUND(100.0 * SUM(CASE WHEN winner = 'DRAW' THEN 1 ELSE 0 END) / COUNT(*), 1) AS draw_percentage,
    
    -- High scoring matches
    SUM(CASE WHEN is_high_scoring THEN 1 ELSE 0 END) AS high_scoring_matches,
    ROUND(100.0 * SUM(CASE WHEN is_high_scoring THEN 1 ELSE 0 END) / COUNT(*), 1) AS high_scoring_percentage,
    
    CURRENT_TIMESTAMP AS calculated_at

FROM {{ ref('fact_matches') }}
GROUP BY competition_code, competition_name, match_year
ORDER BY match_year DESC, competition_code
