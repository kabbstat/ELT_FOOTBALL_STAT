{{
    config(
        materialized='table'
    )
}}

WITH matches AS (
    SELECT * FROM {{ ref('stg_matches') }}
    WHERE is_finished = TRUE
),

team_matches AS (
    SELECT 
        home_team_id AS team_id,
        home_team_name AS team_name,
        league_code,
        match_utc_date,
        CASE WHEN home_win THEN 'W' WHEN is_draw THEN 'D' ELSE 'L' END AS result,
        CASE WHEN home_win THEN 3 WHEN is_draw THEN 1 ELSE 0 END AS points,
        ROW_NUMBER() OVER (PARTITION BY home_team_id, league_code ORDER BY match_utc_date DESC) AS rn
    FROM matches
    
    UNION ALL
    
    SELECT 
        away_team_id AS team_id,
        away_team_name AS team_name,
        league_code,
        match_utc_date,
        CASE WHEN away_win THEN 'W' WHEN is_draw THEN 'D' ELSE 'L' END AS result,
        CASE WHEN away_win THEN 3 WHEN is_draw THEN 1 ELSE 0 END AS points,
        ROW_NUMBER() OVER (PARTITION BY away_team_id, league_code ORDER BY match_utc_date DESC) AS rn
    FROM matches
),

last_5_matches AS (
    SELECT
        team_id,
        team_name,
        league_code,
        SUM(points) AS last_5_points,
        STRING_AGG(result, '' ORDER BY match_utc_date DESC) AS current_form
    FROM team_matches
    WHERE rn <= 5
    GROUP BY team_id, team_name, league_code
)

SELECT
    team_id,
    team_name,
    league_code,
    last_5_points,
    current_form,
    
    CASE 
        WHEN last_5_points >= 12 THEN '🔥 Hot'
        WHEN last_5_points >= 9 THEN '📈 Good'
        WHEN last_5_points >= 6 THEN '➡️ Stable'
        WHEN last_5_points >= 3 THEN '📉 Struggling'
        ELSE '❄️ Cold'
    END AS form_status,
    
    CURRENT_TIMESTAMP AS dbt_updated_at

FROM last_5_matches
ORDER BY league_code, last_5_points DESC