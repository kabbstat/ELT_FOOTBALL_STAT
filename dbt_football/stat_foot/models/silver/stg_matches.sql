{{ config(
    materialized='view',
    schema='silver'
) }}

WITH source_data AS (
    SELECT * FROM {{ source('bronze', 'matches') }}
    WHERE status IN ('FINISHED', 'IN_PLAY', 'PAUSED', 'SCHEDULED', 'TIMED')
), 
cleaned AS (
    SELECT 
    id AS match_id,
    competition_id,
    season_id,
    "homeTeam_id" AS home_team_id,
    "awayTeam_id" AS away_team_id,
    "utcDate"::TIMESTAMP AS match_utc_date,
    EXTRACT(YEAR FROM "utcDate"::TIMESTAMP) AS match_year,
    EXTRACT(MONTH FROM "utcDate"::TIMESTAMP) AS match_month,
    TO_CHAR("utcDate"::TIMESTAMP, 'Day') AS match_day_name,
    status AS match_status,
    matchday AS match_day_number,
    stage,
    COALESCE("group", 'N/A') AS match_group,
    "homeTeam_name" AS home_team_name,
    "homeTeam_shortName" AS home_team_short_name,
    "homeTeam_tla" AS home_team_code,
    "awayTeam_name" AS away_team_name,
    "awayTeam_shortName" AS away_team_short_name,
    "awayTeam_tla" AS away_team_code,
    "score_fullTime_home" AS full_time_home_score,
    "score_fullTime_away" AS full_time_away_score,
    "score_halfTime_home" AS half_time_home_score,
    "score_halfTime_away" AS half_time_away_score,

    CASE 
        WHEN score_winner = 'HOME_TEAM' THEN 'Home Win'
        WHEN score_winner = 'AWAY_TEAM' THEN 'Away Win'
        WHEN score_winner = 'DRAW' THEN 'Draw'
        ELSE 'Unknown'
    END AS match_result,
    score_winner AS winner_code,
    score_duration AS match_duration,
    competition_code AS league_code,
    competition_name AS league_name,

    ABS("score_fullTime_home" - "score_fullTime_away") AS goal_difference,
    "score_fullTime_home" + "score_fullTime_away" AS total_goals,


    CASE WHEN status = 'FINISHED' THEN TRUE ELSE FALSE END AS is_finished,
    CASE WHEN "score_fullTime_home" > "score_fullTime_away" THEN TRUE ELSE FALSE END AS home_win,
    CASE WHEN "score_fullTime_home" < "score_fullTime_away" THEN TRUE ELSE FALSE END AS away_win,
    CASE WHEN "score_fullTime_home" = "score_fullTime_away" THEN TRUE ELSE FALSE END AS is_draw,
    CURRENT_TIMESTAMP AS dbt_loaded_at,
    "lastUpdated"::TIMESTAMP AS source_last_updated_at
    FROM source_data
    WHERE id IS NOT NULL
    AND status IN ('FINISHED', 'IN_PLAY', 'SCHEDULED')

)
SELECT * FROM cleaned