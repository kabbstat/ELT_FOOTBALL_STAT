# Architecture du Projet

> Derniere mise a jour : Fevrier 2026

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                     FOOTBALL ELT PIPELINE                        │
│        Production-Grade Architecture + Elasticsearch/Kibana     │
└─────────────────────────────────────────────────────────────────┘

┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  Data Sources  │  │   OpenWeather  │  │  Transfermarkt │  │   RSS Feeds    │
│                │  │                │  │                │  │                │
│  Football API  │  │   Weather API  │  │  Market Values │  │  News Articles │
│  (Free Tier)   │  │  (Free Tier)   │  │  (Scraping)    │  │  (8 sources)   │
└───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘
        │
        │ HTTPS/JSON
        ▼
┌───────────────────────────────────────────────────────────────┐
│                      EXTRACTION LAYER                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  fetch_daily_matches.py   - Matchs quotidiens        │    │
│  │  fetch_weather.py         - Meteo des villes         │    │
│  │  fetch_match_weather.py   - Meteo par match          │    │
│  │  fetch_transfermarkt.py   - Valeurs de marche        │    │
│  │  fetch_football_news.py   - Actualites RSS (8 feeds) │    │
│  │  load_postgres.py         - Chargement Bronze        │    │
│  └──────────────────────────────────────────────────────┘    │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ Parquet files
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    LANDING ZONE (File System)                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  data/landing/                                        │    │
│  │  - all_matches_2023.parquet                          │    │
│  │  - all_matches_2024.parquet                          │    │
│  │  - competitions.parquet                              │    │
│  │  - Raw JSON backups                                  │    │
│  └──────────────────────────────────────────────────────┘    │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ Bulk load
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    BRONZE LAYER (PostgreSQL)                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Schema: bronze                                       │    │
│  │  - matches (raw)                                      │    │
│  │  - competitions (raw)                                 │    │
│  │                                                        │    │
│  │  Characteristics:                                     │    │
│  │  ✓ Immutable                                         │    │
│  │  ✓ Full audit trail                                  │    │
│  │  ✓ Source of truth                                   │    │
│  └──────────────────────────────────────────────────────┘    │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ DBT transformations
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    SILVER LAYER (PostgreSQL)                   │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Schema: silver                                       │    │
│  │  - stg_matches (cleaned & standardized)              │    │
│  │  - stg_teams (deduplicated)                          │    │
│  │  - stg_competitions (metadata competitions)          │    │
│  │  - stg_weather (meteo nettoyee)                      │    │
│  │  - stg_team_values (valeurs marche normalisees)      │    │
│  │                                                        │    │
│  │  Transformations:                                     │    │
│  │  ✓ Type casting & null handling                      │    │
│  │  ✓ Column renaming & date parsing                    │    │
│  │  ✓ Deduplication                                     │    │
│  └──────────────────────────────────────────────────────┘    │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ Business logic
        ▼
┌───────────────────────────────────────────────────────────────┐
│                     GOLD LAYER (PostgreSQL)                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Schema: gold                                         │    │
│  │                                                        │    │
│  │  Fact Tables:                                         │    │
│  │  - fact_matches                                       │    │
│  │                                                        │    │
│  │  Dimension Tables:                                    │    │
│  │  - dim_teams                                         │    │
│  │                                                        │    │
│  │  Aggregations:                                        │    │
│  │  - agg_team_performance                              │    │
│  │  - agg_competition_stats                             │    │
│  │                                                        │    │
│  │  Marts:                                               │    │
│  │  - mart_league_standings                             │    │
│  │  - mart_team_form                                    │    │
│  │                                                        │    │
│  │  Optimizations:                                       │    │
│  │  ✓ Indexes on foreign keys                          │    │
│  │  ✓ Materialized as tables                           │    │
│  │  ✓ Pre-calculated metrics                           │    │
│  └──────────────────────────────────────────────────────┘    │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ SQL queries
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Streamlit Dashboard (app.py)                        │    │
│  │  - Overview                                           │    │
│  │  - Competition Analysis                              │    │
│  │  - Team Performance                                  │    │
│  │  - Match Analysis                                    │    │
│  │  - Team Deep Dive                                    │    │
│  │  - Match Probability (scikit-learn)                  │    │
│  │  - News Search (Elasticsearch full-text)             │    │
│  │                                                        │    │
│  │  Features:                                            │    │
│  │  ✓ Interactive charts (Plotly)                      │    │
│  │  ✓ Real-time data refresh                           │    │
│  │  ✓ Multiple views                                    │    │
│  │  ✓ Responsive design                                 │    │
│  └──────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION (Airflow)                      │
│                                                                 │
│  DAG: football_elt_pipeline_v3                                 │
│  Schedule: 0 6 * * * (quotidien a 06:00 UTC)                  │
│                                                                 │
│  Architecture dual-branch :                                     │
│                                                                 │
│  Branche inconditionnelle (quotidienne) :                      │
│  1. extract_weather                                            │
│  2. extract_transfermarkt                                      │
│  3. extract_news (RSS → Elasticsearch)                         │
│                                                                 │
│  Branche conditionnelle (jours de match) :                     │
│  4. check_match_days (ShortCircuitOperator)                    │
│  5. extract_daily_matches → load_matches                       │
│  6. extract_match_weather                                      │
│                                                                 │
│  Pipeline commun :                                              │
│  7. dbt_snapshot → dbt_run → dbt_test → dbt_freshness         │
│  8. index_elasticsearch → generate_docs → quality_report       │
│                                                                 │
│  Features:                                                      │
│  ✓ trigger_rule pour eviter propagation des skips             │
│  ✓ Retry logic & error handling                               │
│  ✓ Parallel extraction tasks                                  │
└───────────────────────────────────────────────────────────────┘
```

## Flux de Données Détaillé

### 1. Extraction (E)

```
API Request → Rate Limiting → Retry Logic → JSON → Parquet → Landing Zone
                    ↓
              Error Handling
                    ↓
              Logging (logs/extraction.log)
```

### 2. Loading (L)

```
Landing Zone → Validation → PostgreSQL (Bronze) → Stats Collection
                    ↓
              Error Handling
                    ↓
              Logging (logs/loading.log)
```

### 3. Transformation (T)

```
Bronze → Silver (stg_*) → Gold (fact_*, dim_*, agg_*)
           ↓                        ↓
       DBT Tests              DBT Tests
           ↓                        ↓
       Documentation          Documentation
```

## Composants Techniques

### Base de Données (PostgreSQL)

```sql
football_stats_db
├── bronze
│   ├── matches (500K+ rows)
│   └── competitions
├── silver
│   ├── stg_matches (cleaned)
│   ├── stg_teams (deduplicated)
│   ├── stg_competitions (metadata)
│   ├── stg_weather (meteo)
│   └── stg_team_values (valeurs marche)
└── gold
    ├── fact_matches (core facts)
    ├── dim_teams (dimension)
    ├── agg_team_performance (aggregated)
    ├── agg_competition_stats (aggregated)
    ├── mart_league_standings (classements)
    └── mart_team_form (forme recente)
```

### Airflow

```
airflow/
├── dags/
│   ├── football_elt_pipeline_v2.py
│   └── football_elt_pipeline_v3.py
├── logs/
│   └── dag_id=football_elt_pipeline_v3/
└── plugins/
```

### DBT

```
dbt_football/stat_foot/
├── models/
│   ├── sources.yml (source definitions)
│   ├── silver/ (staging models)
│   └── gold/ (business models)
├── tests/ (custom data tests)
└── target/ (compiled SQL & docs)
```

### Dashboard

```
dashboard/
├── app.py (Streamlit application)
└── requirements.txt
```

## Principes de Design

### 1. Idempotence
- Réexécution sûre du pipeline
- Pas d'effets de bord
- Replace vs Append stratégies

### 2. Scalabilité
- Architecture modulaire
- Séparation des responsabilités
- Extensible pour nouvelles sources

### 3. Fiabilité
- Error handling à tous les niveaux
- Retry logic avec backoff
- Data validation
- Tests automatisés

### 4. Observabilité
- Logging structuré
- Métriques de pipeline
- Alertes configurables
- Documentation générée

### 5. Maintenabilité
- Code propre et documenté
- Configuration centralisée
- Tests de qualité
- Documentation complète

## Technologies & Versions

| Composant | Version | Justification |
|-----------|---------|---------------|
| Python | 3.11 | Type hints, performances |
| PostgreSQL | 15 | Fonctionnalités modernes |
| Airflow | 2.7.3 | TaskGroups, UI améliorée |
| DBT | 1.7 | Tests améliorés, snapshots |
| Streamlit | 1.28+ | Components modernes |
| Elasticsearch | 8.11 | Full-text search, news |
| Kibana | 8.11 | Visualisations analytics |
| Docker | 20.10+ | Containerization |

## Sécurité

- ✅ Credentials dans .env (jamais commité)
- ✅ .gitignore complet
- ✅ Validation des inputs
- ✅ SQL injection prevention (SQLAlchemy)
- ✅ Rate limiting
- ✅ Logs sans données sensibles

## Performance

### Optimisations Implémentées

1. **Batch Loading** : Chunks de 1000 rows
2. **Indexes** : Sur foreign keys et colonnes fréquentes
3. **Materialization** : Tables vs Views selon usage
4. **Cache** : Streamlit cache pour requêtes
5. **Parallel Processing** : TaskGroups Airflow

### Métriques

- Extraction : ~2-3 minutes pour 3 ligues
- Loading : ~30 secondes pour 500K rows
- Transformation : ~1-2 minutes (DBT run)
- Dashboard : <1 seconde (avec cache)

## Monitoring

### Logs
- `logs/extraction.log` : Extraction détaillée
- `logs/loading.log` : Loading détaillé
- `airflow/logs/` : Orchestration
- `dbt_football/stat_foot/logs/` : Transformations

### Métriques Collectées
- Nombre de requêtes API
- Rows extraites/chargées
- Durée des tasks
- Tests réussis/échoués
- Erreurs et warnings

### Alertes
- Email sur échec de task
- Notification custom configurable
- Logs d'erreur structurés
