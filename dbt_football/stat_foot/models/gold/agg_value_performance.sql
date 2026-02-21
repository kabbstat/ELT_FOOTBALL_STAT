{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    Analytics: Market Value vs Performance
    
    Key insights:
    - Win rate by value tier
    - Upset rate by competition
    - Does money buy success?
*/

WITH enriched_matches AS (
    SELECT * FROM {{ ref('fact_matches_enriched') }}
    WHERE status = 'FINISHED'
),

-- Aggregate by value tier matchup
value_tier_analysis AS (
    SELECT
        competition_code,
        value_tier_matchup,
        COUNT(*) AS total_matches,
        SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS home_wins,
        SUM(CASE WHEN away_win THEN 1 ELSE 0 END) AS away_wins,
        SUM(CASE WHEN is_draw THEN 1 ELSE 0 END) AS draws,
        SUM(CASE WHEN is_upset THEN 1 ELSE 0 END) AS upsets,
        ROUND(AVG(total_goals), 2) AS avg_goals_per_match,
        ROUND(AVG(combined_market_value) / 1000000, 2) AS avg_combined_value_millions
    FROM enriched_matches
    GROUP BY competition_code, value_tier_matchup
),

-- Aggregate by competition
competition_analysis AS (
    SELECT
        competition_code,
        competition_name,
        COUNT(*) AS total_matches,
        SUM(CASE WHEN is_upset THEN 1 ELSE 0 END) AS total_upsets,
        ROUND(100.0 * SUM(CASE WHEN is_upset THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS upset_rate_percent,
        ROUND(100.0 * SUM(CASE WHEN richer_team_won THEN 1 ELSE 0 END) / NULLIF(COUNT(*) - SUM(CASE WHEN is_draw THEN 1 ELSE 0 END), 0), 2) AS richer_team_win_rate,
        ROUND(AVG(total_goals), 2) AS avg_goals,
        SUM(total_goals) AS total_goals_scored,
        ROUND(AVG(CASE WHEN home_team_market_value > 0 THEN home_team_market_value ELSE NULL END) / 1000000, 2) AS avg_home_team_value_millions,
        ROUND(AVG(CASE WHEN away_team_market_value > 0 THEN away_team_market_value ELSE NULL END) / 1000000, 2) AS avg_away_team_value_millions
    FROM enriched_matches
    GROUP BY competition_code, competition_name
),

-- Team performance vs value
team_value_performance AS (
    SELECT
        home_team_name AS team_name,
        competition_code,
        MAX(home_team_market_value) AS market_value,
        MAX(home_value_tier) AS value_tier,
        COUNT(*) AS home_matches,
        SUM(CASE WHEN home_win THEN 1 ELSE 0 END) AS home_wins,
        ROUND(100.0 * SUM(CASE WHEN home_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS home_win_rate,
        SUM(fulltime_home_score) AS goals_scored_home,
        SUM(fulltime_away_score) AS goals_conceded_home
    FROM enriched_matches
    WHERE home_team_market_value > 0
    GROUP BY home_team_name, competition_code
)

-- Final selection: Competition-level insights
SELECT
    'competition_analysis' AS analysis_type,
    ca.competition_code,
    ca.competition_name,
    ca.total_matches,
    ca.total_upsets,
    ca.upset_rate_percent,
    ca.richer_team_win_rate,
    ca.avg_goals,
    ca.total_goals_scored,
    ca.avg_home_team_value_millions,
    ca.avg_away_team_value_millions,
    CURRENT_TIMESTAMP AS generated_at
FROM competition_analysis ca

UNION ALL

-- Value tier matchup insights (limited to top combinations)
SELECT
    'value_tier_matchup' AS analysis_type,
    vta.competition_code,
    vta.value_tier_matchup AS competition_name,
    vta.total_matches,
    vta.upsets AS total_upsets,
    ROUND(100.0 * vta.upsets / NULLIF(vta.total_matches, 0), 2) AS upset_rate_percent,
    NULL AS richer_team_win_rate,
    vta.avg_goals_per_match AS avg_goals,
    NULL AS total_goals_scored,
    vta.avg_combined_value_millions AS avg_home_team_value_millions,
    NULL AS avg_away_team_value_millions,
    CURRENT_TIMESTAMP AS generated_at
FROM value_tier_analysis vta
WHERE vta.total_matches >= 5
