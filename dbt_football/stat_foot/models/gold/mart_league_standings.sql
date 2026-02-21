{{
    config(
        materialized='table'
    )
}}

WITH team_stats AS (
    SELECT * FROM {{ ref('mart_team_stats') }}
)

SELECT
    league_code,
    ROW_NUMBER() OVER (
        PARTITION BY league_code 
        ORDER BY total_points DESC, goal_difference DESC, total_goals_scored DESC
    ) AS team_rank,
    team_id,
    team_name,
    total_matches AS matches_played,
    total_wins AS wins,
    total_draws AS draws,
    total_losses AS losses,
    total_goals_scored AS goals_for,
    total_goals_conceded AS goals_against,
    goal_difference,
    total_points AS points,
    
    -- Championship indicators
    CASE 
        WHEN ROW_NUMBER() OVER (PARTITION BY league_code ORDER BY total_points DESC, goal_difference DESC) = 1 
        THEN '🏆 Leader'
        WHEN ROW_NUMBER() OVER (PARTITION BY league_code ORDER BY total_points DESC, goal_difference DESC) <= 4 
        THEN '⭐ Champions League'
        WHEN ROW_NUMBER() OVER (PARTITION BY league_code ORDER BY total_points DESC, goal_difference DESC) <= 6 
        THEN '🎯 Europa League'
        WHEN ROW_NUMBER() OVER (PARTITION BY league_code ORDER BY total_points DESC) >= 18 
        THEN '⚠️ Relegation Zone'
        ELSE '✅ Mid-table'
    END AS status,
    
    CURRENT_TIMESTAMP AS dbt_updated_at

FROM team_stats
ORDER BY league_code, team_rank