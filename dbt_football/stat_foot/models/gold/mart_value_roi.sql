{{ config(
    materialized='table',
    schema='gold'
) }}

/*
    Value ROI Analysis (Return on Investment)
    ==========================================
    Which clubs get the best performance per euro of market value?
    
    Key insights:
    - Points per million euros
    - Overperformers (bargains) and underperformers (overspends)
    - Cost per win, cost per goal
*/

WITH team_stats AS (
    SELECT * FROM {{ ref('mart_team_stats') }}
),

team_values AS (
    SELECT * FROM {{ ref('stg_team_values') }}
),

-- Combine stats with market values
combined AS (
    SELECT
        ts.team_id,
        ts.team_name,
        ts.league_code,

        -- Performance
        ts.total_matches,
        ts.total_wins,
        ts.total_draws,
        ts.total_losses,
        ts.total_points,
        ts.total_goals_scored,
        ts.total_goals_conceded,
        ts.goal_difference,
        ts.points_per_match,
        ts.win_rate,
        ts.goals_scored_per_match,
        ts.performance_rating,

        -- Market value
        COALESCE(tv.market_value_eur, 0) AS market_value_eur,
        COALESCE(tv.value_tier, 'unknown') AS value_tier,
        COALESCE(tv.avg_player_value_eur, 0) AS avg_player_value,
        COALESCE(tv.squad_size, 0) AS squad_size,
        COALESCE(tv.average_age, 0) AS average_age,
        tv.value_rank_in_competition

    FROM team_stats ts
    LEFT JOIN team_values tv
        ON LOWER(TRIM(ts.team_name)) = LOWER(TRIM(tv.team_name))
),

-- Calculate ROI metrics
roi AS (
    SELECT
        *,

        -- Points per million EUR
        CASE
            WHEN market_value_eur > 0
            THEN ROUND(total_points::DECIMAL / (market_value_eur / 1000000.0), 4)
            ELSE NULL
        END AS points_per_million_eur,

        -- Cost per win
        CASE
            WHEN total_wins > 0 AND market_value_eur > 0
            THEN ROUND(market_value_eur::DECIMAL / total_wins, 0)
            ELSE NULL
        END AS cost_per_win_eur,

        -- Cost per goal
        CASE
            WHEN total_goals_scored > 0 AND market_value_eur > 0
            THEN ROUND(market_value_eur::DECIMAL / total_goals_scored, 0)
            ELSE NULL
        END AS cost_per_goal_eur,

        -- Expected rank (by value) vs actual rank (by points)
        value_rank_in_competition AS expected_rank,
        ROW_NUMBER() OVER (
            PARTITION BY league_code
            ORDER BY total_points DESC, goal_difference DESC
        ) AS actual_rank

    FROM combined
    WHERE market_value_eur > 0
)

SELECT
    team_id,
    team_name,
    league_code,

    -- Performance
    total_matches,
    total_wins,
    total_draws,
    total_losses,
    total_points,
    total_goals_scored,
    total_goals_conceded,
    goal_difference,
    points_per_match,
    win_rate,
    performance_rating,

    -- Market value
    market_value_eur,
    value_tier,
    avg_player_value,
    squad_size,
    average_age,

    -- ROI metrics
    points_per_million_eur,
    cost_per_win_eur,
    cost_per_goal_eur,

    -- Rank comparison
    expected_rank,
    actual_rank,
    expected_rank - actual_rank AS rank_difference,  -- positive = overperforming

    -- ROI classification
    CASE
        WHEN expected_rank - actual_rank >= 5 THEN '🌟 Major bargain'
        WHEN expected_rank - actual_rank >= 2 THEN '💰 Overperformer'
        WHEN expected_rank - actual_rank >= -1 THEN '✅ On track'
        WHEN expected_rank - actual_rank >= -4 THEN '⚠️ Underperformer'
        ELSE '💸 Major overspend'
    END AS roi_classification,

    -- Efficiency metrics ranking
    ROW_NUMBER() OVER (
        PARTITION BY league_code
        ORDER BY points_per_million_eur DESC NULLS LAST
    ) AS efficiency_rank,

    CURRENT_TIMESTAMP AS dbt_updated_at

FROM roi
ORDER BY league_code, efficiency_rank
