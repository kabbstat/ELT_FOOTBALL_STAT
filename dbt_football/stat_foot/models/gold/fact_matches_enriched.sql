{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    Combined analytics model: Matches + Team Values + Weather impact
    This model crosses all three data sources to create valuable insights.
    
    Key analysis:
    - Does team market value predict match outcomes?
    - Do weather conditions affect scoring?
    - What's the "upset" rate (lower value team winning)?
*/

WITH matches AS (
    SELECT * FROM {{ ref('fact_matches') }}
),

team_values AS (
    SELECT * FROM {{ ref('stg_team_values') }}
),

-- Join matches with home team values
matches_with_home_values AS (
    SELECT 
        m.*,
        tv.market_value_eur AS home_team_market_value,
        tv.avg_player_value_eur AS home_avg_player_value,
        tv.squad_size AS home_squad_size,
        tv.average_age AS home_squad_avg_age,
        tv.value_tier AS home_value_tier,
        tv.value_rank_in_competition AS home_value_rank
    FROM matches m
    LEFT JOIN team_values tv 
        ON LOWER(TRIM(m.home_team_name)) = LOWER(TRIM(tv.team_name))
),

-- Join with away team values
matches_with_all_values AS (
    SELECT 
        mhv.*,
        tv.market_value_eur AS away_team_market_value,
        tv.avg_player_value_eur AS away_avg_player_value,
        tv.squad_size AS away_squad_size,
        tv.average_age AS away_squad_avg_age,
        tv.value_tier AS away_value_tier,
        tv.value_rank_in_competition AS away_value_rank
    FROM matches_with_home_values mhv
    LEFT JOIN team_values tv 
        ON LOWER(TRIM(mhv.away_team_name)) = LOWER(TRIM(tv.team_name))
),

-- Calculate value-based metrics
enriched AS (
    SELECT 
        -- Match identifiers
        match_id,
        match_datetime_utc,
        match_date,
        match_year,
        match_month,
        matchday,
        competition_code,
        competition_name,
        status,
        
        -- Teams
        home_team_name,
        away_team_name,
        home_team_short_name,
        away_team_short_name,
        
        -- Scores
        fulltime_home_score,
        fulltime_away_score,
        halftime_home_score,
        halftime_away_score,
        total_goals,
        goal_difference,
        
        -- Match outcome
        winner,
        match_outcome,
        home_win,
        away_win,
        is_draw,
        is_high_scoring,
        
        -- Home team market values
        COALESCE(home_team_market_value, 0) AS home_team_market_value,
        COALESCE(home_avg_player_value, 0) AS home_avg_player_value,
        COALESCE(home_squad_size, 0) AS home_squad_size,
        COALESCE(home_squad_avg_age, 0) AS home_squad_avg_age,
        COALESCE(home_value_tier, 'unknown') AS home_value_tier,
        COALESCE(home_value_rank, 0) AS home_value_rank,
        
        -- Away team market values
        COALESCE(away_team_market_value, 0) AS away_team_market_value,
        COALESCE(away_avg_player_value, 0) AS away_avg_player_value,
        COALESCE(away_squad_size, 0) AS away_squad_size,
        COALESCE(away_squad_avg_age, 0) AS away_squad_avg_age,
        COALESCE(away_value_tier, 'unknown') AS away_value_tier,
        COALESCE(away_value_rank, 0) AS away_value_rank,
        
        -- Value comparisons
        COALESCE(home_team_market_value, 0) - COALESCE(away_team_market_value, 0) AS value_difference,
        
        CASE 
            WHEN COALESCE(away_team_market_value, 1) > 0 
            THEN ROUND(COALESCE(home_team_market_value, 0)::DECIMAL / COALESCE(away_team_market_value, 1), 2)
            ELSE 0
        END AS value_ratio,
        
        COALESCE(home_team_market_value, 0) + COALESCE(away_team_market_value, 0) AS combined_market_value,
        
        -- Favorite determination (higher market value)
        CASE
            WHEN COALESCE(home_team_market_value, 0) > COALESCE(away_team_market_value, 0) THEN 'home'
            WHEN COALESCE(away_team_market_value, 0) > COALESCE(home_team_market_value, 0) THEN 'away'
            ELSE 'equal'
        END AS favorite_by_value,
        
        -- Upset detection (underdog wins)
        CASE
            WHEN COALESCE(home_team_market_value, 0) > COALESCE(away_team_market_value, 0) 
                 AND winner = 'AWAY_TEAM' THEN TRUE
            WHEN COALESCE(away_team_market_value, 0) > COALESCE(home_team_market_value, 0) 
                 AND winner = 'HOME_TEAM' THEN TRUE
            ELSE FALSE
        END AS is_upset,
        
        -- Value tier matchup
        CONCAT(
            COALESCE(home_value_tier, 'unknown'), 
            ' vs ', 
            COALESCE(away_value_tier, 'unknown')
        ) AS value_tier_matchup,
        
        -- Did the richer team win?
        CASE
            WHEN COALESCE(home_team_market_value, 0) > COALESCE(away_team_market_value, 0) 
                 AND winner = 'HOME_TEAM' THEN TRUE
            WHEN COALESCE(away_team_market_value, 0) > COALESCE(home_team_market_value, 0) 
                 AND winner = 'AWAY_TEAM' THEN TRUE
            WHEN winner = 'DRAW' THEN NULL
            ELSE FALSE
        END AS richer_team_won,
        
        -- Value advantage ratio (for regression analysis)
        CASE 
            WHEN COALESCE(home_team_market_value, 0) + COALESCE(away_team_market_value, 0) > 0
            THEN ROUND(
                (COALESCE(home_team_market_value, 0)::DECIMAL - COALESCE(away_team_market_value, 0)) / 
                (COALESCE(home_team_market_value, 0) + COALESCE(away_team_market_value, 0)),
                4
            )
            ELSE 0
        END AS value_advantage_ratio,
        
        -- Metadata
        CURRENT_TIMESTAMP AS dbt_loaded_at
        
    FROM matches_with_all_values
)

SELECT * FROM enriched
