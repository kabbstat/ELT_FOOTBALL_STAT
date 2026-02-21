{{ config(
    materialized='table',
    schema='gold'
) }}

WITH home_stats AS (
    SELECT 
        home_team_id AS team_id,
        home_team_name AS team_name,
        competition_code,
        COUNT(*) AS matches_played_home,
        SUM(CASE WHEN winner = 'HOME_TEAM' THEN 1 ELSE 0 END) AS wins_home,
        SUM(CASE WHEN winner = 'DRAW' THEN 1 ELSE 0 END) AS draws_home,
        SUM(CASE WHEN winner = 'AWAY_TEAM' THEN 1 ELSE 0 END) AS losses_home,
        SUM(fulltime_home_score) AS goals_scored_home,
        SUM(fulltime_away_score) AS goals_conceded_home,
        SUM(CASE WHEN winner = 'HOME_TEAM' THEN 3 
                 WHEN winner = 'DRAW' THEN 1 
                 ELSE 0 END) AS points_home
    FROM {{ ref('fact_matches') }}
    GROUP BY home_team_id, home_team_name, competition_code
),

away_stats AS (
    SELECT 
        away_team_id AS team_id,
        away_team_name AS team_name,
        competition_code,
        COUNT(*) AS matches_played_away,
        SUM(CASE WHEN winner = 'AWAY_TEAM' THEN 1 ELSE 0 END) AS wins_away,
        SUM(CASE WHEN winner = 'DRAW' THEN 1 ELSE 0 END) AS draws_away,
        SUM(CASE WHEN winner = 'HOME_TEAM' THEN 1 ELSE 0 END) AS losses_away,
        SUM(fulltime_away_score) AS goals_scored_away,
        SUM(fulltime_home_score) AS goals_conceded_away,
        SUM(CASE WHEN winner = 'AWAY_TEAM' THEN 3 
                 WHEN winner = 'DRAW' THEN 1 
                 ELSE 0 END) AS points_away
    FROM {{ ref('fact_matches') }}
    GROUP BY away_team_id, away_team_name, competition_code
),

combined AS (
    SELECT 
        COALESCE(h.team_id, a.team_id) AS team_id,
        COALESCE(h.team_name, a.team_name) AS team_name,
        COALESCE(h.competition_code, a.competition_code) AS competition_code,
        
        -- Matches
        COALESCE(h.matches_played_home, 0) + COALESCE(a.matches_played_away, 0) AS total_matches,
        COALESCE(h.matches_played_home, 0) AS home_matches,
        COALESCE(a.matches_played_away, 0) AS away_matches,
        
        -- Wins
        COALESCE(h.wins_home, 0) + COALESCE(a.wins_away, 0) AS total_wins,
        COALESCE(h.wins_home, 0) AS home_wins,
        COALESCE(a.wins_away, 0) AS away_wins,
        
        -- Draws
        COALESCE(h.draws_home, 0) + COALESCE(a.draws_away, 0) AS total_draws,
        
        -- Losses
        COALESCE(h.losses_home, 0) + COALESCE(a.losses_away, 0) AS total_losses,
        
        -- Goals
        COALESCE(h.goals_scored_home, 0) + COALESCE(a.goals_scored_away, 0) AS total_goals_scored,
        COALESCE(h.goals_conceded_home, 0) + COALESCE(a.goals_conceded_away, 0) AS total_goals_conceded,
        
        -- Points
        COALESCE(h.points_home, 0) + COALESCE(a.points_away, 0) AS total_points
        
    FROM home_stats h
    FULL OUTER JOIN away_stats a 
        ON h.team_id = a.team_id 
        AND h.competition_code = a.competition_code
)

SELECT 
    *,
    -- Calculated metrics
    total_goals_scored - total_goals_conceded AS goal_difference,
    ROUND(CAST(total_goals_scored AS DECIMAL) / NULLIF(total_matches, 0), 2) AS avg_goals_scored_per_match,
    ROUND(CAST(total_goals_conceded AS DECIMAL) / NULLIF(total_matches, 0), 2) AS avg_goals_conceded_per_match,
    ROUND(CAST(total_points AS DECIMAL) / NULLIF(total_matches, 0), 2) AS points_per_match,
    ROUND(100.0 * total_wins / NULLIF(total_matches, 0), 1) AS win_percentage,
    
    CURRENT_TIMESTAMP AS calculated_at
    
FROM combined
ORDER BY competition_code, total_points DESC, goal_difference DESC
