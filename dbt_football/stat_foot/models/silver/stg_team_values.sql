{{
    config(
        alias='stg_team_values',
        schema='silver',
        materialized='table'
    )
}}

/*
    Staging model for team market values
    Source: Transfermarkt (static data / web scraping)
*/

WITH source_values AS (
    SELECT * FROM {{ source('bronze', 'team_values') }}
),

cleaned AS (
    SELECT
        -- Team identification
        team_name,
        COALESCE(competition_code, 'Unknown') AS competition_code,
        COALESCE(country, 'Unknown') AS country,
        
        -- Squad information
        CAST(COALESCE(squad_size, 0) AS INTEGER) AS squad_size,
        CAST(COALESCE(avg_age, 0) AS DECIMAL(4,1)) AS average_age,
        
        -- Market values
        CAST(COALESCE(market_value_eur, 0) AS BIGINT) AS market_value_eur,
        
        -- Calculated: average player value
        CASE 
            WHEN squad_size > 0 THEN CAST(market_value_eur / squad_size AS BIGINT)
            ELSE 0
        END AS avg_player_value_eur,
        
        -- Value categories for analysis
        CASE
            WHEN market_value_eur >= 1000000000 THEN 'elite'        -- > 1 billion
            WHEN market_value_eur >= 500000000 THEN 'top_tier'      -- 500M - 1B
            WHEN market_value_eur >= 200000000 THEN 'upper_mid'     -- 200M - 500M
            WHEN market_value_eur >= 100000000 THEN 'mid_tier'      -- 100M - 200M
            ELSE 'lower_tier'                                        -- < 100M
        END AS value_tier,
        
        -- Age categories
        CASE
            WHEN avg_age < 25 THEN 'young'
            WHEN avg_age < 27 THEN 'balanced'
            WHEN avg_age < 29 THEN 'experienced'
            ELSE 'veteran'
        END AS squad_age_category,
        
        -- Metadata
        COALESCE(data_source, 'unknown') AS data_source,
        CAST(fetched_at AS TIMESTAMP) AS fetched_at,
        
        -- Ranking within competition
        ROW_NUMBER() OVER (
            PARTITION BY competition_code 
            ORDER BY market_value_eur DESC
        ) AS value_rank_in_competition
        
    FROM source_values
    WHERE team_name IS NOT NULL
)

SELECT * FROM cleaned
