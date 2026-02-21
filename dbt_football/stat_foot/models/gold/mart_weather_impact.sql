{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    Weather Impact Analysis
    ========================
    Analyses how weather conditions affect match outcomes and scoring.
    
    Key insights:
    - Average goals per weather condition
    - Home win rate under rain/cold/wind
    - Scoring patterns by temperature range
*/

WITH matches AS (
    SELECT * FROM {{ ref('fact_matches_full') }}
    WHERE status = 'FINISHED'
      AND weather_condition IS NOT NULL
),

-- Goals by weather condition
by_weather_condition AS (
    SELECT
        weather_condition,
        weather_category,
        competition_code,
        COUNT(*) AS total_matches,
        ROUND(AVG(total_goals), 2) AS avg_goals,
        ROUND(AVG(fulltime_home_score), 2) AS avg_home_goals,
        ROUND(AVG(fulltime_away_score), 2) AS avg_away_goals,
        SUM(total_goals) AS total_goals_scored,
        ROUND(100.0 * SUM(CASE WHEN home_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS home_win_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN away_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS away_win_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS draw_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN is_high_scoring THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS high_scoring_rate_pct,
        ROUND(AVG(weather_impact_score), 2) AS avg_weather_impact
    FROM matches
    GROUP BY weather_condition, weather_category, competition_code
),

-- Goals by temperature range
by_temperature AS (
    SELECT
        CASE
            WHEN temperature_celsius < 5 THEN '❄️ < 5°C'
            WHEN temperature_celsius < 10 THEN '🌡️ 5-10°C'
            WHEN temperature_celsius < 15 THEN '🌤️ 10-15°C'
            WHEN temperature_celsius < 20 THEN '☀️ 15-20°C'
            WHEN temperature_celsius < 25 THEN '🔥 20-25°C'
            ELSE '🌡️ > 25°C'
        END AS temp_range,
        competition_code,
        COUNT(*) AS total_matches,
        ROUND(AVG(total_goals), 2) AS avg_goals,
        ROUND(100.0 * SUM(CASE WHEN home_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS home_win_rate_pct,
        ROUND(100.0 * SUM(CASE WHEN is_upset THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS upset_rate_pct,
        ROUND(AVG(temperature_celsius), 1) AS avg_temp
    FROM matches
    WHERE temperature_celsius IS NOT NULL
    GROUP BY
        CASE
            WHEN temperature_celsius < 5 THEN '❄️ < 5°C'
            WHEN temperature_celsius < 10 THEN '🌡️ 5-10°C'
            WHEN temperature_celsius < 15 THEN '🌤️ 10-15°C'
            WHEN temperature_celsius < 20 THEN '☀️ 15-20°C'
            WHEN temperature_celsius < 25 THEN '🔥 20-25°C'
            ELSE '🌡️ > 25°C'
        END,
        competition_code
),

-- Adverse weather impact
adverse_analysis AS (
    SELECT
        competition_code,
        COUNT(*) AS total_matches,
        SUM(CASE WHEN weather_category = 'adverse' THEN 1 ELSE 0 END) AS adverse_matches,
        ROUND(AVG(CASE WHEN weather_category = 'adverse' THEN total_goals END), 2) AS avg_goals_adverse,
        ROUND(AVG(CASE WHEN weather_category = 'favorable' THEN total_goals END), 2) AS avg_goals_favorable,
        ROUND(
            AVG(CASE WHEN weather_category = 'adverse' THEN total_goals END)
            - AVG(CASE WHEN weather_category = 'favorable' THEN total_goals END),
            2
        ) AS goals_diff_adverse_vs_favorable,
        ROUND(100.0 * SUM(CASE WHEN weather_category = 'adverse' AND home_win THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN weather_category = 'adverse' THEN 1 ELSE 0 END), 0), 1)
            AS home_win_rate_adverse_pct,
        ROUND(100.0 * SUM(CASE WHEN weather_category = 'favorable' AND home_win THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN weather_category = 'favorable' THEN 1 ELSE 0 END), 0), 1)
            AS home_win_rate_favorable_pct
    FROM matches
    GROUP BY competition_code
)

-- Combined output
SELECT
    'by_condition' AS analysis_type,
    weather_condition AS category,
    competition_code,
    total_matches,
    avg_goals,
    home_win_rate_pct,
    away_win_rate_pct,
    draw_rate_pct,
    high_scoring_rate_pct AS extra_metric,
    avg_weather_impact AS extra_value,
    CURRENT_TIMESTAMP AS generated_at
FROM by_weather_condition
WHERE total_matches >= 3

UNION ALL

SELECT
    'by_temperature' AS analysis_type,
    temp_range AS category,
    competition_code,
    total_matches,
    avg_goals,
    home_win_rate_pct,
    NULL AS away_win_rate_pct,
    NULL AS draw_rate_pct,
    upset_rate_pct AS extra_metric,
    avg_temp AS extra_value,
    CURRENT_TIMESTAMP AS generated_at
FROM by_temperature
WHERE total_matches >= 3

UNION ALL

SELECT
    'adverse_vs_favorable' AS analysis_type,
    'Overall' AS category,
    competition_code,
    total_matches,
    goals_diff_adverse_vs_favorable AS avg_goals,
    home_win_rate_adverse_pct AS home_win_rate_pct,
    home_win_rate_favorable_pct AS away_win_rate_pct,
    NULL AS draw_rate_pct,
    adverse_matches::DECIMAL AS extra_metric,
    avg_goals_adverse AS extra_value,
    CURRENT_TIMESTAMP AS generated_at
FROM adverse_analysis
