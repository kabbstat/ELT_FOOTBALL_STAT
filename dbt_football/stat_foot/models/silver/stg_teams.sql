{{ config(
    materialized='table',
    schema='silver'
) }}

WITH home_teams AS (
    SELECT DISTINCT
        "homeTeam_id" AS team_id,
        "homeTeam_name" AS team_name,
        "homeTeam_shortName" AS team_short_name,
        "homeTeam_tla" AS team_tla,
        "homeTeam_crest" AS team_crest,
        competition_code,
        competition_name
    FROM {{ source('bronze', 'matches') }}
    WHERE "homeTeam_id" IS NOT NULL
),

away_teams AS (
    SELECT DISTINCT
        "awayTeam_id" AS team_id,
        "awayTeam_name" AS team_name,
        "awayTeam_shortName" AS team_short_name,
        "awayTeam_tla" AS team_tla,
        "awayTeam_crest" AS team_crest,
        competition_code,
        competition_name
    FROM {{ source('bronze', 'matches') }}
    WHERE "awayTeam_id" IS NOT NULL
),

all_teams AS (
    SELECT * FROM home_teams
    UNION
    SELECT * FROM away_teams
)

SELECT DISTINCT
    team_id,
    team_name,
    team_short_name,
    team_tla,
    team_crest,
    competition_code,
    competition_name,
    CURRENT_TIMESTAMP AS loaded_at
FROM all_teams
WHERE team_id IS NOT NULL
