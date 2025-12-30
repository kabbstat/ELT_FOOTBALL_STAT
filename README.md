# ⚽ Football Statistics ELT Pipeline

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Airflow](https://img.shields.io/badge/Airflow-2.7-017CEE?logo=apache-airflow&logoColor=white)](https://airflow.apache.org)
[![dbt](https://img.shields.io/badge/dbt-1.7-FF694B?logo=dbt&logoColor=white)](https://getdbt.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docker.com)

> **Production-grade ELT pipeline** for European football statistics analysis using modern data engineering practices.

<p align="center">
  <img src="https://img.shields.io/badge/Status-Production-success" alt="Status">
  <img src="https://img.shields.io/badge/Leagues-3-blue" alt="Leagues">
  <img src="https://img.shields.io/badge/Matches-2000+-green" alt="Matches">
</p>

---

## 🎯 Overview

End-to-end data pipeline extracting football match data from **Premier League**, **La Liga**, and **Ligue 1**, transforming it through a **medallion architecture** (Bronze → Silver → Gold), and visualizing insights via an interactive dashboard.

### Key Features

| Feature | Description |
|---------|-------------|
| **Automated Extraction** | Weekly data pulls from Football-Data.org API |
| **Medallion Architecture** | Bronze (raw) → Silver (cleaned) → Gold (aggregated) |
| **Orchestration** | Apache Airflow with dependency management & monitoring |
| **Data Quality** | 9 automated DBT tests (uniqueness, not-null, custom validations) |
| **Interactive Dashboard** | 5 analytical views with Streamlit & Plotly |

---

## 🏗️ Architecture

```
┌──────────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Football API    │────▶│   BRONZE    │────▶│   SILVER    │────▶│    GOLD     │
│  (Data Source)   │     │  Raw Data   │     │  Cleaned    │     │ Aggregated  │
└──────────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                               │                                        │
                               │            Apache Airflow              │
                               │◀──────────────────────────────────────▶│
                               │              DBT Core                  │
                                                                        │
                                                                        ▼
                                                               ┌─────────────────┐
                                                               │   Dashboard     │
                                                               │   (Streamlit)   │
                                                               └─────────────────┘
```

### Data Layers

| Layer | Schema | Purpose | Models |
|-------|--------|---------|--------|
| **Bronze** | `bronze` | Raw data storage | `matches` |
| **Silver** | `silver` | Cleaned & standardized | `stg_matches`, `stg_teams` |
| **Gold** | `gold` | Business aggregations | `fact_matches`, `dim_teams`, `agg_team_performance`, `agg_competition_stats` |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Orchestration** | Apache Airflow 2.7 |
| **Transformation** | dbt-core 1.7 |
| **Database** | PostgreSQL 15 |
| **Visualization** | Streamlit + Plotly |
| **Containerization** | Docker Compose |
| **Language** | Python 3.11 |

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- PostgreSQL 15
- Python 3.9+
- [Football-Data.org](https://www.football-data.org/) API key (free tier)

### 1. Clone & Configure

```bash
git clone https://github.com/kabbstat/ELT_FOOTBALL_STAT.git
cd ELT_FOOTBALL_STAT

# Create environment file
cp .env.example .env
# Edit .env with your credentials
```

### 2. Database Setup

```sql
-- Connect to PostgreSQL
CREATE DATABASE football_stats_db;
CREATE USER football_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE football_stats_db TO football_user;

-- Create schemas
\c football_stats_db
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
GRANT ALL ON SCHEMA bronze, silver, gold TO football_user;
```

### 3. Start Services

```bash
# Start Airflow
docker-compose up -d

# Access Airflow UI: http://localhost:8080
# Credentials: admin / admin
```

### 4. Run Pipeline

```bash
# Manual extraction
python extractor/foot_data.py
python extractor/load_postgres.py

# DBT transformations
cd dbt_football/stat_foot
dbt run --profiles-dir ~/.dbt
dbt test --profiles-dir ~/.dbt

# Launch dashboard
streamlit run dashboard/app.py
# Access: http://localhost:8501
```

---

## 📁 Project Structure

```
football_stat/
├── airflow/dags/           # Airflow DAG definitions
├── extractor/              # Data extraction & loading scripts
├── dbt_football/stat_foot/ # DBT project
│   ├── models/
│   │   ├── silver/         # Staging models
│   │   └── gold/           # Business models
│   └── tests/              # Custom data tests
├── dashboard/              # Streamlit application
├── data/                   # Parquet & JSON storage
├── docker-compose.yaml     # Container orchestration
└── requirement.txt         # Python dependencies
```

---

## 📊 Dashboard Views

| View | Description |
|------|-------------|
| **Overview** | KPIs, recent matches, competition distribution |
| **Competition Analysis** | Stats by league, home advantage, goal trends |
| **Team Performance** | Rankings, top scorers, best defenses |
| **Match Analysis** | High-scoring matches, goal distribution |
| **Team Deep Dive** | Detailed stats for selected team |

---

## 🧪 Data Quality

### DBT Tests

- **Source Tests**: ID uniqueness, not-null constraints, accepted values
- **Custom Tests**: Valid scores, halftime ≤ fulltime, reasonable dates

```bash
# Run all tests
dbt test --profiles-dir ~/.dbt
# Expected: PASS=9 ERROR=0
```

---

## 📈 Roadmap

- [ ] CI/CD with GitHub Actions
- [ ] Additional leagues (Bundesliga, Serie A)
- [ ] Match prediction ML models
- [ ] Cloud deployment (AWS/GCP)
- [ ] REST API for data access

---

## 👨‍💻 Author

**Kabbstat** — Data Engineer

[![GitHub](https://img.shields.io/badge/GitHub-kabbstat-181717?logo=github)](https://github.com/kabbstat)

---

## 📄 License

MIT License — feel free to use this project for learning and development.

---

<p align="center">
  <b>⭐ Star this repo if you found it useful!</b>
</p>
