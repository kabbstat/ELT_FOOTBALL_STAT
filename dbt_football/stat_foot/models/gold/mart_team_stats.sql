{{
    config(
        materialized='table'
    )
}}

WITH matches AS (
    SELECT * FROM {{ ref('stg_matches') }}
    WHERE is_finished = TRUE
),

home_stats AS (
    SELECT
        home_team_id AS team_id,
        home_team_name AS team_name,
        league_code,
        
        COUNT(*) AS home_matches,
        SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS home_wins,
        SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) AS home_draws,
        SUM(CASE WHEN away_win THEN 1 ELSE 0 END) AS home_losses,
        
        SUM(full_time_home_score) AS home_goals_scored,
        SUM(full_time_away_score) AS home_goals_conceded,
        
        SUM(CASE WHEN home_win THEN 3 WHEN is_draw THEN 1 ELSE 0 END) AS home_points
    
    FROM matches
    GROUP BY home_team_id, home_team_name, league_code
),

away_stats AS (
    SELECT
        away_team_id AS team_id,
        away_team_name AS team_name,
        league_code,
        
        COUNT(*) AS away_matches,
        SUM(CASE WHEN away_win THEN 1 ELSE 0 END) AS away_wins,
        SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) AS away_draws,
        SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS away_losses,
        
        SUM(full_time_away_score) AS away_goals_scored,
        SUM(full_time_home_score) AS away_goals_conceded,
        
        SUM(CASE WHEN away_win THEN 3 WHEN is_draw THEN 1 ELSE 0 END) AS away_points
    
    FROM matches
    GROUP BY away_team_id, away_team_name, league_code
),

combined AS (
    SELECT
        COALESCE(h.team_id, a.team_id) AS team_id,
        COALESCE(h.team_name, a.team_name) AS team_name,
        COALESCE(h.league_code, a.league_code) AS league_code,
        
        -- Matches
        COALESCE(h.home_matches, 0) + COALESCE(a.away_matches, 0) AS total_matches,
        COALESCE(h.home_matches, 0) AS home_matches,
        COALESCE(a.away_matches, 0) AS away_matches,
        
        -- Wins
        COALESCE(h.home_wins, 0) + COALESCE(a.away_wins, 0) AS total_wins,
        COALESCE(h.home_wins, 0) AS home_wins,
        COALESCE(a.away_wins, 0) AS away_wins,
        
        -- Draws
        COALESCE(h.home_draws, 0) + COALESCE(a.away_draws, 0) AS total_draws,
        
        -- Losses
        COALESCE(h.home_losses, 0) + COALESCE(a.away_losses, 0) AS total_losses,
        
        -- Goals
        COALESCE(h.home_goals_scored, 0) + COALESCE(a.away_goals_scored, 0) AS total_goals_scored,
        COALESCE(h.home_goals_conceded, 0) + COALESCE(a.away_goals_conceded, 0) AS total_goals_conceded,
        
        -- Points
        COALESCE(h.home_points, 0) + COALESCE(a.away_points, 0) AS total_points
    
    FROM home_stats h
    FULL OUTER JOIN away_stats a 
        ON h.team_id = a.team_id 
        AND h.league_code = a.league_code
)

SELECT
    team_id,
    team_name,
    league_code,
    
    -- Match counts
    total_matches,
    home_matches,
    away_matches,
    
    -- Results
    total_wins,
    total_draws,
    total_losses,
    home_wins,
    away_wins,
    
    -- Goals
    total_goals_scored,
    total_goals_conceded,
    total_goals_scored - total_goals_conceded AS goal_difference,
    
    -- Points
    total_points,
    
    -- Calculated metrics
    ROUND(total_points::NUMERIC / NULLIF(total_matches, 0), 2) AS points_per_match,
    ROUND((total_wins::NUMERIC / NULLIF(total_matches, 0)) * 100, 1) AS win_rate,
    ROUND((total_goals_scored::NUMERIC / NULLIF(total_matches, 0)), 2) AS goals_scored_per_match,
    ROUND((total_goals_conceded::NUMERIC / NULLIF(total_matches, 0)), 2) AS goals_conceded_per_match,
    
    -- Form indicators
    CASE 
        WHEN total_points::NUMERIC / NULLIF(total_matches, 0) >= 2.5 THEN 'Excellent'
        WHEN total_points::NUMERIC / NULLIF(total_matches, 0) >= 2.0 THEN 'Good'
        WHEN total_points::NUMERIC / NULLIF(total_matches, 0) >= 1.5 THEN 'Average'
        WHEN total_points::NUMERIC / NULLIF(total_matches, 0) >= 1.0 THEN 'Below Average'
        ELSE 'Poor'
    END AS performance_rating,
    
    -- Metadata
    CURRENT_TIMESTAMP AS dbt_updated_at

FROM combined
ORDER BY league_code, total_points DESC, goal_difference DESC