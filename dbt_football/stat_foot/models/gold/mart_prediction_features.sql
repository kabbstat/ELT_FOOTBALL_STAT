{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    ML Feature Table for Match Prediction
    =======================================
    Pre-computed features ready for ML model ingestion.
    Each row = one match with all predictive features.

    Feature categories:
    1. Team form (last 5 matches)
    2. Market value comparison
    3. Weather conditions
    4. Head-to-head (H2H) history
    5. Home/away advantage
*/

WITH enriched AS (
    SELECT * FROM {{ ref('fact_matches_full') }}
    WHERE status = 'FINISHED'
),

team_form AS (
    SELECT * FROM {{ ref('mart_team_form') }}
),

team_stats AS (
    SELECT * FROM {{ ref('mart_team_stats') }}
),

-- Head-to-head history
h2h AS (
    SELECT
        home_team_name,
        away_team_name,
        COUNT(*) AS h2h_total_matches,
        SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS h2h_home_wins,
        SUM(CASE WHEN away_win THEN 1 ELSE 0 END) AS h2h_away_wins,
        SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) AS h2h_draws,
        ROUND(AVG(total_goals), 2) AS h2h_avg_goals,
        ROUND(AVG(fulltime_home_score), 2) AS h2h_avg_home_goals,
        ROUND(AVG(fulltime_away_score), 2) AS h2h_avg_away_goals
    FROM enriched
    GROUP BY home_team_name, away_team_name
)

SELECT
    -- Match identifiers
    e.match_id,
    e.match_date,
    e.matchday,
    e.competition_code,

    -- Teams
    e.home_team_name,
    e.away_team_name,

    -- TARGET VARIABLE
    CASE
        WHEN e.home_win THEN 1
        WHEN e.is_draw THEN 0
        WHEN e.away_win THEN -1
    END AS match_result_encoded,  -- 1=home win, 0=draw, -1=away win
    e.total_goals,

    -- ==========================================
    -- FEATURE 1: Market Value comparison
    -- ==========================================
    e.home_market_value,
    e.away_market_value,
    e.combined_market_value,
    e.value_ratio,
    CASE
        WHEN e.combined_market_value > 0
        THEN ROUND(
            (e.home_market_value::DECIMAL - e.away_market_value) /
            e.combined_market_value, 4
        )
        ELSE 0
    END AS value_advantage_pct,  -- [-1, 1]: positive = home richer
    e.home_value_tier,
    e.away_value_tier,

    -- ==========================================
    -- FEATURE 2: Team Form (last 5 matches)
    -- ==========================================
    COALESCE(hf.last_5_points, 0) AS home_form_points,
    COALESCE(hf.current_form, '') AS home_form_string,
    COALESCE(af.last_5_points, 0) AS away_form_points,
    COALESCE(af.current_form, '') AS away_form_string,
    COALESCE(hf.last_5_points, 0) - COALESCE(af.last_5_points, 0) AS form_difference,

    -- ==========================================
    -- FEATURE 3: Season stats
    -- ==========================================
    COALESCE(hs.win_rate, 0) AS home_team_win_rate,
    COALESCE(hs.goals_scored_per_match, 0) AS home_team_goals_per_match,
    COALESCE(hs.goals_conceded_per_match, 0) AS home_team_conceded_per_match,
    COALESCE(hs.points_per_match, 0) AS home_team_points_per_match,
    COALESCE(aws.win_rate, 0) AS away_team_win_rate,
    COALESCE(aws.goals_scored_per_match, 0) AS away_team_goals_per_match,
    COALESCE(aws.goals_conceded_per_match, 0) AS away_team_conceded_per_match,
    COALESCE(aws.points_per_match, 0) AS away_team_points_per_match,

    -- ==========================================
    -- FEATURE 4: Head-to-Head
    -- ==========================================
    COALESCE(h.h2h_total_matches, 0) AS h2h_total_matches,
    COALESCE(h.h2h_home_wins, 0) AS h2h_home_wins,
    COALESCE(h.h2h_away_wins, 0) AS h2h_away_wins,
    COALESCE(h.h2h_avg_goals, 0) AS h2h_avg_goals,

    -- ==========================================
    -- FEATURE 5: Weather conditions
    -- ==========================================
    COALESCE(e.temperature_celsius, 15) AS temperature,  -- default to mild
    COALESCE(e.humidity_percent, 60) AS humidity,
    COALESCE(e.wind_speed_ms, 3) AS wind_speed,
    COALESCE(e.rain_last_hour_mm, 0) AS rain_mm,
    COALESCE(e.weather_impact_score, 0) AS weather_impact_score,
    CASE WHEN e.is_rainy THEN 1 ELSE 0 END AS is_rainy_flag,
    CASE WHEN e.is_cold THEN 1 ELSE 0 END AS is_cold_flag,
    CASE WHEN e.is_windy THEN 1 ELSE 0 END AS is_windy_flag,

    -- ==========================================
    -- FEATURE 6: Temporal features
    -- ==========================================
    e.match_month,
    EXTRACT(DOW FROM e.match_datetime_utc) AS day_of_week,  -- 0=Sunday
    CASE
        WHEN EXTRACT(HOUR FROM e.match_datetime_utc) < 15 THEN 'early'
        WHEN EXTRACT(HOUR FROM e.match_datetime_utc) < 18 THEN 'afternoon'
        ELSE 'evening'
    END AS kick_off_period,

    -- ==========================================
    -- COMPOSITE FEATURES
    -- ==========================================
    -- Overall home advantage score
    ROUND((
        COALESCE(hf.last_5_points, 0) * 0.3 +
        CASE WHEN e.home_market_value > e.away_market_value THEN 3 ELSE 0 END * 0.4 +
        COALESCE(h.h2h_home_wins, 0) * 0.3
    )::DECIMAL, 2) AS home_advantage_score,

    -- Metadata
    CURRENT_TIMESTAMP AS feature_generated_at

FROM enriched e
LEFT JOIN team_form hf
    ON e.home_team_name = hf.team_name AND e.competition_code = hf.league_code
LEFT JOIN team_form af
    ON e.away_team_name = af.team_name AND e.competition_code = af.league_code
LEFT JOIN team_stats hs
    ON e.home_team_name = hs.team_name AND e.competition_code = hs.league_code
LEFT JOIN team_stats aws
    ON e.away_team_name = aws.team_name AND e.competition_code = aws.league_code
LEFT JOIN h2h h
    ON e.home_team_name = h.home_team_name AND e.away_team_name = h.away_team_name
