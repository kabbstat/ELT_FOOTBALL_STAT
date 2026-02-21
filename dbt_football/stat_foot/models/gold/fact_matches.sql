{{ config(
    materialized='table',
    schema='gold'
) }}

SELECT 
    -- Primary Key
    match_id,
    
    -- Dates
    match_utc_date AS match_datetime_utc,
    match_utc_date::DATE AS match_date,
    match_year,
    match_month,
    match_day_name AS match_day_of_week,
    
    -- Match Details
    league_code AS competition_code,
    league_name AS competition_name,
    match_day_number AS matchday,
    stage,
    match_group AS group_name,
    match_status AS status,
    
    -- Teams
    home_team_id,
    home_team_name,
    away_team_id,
    away_team_name,
    home_team_short_name,
    away_team_short_name,
    home_team_code,
    away_team_code,
    
    -- Scores
    full_time_home_score AS fulltime_home_score,
    full_time_away_score AS fulltime_away_score,
    half_time_home_score AS halftime_home_score,
    half_time_away_score AS halftime_away_score,
    total_goals,
    goal_difference,
    
    -- Outcomes
    winner_code AS winner,
    match_result AS match_outcome,
    home_win,
    away_win,
    is_draw,
    CASE WHEN total_goals >= 4 THEN TRUE ELSE FALSE END AS is_high_scoring,
    
    -- Season
    season_id,
    competition_id,
    
    -- Metadata
    source_last_updated_at AS last_updated_at,
    dbt_loaded_at AS loaded_at

FROM {{ ref('stg_matches') }}
WHERE match_status = 'FINISHED'
