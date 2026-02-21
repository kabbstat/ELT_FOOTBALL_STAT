# Architecture du Projet

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                     FOOTBALL ELT PIPELINE                        │
│                   Production-Grade Architecture                  │
└─────────────────────────────────────────────────────────────────┘

┌────────────────┐
│  Data Sources  │
│                │
│  Football API  │ ← Rate limiting: 10 req/min
│  (Free Tier)   │
└───────┬────────┘
        │
        │ HTTPS/JSON
        ▼
┌───────────────────────────────────────────────────────────────┐
│                      EXTRACTION LAYER                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  foot_data_enhanced.py                               │    │
│  │  - Error handling & retry logic                      │    │
│  │  - Rate limiting                                      │    │
│  │  - Structured logging                                 │    │
│  │  - Data validation                                    │    │
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
│  │                                                        │    │
│  │  Transformations:                                     │    │
│  │  ✓ Type casting                                      │    │
│  │  ✓ Null handling                                     │    │
│  │  ✓ Column renaming                                   │    │
│  │  ✓ Date parsing                                      │    │
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
│  DAG: football_elt_pipeline_enhanced                           │
│  Schedule: @weekly                                             │
│                                                                 │
│  Tasks:                                                         │
│  1. extract_football_data                                      │
│  2. validate_extracted_data                                    │
│  3. load_to_bronze                                             │
│  4. dbt_transformation (clean → deps → run → test → docs)     │
│  5. data_quality_checks                                        │
│  6. send_success_report                                        │
│                                                                 │
│  Features:                                                      │
│  ✓ Error handling                                             │
│  ✓ Retry logic                                                │
│  ✓ Monitoring & alerting                                      │
│  ✓ TaskGroups for organization                               │
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
│   └── stg_teams (deduplicated)
└── gold
    ├── fact_matches (core facts)
    ├── dim_teams (dimension)
    ├── agg_team_performance (aggregated)
    └── agg_competition_stats (aggregated)
```

### Airflow

```
airflow/
├── dags/
│   └── football_elt_dag_enhanced.py
├── logs/
│   └── dag_id=football_elt_pipeline_enhanced/
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
| Python | 3.9+ | Type hints, performances |
| PostgreSQL | 15 | Fonctionnalités modernes |
| Airflow | 2.7+ | TaskGroups, UI améliorée |
| DBT | 1.6+ | Tests améliorés |
| Streamlit | 1.28+ | Components modernes |
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
