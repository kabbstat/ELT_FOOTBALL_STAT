# Football Statistics ELT Pipeline

Pipeline ELT complet pour l'analyse de statistiques de football europeen (Premier League, La Liga, Ligue 1) avec une architecture medallion, Elasticsearch/Kibana pour l'analytics, et un dashboard interactif.

---

## Table des Matieres

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Stack Technique](#stack-technique)
4. [Sources de Donnees](#sources-de-donnees)
5. [Installation](#installation)
6. [Utilisation](#utilisation)
7. [Structure du Projet](#structure-du-projet)
8. [Tests de Qualite](#tests-de-qualite)

---

## Vue d'ensemble

Ce projet implemente un pipeline ELT (Extract, Load, Transform) pour collecter, transformer et analyser des donnees de football provenant de plusieurs sources :

- Matchs et resultats depuis Football-Data.org API
- Donnees meteorologiques via OpenWeather API
- Valeurs de marche des equipes depuis Transfermarkt

Les donnees sont stockees dans PostgreSQL avec une architecture medallion (Bronze, Silver, Gold) et indexees dans Elasticsearch pour des recherches et visualisations avancees via Kibana.

---

## Architecture

```
                           SOURCES DE DONNEES
     ┌─────────────────┬─────────────────┬─────────────────┐
     │  Football API   │  OpenWeather    │  Transfermarkt  │
     │   (Matchs)      │   (Meteo)       │  (Valeurs)      │
     └────────┬────────┴────────┬────────┴────────┬────────┘
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   EXTRACTION LAYER    │
                    │   (Python Scripts)    │
                    │                       │
                    │  - foot_data.py       │
                    │  - fetch_weather.py   │
                    │  - fetch_transfermarkt│
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 │                 ▼
┌─────────────────────┐         │    ┌─────────────────────┐
│     POSTGRESQL      │         │    │   ELASTICSEARCH     │
│                     │         │    │                     │
│  ┌───────────────┐  │         │    │  Index: football-   │
│  │    BRONZE     │  │         │    │  enriched-matches   │
│  │  (Raw Data)   │  │         │    │                     │
│  │  - matches    │  │         │    │  Features:          │
│  │  - weather    │  │         │    │  - Full-text search │
│  │  - team_values│  │         │    │  - Aggregations     │
│  └───────┬───────┘  │         │    │  - Geo queries      │
│          │ DBT      │         │    └──────────┬──────────┘
│          ▼          │         │               │
│  ┌───────────────┐  │         │               ▼
│  │    SILVER     │  │         │    ┌─────────────────────┐
│  │  (Cleaned)    │  │         │    │      KIBANA         │
│  │  - stg_matches│  │         │    │                     │
│  │  - stg_teams  │  │         │    │  - Dashboards       │
│  │  - stg_weather│  │         │    │  - Visualizations   │
│  └───────┬───────┘  │         │    │  - Discover         │
│          │ DBT      │         │    └─────────────────────┘
│          ▼          │         │
│  ┌───────────────┐  │         │
│  │     GOLD      │  │         │
│  │ (Aggregated)  │  │         │
│  │  - fact_match │  │         │
│  │  - dim_teams  │  │         │
│  │  - agg_team   │  │         │
│  │  - mart_*     │  │         │
│  └───────────────┘  │         │
└──────────┬──────────┘         │
           │                    │
           ▼                    │
┌─────────────────────┐         │
│  STREAMLIT DASHBOARD│◄────────┘
│                     │
│  - Overview         │
│  - Team Analysis    │
│  - Match Analysis   │
└─────────────────────┘

              ORCHESTRATION
     ┌─────────────────────────────┐
     │      APACHE AIRFLOW         │
     │                             │
     │  DAG: football_elt_pipeline │
     │  Schedule: @weekly          │
     │                             │
     │  Tasks:                     │
     │  1. extract_data            │
     │  2. load_postgres           │
     │  3. load_elasticsearch      │
     │  4. dbt_transform           │
     │  5. data_quality_checks     │
     └─────────────────────────────┘
```

### Couches de Donnees (Medallion Architecture)

| Couche | Schema | Description | Tables |
|--------|--------|-------------|--------|
| Bronze | `bronze` | Donnees brutes non transformees | `matches`, `weather`, `team_values`, `competitions` |
| Silver | `silver` | Donnees nettoyees et standardisees | `stg_matches`, `stg_teams`, `stg_weather`, `stg_team_values` |
| Gold | `gold` | Agregations metier et marts | `fact_matches`, `dim_teams`, `agg_team_performance`, `mart_league_standings`, `mart_team_form` |

---

## Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Orchestration | Apache Airflow | 2.7 |
| Transformation | dbt-core | 1.7 |
| Base de donnees | PostgreSQL | 15 |
| Search Engine | Elasticsearch | 8.11 |
| Visualisation Analytics | Kibana | 8.11 |
| Dashboard | Streamlit + Plotly | - |
| Containerisation | Docker Compose | - |
| Langage | Python | 3.11 |

---

## Sources de Donnees

### Football-Data.org API
- Matchs des ligues : Premier League, La Liga, Ligue 1
- Resultats mi-temps et temps plein
- Informations equipes et competitions
- Rate limit : 10 requetes/minute (tier gratuit)

### OpenWeather API
- Temperature et conditions meteo
- Donnees par ville de match

### Transfermarkt (Web Scraping)
- Valeurs de marche des equipes
- Donnees financieres

---

## Installation

### Prerequis

- Docker et Docker Compose
- PostgreSQL 15 (local ou Docker)
- Python 3.9+
- Cles API :
  - [Football-Data.org](https://www.football-data.org/) (gratuit)
  - [OpenWeather](https://openweathermap.org/api) (gratuit)

### 1. Cloner le projet

```bash
git clone https://github.com/your-repo/DATA705-BIG-DATA.git
cd DATA705-BIG-DATA
```

### 2. Configuration

```bash
# Copier le fichier d'environnement
cp .env.example .env

# Editer avec vos credentials
# FOOTBALL_API_TOKEN=votre_token
# OPENWEATHER_API_KEY=votre_cle
# DB_PASS=votre_mot_de_passe
```

### 3. Base de donnees PostgreSQL

```sql
CREATE DATABASE football_stats_db;
CREATE USER football_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE football_stats_db TO football_user;

\c football_stats_db
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
GRANT ALL ON SCHEMA bronze, silver, gold TO football_user;
```

### 4. Demarrer les services

```bash
# Demarrer tous les services (Airflow, Elasticsearch, Kibana)
docker-compose up -d

# Verifier les services
docker-compose ps
```

### Acces aux interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8080 | admin / admin |
| Kibana | http://localhost:5601 | - |
| Elasticsearch | http://localhost:9200 | - |
| Streamlit | http://localhost:8501 | - |

---

## Utilisation

### Extraction manuelle

```bash
# Extraire les donnees de match
python extractor/foot_data.py

# Extraire les donnees meteo
python extractor/fetch_weather.py

# Extraire les valeurs Transfermarkt
python extractor/fetch_transfermarkt.py

# Charger dans PostgreSQL
python extractor/load_postgres.py

# Charger dans Elasticsearch
python extractor/load_elasticsearch.py
```

### Transformations DBT

```bash
cd dbt_football/stat_foot

# Installer les dependances DBT
dbt deps --profiles-dir ~/.dbt

# Executer les transformations
dbt run --profiles-dir ~/.dbt

# Lancer les tests
dbt test --profiles-dir ~/.dbt

# Generer la documentation
dbt docs generate --profiles-dir ~/.dbt
```

### Dashboard Streamlit

```bash
streamlit run dashboard/app.py
```

---

## Structure du Projet

```
DATA705-BIG-DATA/
├── airflow/
│   └── dags/
│       └── football_elt_pipeline_v2.py    # DAG Airflow principal
├── config/
│   └── settings.py                         # Configuration centralisee
├── dashboard/
│   ├── app.py                              # Application Streamlit
│   └── requirements.txt
├── dbt_football/
│   └── stat_foot/
│       ├── models/
│       │   ├── silver/                     # Modeles de staging
│       │   │   ├── stg_matches.sql
│       │   │   ├── stg_teams.sql
│       │   │   ├── stg_weather.sql
│       │   │   └── stg_team_values.sql
│       │   └── gold/                       # Modeles business
│       │       ├── fact_matches.sql
│       │       ├── dim_teams.sql
│       │       ├── agg_team_performance.sql
│       │       ├── mart_league_standings.sql
│       │       └── mart_team_form.sql
│       └── tests/                          # Tests de qualite
├── extractor/
│   ├── foot_data.py                        # Extraction Football API
│   ├── fetch_weather.py                    # Extraction meteo
│   ├── fetch_transfermarkt.py              # Extraction valeurs marche
│   ├── load_postgres.py                    # Chargement PostgreSQL
│   ├── load_elasticsearch.py               # Chargement Elasticsearch
│   ├── analytics_queries.py                # Requetes analytiques ES
│   └── setup_kibana_dashboard.py           # Configuration Kibana
├── docker-compose.yaml                     # Services Docker
├── Dockerfile                              # Image Airflow custom
├── requirement.txt                         # Dependances Python
└── README.md
```

---

## Tests de Qualite

### Tests DBT

| Type | Description |
|------|-------------|
| Unicite | Verification des IDs uniques |
| Non-null | Champs obligatoires remplis |
| Valeurs acceptees | Status de match valides |
| Custom | Scores valides, mi-temps <= temps plein, dates raisonnables |

```bash
# Executer tous les tests
dbt test --profiles-dir ~/.dbt

# Resultat attendu : PASS=9 ERROR=0
```

### Fichiers de tests custom

- `test_valid_scores.sql` : Verifie que les scores sont positifs
- `test_halftime_vs_fulltime.sql` : Verifie coherence mi-temps/temps plein
- `test_reasonable_dates.sql` : Verifie les dates dans une plage raisonnable

---

## Licence

MIT License
