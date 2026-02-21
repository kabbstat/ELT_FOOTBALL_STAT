{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    Fully enriched fact table: Matches + Team Values + Match Weather
    ================================================================
    Joins all 3 data sources. Unlike fact_matches_enriched (values-only),
    this includes weather conditions at match time.

    Key analyses enabled:
    - Weather impact on scoring
    - Market value vs performance with weather context
    - Home advantage under adverse conditions
*/

WITH matches AS (
    SELECT * FROM {{ ref('fact_matches') }}
),

team_values AS (
    SELECT * FROM {{ ref('stg_team_values') }}
),

weather AS (
    SELECT * FROM {{ ref('stg_weather') }}
),

-- Join home team values
with_home_values AS (
    SELECT
        m.*,
        tv.market_value_eur    AS home_market_value,
        tv.avg_player_value_eur AS home_avg_player_value,
        tv.squad_size          AS home_squad_size,
        tv.average_age         AS home_avg_age,
        tv.value_tier          AS home_value_tier,
        tv.value_rank_in_competition AS home_value_rank
    FROM matches m
    LEFT JOIN team_values tv
        ON LOWER(TRIM(m.home_team_name)) = LOWER(TRIM(tv.team_name))
),

-- Join away team values
with_all_values AS (
    SELECT
        hv.*,
        tv.market_value_eur    AS away_market_value,
        tv.avg_player_value_eur AS away_avg_player_value,
        tv.squad_size          AS away_squad_size,
        tv.average_age         AS away_avg_age,
        tv.value_tier          AS away_value_tier,
        tv.value_rank_in_competition AS away_value_rank
    FROM with_home_values hv
    LEFT JOIN team_values tv
        ON LOWER(TRIM(hv.away_team_name)) = LOWER(TRIM(tv.team_name))
),

-- Join weather (city-level, best available)
with_weather AS (
    SELECT
        v.*,
        w.temperature_celsius,
        w.feels_like_celsius,
        w.humidity_percent,
        w.pressure_hpa,
        w.weather_condition,
        w.weather_description,
        w.wind_speed_ms,
        w.wind_direction_deg,
        w.cloud_coverage_percent,
        w.rain_last_hour_mm,
        w.snow_last_hour_mm,
        w.visibility_meters,
        w.is_rainy,
        w.is_cold,
        w.is_hot,
        w.is_windy,
        w.weather_category
    FROM with_all_values v
    LEFT JOIN weather w
        ON LOWER(TRIM(w.city)) = LOWER(TRIM(
            CASE
                -- Map team to city for join
                WHEN v.home_team_name ILIKE '%Arsenal%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Chelsea%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Tottenham%' THEN 'London'
                WHEN v.home_team_name ILIKE '%West Ham%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Crystal Palace%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Fulham%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Brentford%' THEN 'London'
                WHEN v.home_team_name ILIKE '%Manchester City%' THEN 'Manchester'
                WHEN v.home_team_name ILIKE '%Manchester United%' THEN 'Manchester'
                WHEN v.home_team_name ILIKE '%Liverpool%' THEN 'Liverpool'
                WHEN v.home_team_name ILIKE '%Everton%' THEN 'Liverpool'
                WHEN v.home_team_name ILIKE '%Newcastle%' THEN 'Newcastle'
                WHEN v.home_team_name ILIKE '%Aston Villa%' THEN 'Birmingham'
                WHEN v.home_team_name ILIKE '%Brighton%' THEN 'Brighton'
                WHEN v.home_team_name ILIKE '%Nottingham%' THEN 'Nottingham'
                WHEN v.home_team_name ILIKE '%Wolverhampton%' THEN 'Wolverhampton'
                WHEN v.home_team_name ILIKE '%Bournemouth%' THEN 'Bournemouth'
                WHEN v.home_team_name ILIKE '%Paris%' THEN 'Paris'
                WHEN v.home_team_name ILIKE '%Marseille%' THEN 'Marseille'
                WHEN v.home_team_name ILIKE '%Lyon%' THEN 'Lyon'
                WHEN v.home_team_name ILIKE '%Monaco%' THEN 'Monaco'
                WHEN v.home_team_name ILIKE '%Lille%' THEN 'Lille'
                WHEN v.home_team_name ILIKE '%Nice%' THEN 'Nice'
                WHEN v.home_team_name ILIKE '%Rennais%' THEN 'Rennes'
                WHEN v.home_team_name ILIKE '%Lens%' THEN 'Lens'
                WHEN v.home_team_name ILIKE '%Nantes%' THEN 'Nantes'
                WHEN v.home_team_name ILIKE '%Montpellier%' THEN 'Montpellier'
                WHEN v.home_team_name ILIKE '%Strasbourg%' THEN 'Strasbourg'
                WHEN v.home_team_name ILIKE '%Brestois%' THEN 'Brest'
                WHEN v.home_team_name ILIKE '%Toulouse%' THEN 'Toulouse'
                WHEN v.home_team_name ILIKE '%Reims%' THEN 'Reims'
                WHEN v.home_team_name ILIKE '%Barcelona%' THEN 'Barcelona'
                WHEN v.home_team_name ILIKE '%Real Madrid%' THEN 'Madrid'
                WHEN v.home_team_name ILIKE '%Atlético%' THEN 'Madrid'
                WHEN v.home_team_name ILIKE '%Sevilla%' THEN 'Sevilla'
                WHEN v.home_team_name ILIKE '%Real Sociedad%' THEN 'San Sebastian'
                WHEN v.home_team_name ILIKE '%Betis%' THEN 'Sevilla'
                WHEN v.home_team_name ILIKE '%Villarreal%' THEN 'Villarreal'
                WHEN v.home_team_name ILIKE '%Athletic Club%' THEN 'Bilbao'
                WHEN v.home_team_name ILIKE '%Valencia%' THEN 'Valencia'
                ELSE NULL
            END
        ))
),

-- Final enrichment with computed metrics
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

        -- Outcome
        winner,
        match_outcome,
        home_win,
        away_win,
        is_draw,
        is_high_scoring,

        -- Home team market values
        COALESCE(home_market_value, 0)     AS home_market_value,
        COALESCE(home_avg_player_value, 0) AS home_avg_player_value,
        COALESCE(home_squad_size, 0)       AS home_squad_size,
        COALESCE(home_avg_age, 0)          AS home_avg_age,
        COALESCE(home_value_tier, 'unknown') AS home_value_tier,
        COALESCE(home_value_rank, 0)       AS home_value_rank,

        -- Away team market values
        COALESCE(away_market_value, 0)     AS away_market_value,
        COALESCE(away_avg_player_value, 0) AS away_avg_player_value,
        COALESCE(away_squad_size, 0)       AS away_squad_size,
        COALESCE(away_avg_age, 0)          AS away_avg_age,
        COALESCE(away_value_tier, 'unknown') AS away_value_tier,
        COALESCE(away_value_rank, 0)       AS away_value_rank,

        -- Value analytics
        COALESCE(home_market_value, 0) + COALESCE(away_market_value, 0) AS combined_market_value,
        COALESCE(home_market_value, 0) - COALESCE(away_market_value, 0) AS value_difference,

        CASE
            WHEN COALESCE(away_market_value, 1) > 0
            THEN ROUND(COALESCE(home_market_value, 0)::DECIMAL / COALESCE(away_market_value, 1), 2)
            ELSE 0
        END AS value_ratio,

        CASE
            WHEN COALESCE(home_market_value, 0) > COALESCE(away_market_value, 0) THEN 'home'
            WHEN COALESCE(away_market_value, 0) > COALESCE(home_market_value, 0) THEN 'away'
            ELSE 'equal'
        END AS favorite_by_value,

        -- Upset detection
        CASE
            WHEN COALESCE(home_market_value, 0) > COALESCE(away_market_value, 0) AND winner = 'AWAY_TEAM' THEN TRUE
            WHEN COALESCE(away_market_value, 0) > COALESCE(home_market_value, 0) AND winner = 'HOME_TEAM' THEN TRUE
            ELSE FALSE
        END AS is_upset,

        CASE
            WHEN COALESCE(home_market_value, 0) > COALESCE(away_market_value, 0) AND winner = 'HOME_TEAM' THEN TRUE
            WHEN COALESCE(away_market_value, 0) > COALESCE(home_market_value, 0) AND winner = 'AWAY_TEAM' THEN TRUE
            WHEN winner = 'DRAW' THEN NULL
            ELSE FALSE
        END AS richer_team_won,

        -- Weather data
        temperature_celsius,
        feels_like_celsius,
        humidity_percent,
        pressure_hpa,
        weather_condition,
        weather_description,
        wind_speed_ms,
        cloud_coverage_percent,
        rain_last_hour_mm,
        snow_last_hour_mm,
        is_rainy,
        is_cold,
        is_hot,
        is_windy,
        weather_category,

        -- Weather impact score (composite: 0=perfect, higher=worse)
        CASE
            WHEN temperature_celsius IS NOT NULL THEN
                ROUND((
                    -- Temperature penalty (ideal = 15-22°C)
                    CASE
                        WHEN temperature_celsius < 5 THEN 3
                        WHEN temperature_celsius < 10 THEN 1
                        WHEN temperature_celsius > 30 THEN 3
                        WHEN temperature_celsius > 25 THEN 1
                        ELSE 0
                    END
                    -- Rain penalty
                    + CASE WHEN COALESCE(rain_last_hour_mm, 0) > 2 THEN 3
                           WHEN COALESCE(rain_last_hour_mm, 0) > 0 THEN 1
                           ELSE 0 END
                    -- Wind penalty
                    + CASE WHEN COALESCE(wind_speed_ms, 0) > 12 THEN 3
                           WHEN COALESCE(wind_speed_ms, 0) > 8 THEN 1
                           ELSE 0 END
                    -- Snow penalty
                    + CASE WHEN COALESCE(snow_last_hour_mm, 0) > 0 THEN 4 ELSE 0 END
                )::DECIMAL, 1)
            ELSE NULL
        END AS weather_impact_score,

        -- Metadata
        CURRENT_TIMESTAMP AS dbt_loaded_at

    FROM with_weather
)

SELECT * FROM enriched
