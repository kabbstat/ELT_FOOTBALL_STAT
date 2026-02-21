{{ config(
    materialized='table',
    schema='gold'
) }}

SELECT 
    team_id,
    team_name,
    team_short_name,
    team_tla,
    team_crest,
    competition_code,
    competition_name,
    loaded_at
FROM {{ ref('stg_teams') }}
