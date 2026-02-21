{{
    config(
        materialized='table'
    )
}}

WITH matches AS (
    SELECT * FROM {{ ref('stg_matches') }}
    WHERE is_finished = TRUE
)

SELECT
    league_code,
    league_name,
    
    -- Match counts
    COUNT(*) AS total_matches,
    COUNT(DISTINCT home_team_id) + COUNT(DISTINCT away_team_id) AS total_teams,
    
    -- Goals
    SUM(total_goals) AS total_goals,
    ROUND(AVG(total_goals), 2) AS avg_goals_per_match,
    MAX(total_goals) AS max_goals_in_match,
    MIN(total_goals) AS min_goals_in_match,
    
    -- Results distribution
    SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS home_wins,
    SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) AS draws,
    SUM(CASE WHEN away_win THEN 1 ELSE 0 END) AS away_wins,
    
    -- Percentages
    ROUND((SUM(CASE WHEN home_win THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 1) AS home_win_pct,
    ROUND((SUM(CASE WHEN is_draw THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 1) AS draw_pct,
    ROUND((SUM(CASE WHEN away_win THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 1) AS away_win_pct,
    
    -- Goal statistics
    ROUND(AVG(full_time_home_score), 2) AS avg_home_goals,
    ROUND(AVG(full_time_away_score), 2) AS avg_away_goals,
    
    -- High-scoring matches
    SUM(CASE WHEN total_goals >= 4 THEN 1 ELSE 0 END) AS high_scoring_matches,
    SUM(CASE WHEN total_goals = 0 THEN 1 ELSE 0 END) AS goalless_draws,
    
    CURRENT_TIMESTAMP AS dbt_updated_at

FROM matches
GROUP BY league_code, league_name
ORDER BY total_matches DESC