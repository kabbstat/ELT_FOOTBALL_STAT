{{
    config(
        alias='stg_weather',
        schema='silver',
        materialized='table'
    )
}}

/*
    Staging model for weather data
    Source: OpenWeather API
*/

WITH source_weather AS (
    SELECT * FROM {{ source('bronze', 'weather') }}
),

cleaned AS (
    SELECT
        city,
        COALESCE(country, 'Unknown') AS country,
        CAST(lat AS DECIMAL(10,6)) AS latitude,
        CAST(lon AS DECIMAL(10,6)) AS longitude,
        
        -- Temperature
        CAST(temperature AS DECIMAL(5,2)) AS temperature_celsius,
        CAST(feels_like AS DECIMAL(5,2)) AS feels_like_celsius,
        
        -- Weather conditions
        CAST(humidity AS INTEGER) AS humidity_percent,
        CAST(pressure AS INTEGER) AS pressure_hpa,
        COALESCE(weather_main, 'Unknown') AS weather_condition,
        weather_description,
        
        -- Wind
        CAST(wind_speed AS DECIMAL(5,2)) AS wind_speed_ms,
        CAST(wind_deg AS INTEGER) AS wind_direction_deg,
        
        -- Precipitation
        CAST(clouds AS INTEGER) AS cloud_coverage_percent,
        CAST(COALESCE(rain_1h, 0) AS DECIMAL(5,2)) AS rain_last_hour_mm,
        CAST(COALESCE(snow_1h, 0) AS DECIMAL(5,2)) AS snow_last_hour_mm,
        
        -- Visibility
        CAST(visibility AS INTEGER) AS visibility_meters,
        
        -- Timestamps
        CAST(fetched_at AS TIMESTAMP) AS weather_timestamp,
        CAST(fetched_at AS TIMESTAMP) AS fetched_at,
        
        -- Derived fields
        CASE 
            WHEN weather_main IN ('Rain', 'Drizzle', 'Thunderstorm') THEN TRUE
            WHEN COALESCE(rain_1h, 0) > 0 THEN TRUE
            ELSE FALSE
        END AS is_rainy,
        
        CASE 
            WHEN temperature < 10 THEN TRUE
            ELSE FALSE
        END AS is_cold,
        
        CASE 
            WHEN temperature > 30 THEN TRUE
            ELSE FALSE
        END AS is_hot,
        
        CASE 
            WHEN wind_speed > 10 THEN TRUE
            ELSE FALSE
        END AS is_windy,
        
        -- Weather category for analysis
        CASE
            WHEN weather_main IN ('Rain', 'Drizzle', 'Thunderstorm', 'Snow') THEN 'adverse'
            WHEN temperature < 5 OR temperature > 35 THEN 'extreme'
            WHEN wind_speed > 15 THEN 'windy'
            ELSE 'favorable'
        END AS weather_category
        
    FROM source_weather
    WHERE city IS NOT NULL
)

SELECT * FROM cleaned
