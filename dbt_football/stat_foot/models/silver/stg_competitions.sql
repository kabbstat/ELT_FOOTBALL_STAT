{{ config(
    materialized='table',
    schema='silver'
) }}

WITH source_data AS (
    SELECT * FROM {{ source('bronze', 'competitions') }}
),

cleaned AS (
    SELECT
        id AS competition_id,
        name AS competition_name,
        code AS competition_code,
        type AS competition_type,
        emblem AS competition_emblem,
        "area.name" AS area_name,
        "area.code" AS area_code,
        "area.flag" AS area_flag,
        "currentSeason.id" AS current_season_id,
        "currentSeason.startDate"::DATE AS current_season_start,
        "currentSeason.endDate"::DATE AS current_season_end,
        "currentSeason.currentMatchday" AS current_matchday,
        CURRENT_TIMESTAMP AS dbt_loaded_at
    FROM source_data
    WHERE id IS NOT NULL
      AND code IS NOT NULL
)

SELECT * FROM cleaned
