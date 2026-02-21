{% snapshot snapshot_team_values %}

{{
    config(
        target_schema='snapshots',
        unique_key='team_name',
        strategy='check',
        check_cols=['market_value_eur', 'squad_size', 'avg_age'],
        invalidate_hard_deletes=True
    )
}}

/*
    SCD Type 2 Snapshot for Team Market Values
    ============================================
    Captures historical changes in market values over time.
    Tracks: market_value_eur, squad_size, avg_age

    This enables:
    - Market value trend analysis over transfer windows
    - Correlation between value changes and performance
    - Investment tracking (before/after transfers)
*/

SELECT
    team_name,
    competition_code,
    country,
    squad_size,
    avg_age,
    market_value_eur,
    CASE
        WHEN squad_size > 0 THEN market_value_eur / squad_size
        ELSE 0
    END AS avg_player_value_eur,
    data_source,
    fetched_at,
    CURRENT_TIMESTAMP AS snapshot_loaded_at
FROM {{ source('bronze', 'team_values') }}
WHERE team_name IS NOT NULL

{% endsnapshot %}
