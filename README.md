# ⚽ Football ELT Pipeline - Production Grade

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Airflow](https://img.shields.io/badge/Airflow-2.7+-red.svg)
![DBT](https://img.shields.io/badge/DBT-1.6+-orange.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)

Un pipeline ELT complet et de niveau production pour l'extraction, transformation et visualisation de statistiques de football (Premier League, La Liga, Ligue 1).

## 📋 Table des Matières

- [Architecture](#architecture)
- [Fonctionnalités](#fonctionnalités)
- [Stack Technique](#stack-technique)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Structure du Projet](#structure-du-projet)
- [Qualité des Données](#qualité-des-données)
- [Dashboard](#dashboard)
- [Bonnes Pratiques](#bonnes-pratiques)

## 🏗️ Architecture

Ce projet suit une **architecture médaillée** (Bronze/Silver/Gold) avec les bonnes pratiques de data engineering :

```
┌─────────────────┐
│   Football API  │
│  (Data Source)  │
└────────┬────────┘
         │
         ▼
    [EXTRACT]
         │
         ▼
┌─────────────────┐
│  Bronze Layer   │ ← Raw data (JSON → Parquet → PostgreSQL)
│   (PostgreSQL)  │
└────────┬────────┘
         │
         ▼
    [TRANSFORM]
      (DBT)
         │
    ┌────┴────┐
    ▼         ▼
┌──────┐  ┌──────┐
│Silver│  │ Gold │ ← Business logic & aggregations
└───┬──┘  └──┬───┘
    │        │
    ▼        ▼
┌─────────────────┐
│   Dashboard     │ ← Streamlit visualization
│  (Streamlit)    │
└─────────────────┘
```

### Couches de Données

- **Bronze** : Données brutes extraites de l'API
- **Silver** : Données nettoyées et standardisées (`stg_matches`, `stg_teams`)
- **Gold** : Agrégations et métriques business (`fact_matches`, `dim_teams`, `agg_team_performance`, `agg_competition_stats`)

## ✨ Fonctionnalités

### Pipeline ELT

- ✅ **Extraction automatisée** depuis Football-Data.org API
- ✅ **Gestion d'erreurs robuste** avec retry logic
- ✅ **Rate limiting** et respect des quotas API
- ✅ **Logging complet** pour monitoring et debugging
- ✅ **Idempotence** : réexécution sûre du pipeline
- ✅ **Tests de qualité de données** avec DBT
- ✅ **Orchestration Airflow** avec TaskGroups et monitoring

### Transformations DBT

- ✅ Architecture Bronze → Silver → Gold
- ✅ Tests de données (unicité, non-null, valeurs acceptées)
- ✅ Tests personnalisés (scores valides, dates cohérentes)
- ✅ Documentation générée automatiquement
- ✅ Incrémental loading support

### Dashboard

- ✅ **5 vues analytiques** :
  - Vue d'ensemble (métriques clés)
  - Analyse par compétition
  - Performance des équipes
  - Analyse des matchs
  - Deep dive par équipe
- ✅ Visualisations interactives (Plotly)
- ✅ Cache des données pour performance
- ✅ Responsive design

## 🛠️ Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Orchestration | Apache Airflow | 2.7+ |
| Transformation | dbt-core | 1.6+ |
| Base de données | PostgreSQL | 15 |
| Dashboard | Streamlit | 1.28+ |
| Containerization | Docker | 20.10+ |
| Langage | Python | 3.9+ |
| API | Football-Data.org | v4 |

## 📦 Installation

### Prérequis

- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 15
- Git
- Compte Football-Data.org (clé API)

### 1. Cloner le Repository

```bash
git clone https://github.com/kabbstat/ELT_FOOTBALL_STAT.git
cd ELT_FOOTBALL_STAT
```

### 2. Configuration de l'Environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer avec vos credentials
nano .env
```

Remplir les variables suivantes :
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=football_stats_db
DB_USER=football_user
DB_PASS=votre_password
FOOTBALL_API_TOKEN=votre_api_token
```

### 3. Créer la Base de Données PostgreSQL

```bash
# Se connecter à PostgreSQL
psql -U postgres

# Créer la base de données et l'utilisateur
CREATE DATABASE football_stats_db;
CREATE USER football_user WITH PASSWORD 'votre_password';
GRANT ALL PRIVILEGES ON DATABASE football_stats_db TO football_user;

# Créer les schémas
\c football_stats_db
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
GRANT ALL ON SCHEMA bronze, silver, gold TO football_user;
```

### 4. Installer les Dépendances Python

```bash
# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer les dépendances
pip install -r requirement.txt
```

### 5. Démarrer Airflow avec Docker

```bash
# Construire et démarrer les conteneurs
docker-compose up -d

# Vérifier les logs
docker-compose logs -f
```

Airflow sera accessible sur `http://localhost:8080`
- Username: `admin`
- Password: `admin`

### 6. Configurer DBT

```bash
# Tester la connexion DBT
cd dbt_football/stat_foot
dbt debug --profiles-dir ~/.dbt

# Installer les dépendances DBT
dbt deps --profiles-dir ~/.dbt
```

## ⚙️ Configuration

### Configuration Airflow

Le DAG est configuré pour s'exécuter **hebdomadairement** (chaque samedi).

Pour modifier :
```python
# airflow/dags/football_elt_dag_enhanced.py
schedule_interval='@weekly'  # Modifier selon vos besoins
```

### Configuration DBT

Les profils DBT sont dans `~/.dbt/profiles.yml` :

```yaml
stat_foot:
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: football_user
      password: votre_password
      dbname: football_stats_db
      schema: gold
      threads: 4
  target: dev
```

### Configuration API

Limites du free tier Football-Data.org :
- 10 requêtes/minute
- 3 compétitions maximum
- Données historiques limitées

## 🚀 Utilisation

### Exécution Manuelle de l'Extraction

```bash
# Activer l'environnement
source venv/bin/activate

# Exécuter l'extraction
python extractor/foot_data_enhanced.py

# Charger dans PostgreSQL
python extractor/load_postgres_enhanced.py
```

### Exécution des Transformations DBT

```bash
cd dbt_football/stat_foot

# Nettoyer les anciens artifacts
dbt clean

# Installer les dépendances
dbt deps

# Exécuter les transformations
dbt run --profiles-dir ~/.dbt

# Exécuter les tests
dbt test --profiles-dir ~/.dbt

# Générer la documentation
dbt docs generate --profiles-dir ~/.dbt
dbt docs serve  # Ouvre sur http://localhost:8080
```

### Lancer le Dashboard

```bash
cd dashboard

# Installer les dépendances
pip install -r requirements.txt

# Lancer Streamlit
streamlit run app.py
```

Le dashboard sera accessible sur `http://localhost:8501`

### Exécution via Airflow

1. Accéder à Airflow : `http://localhost:8080`
2. Activer le DAG `football_elt_pipeline_enhanced`
3. Déclencher manuellement ou attendre l'exécution planifiée
4. Monitorer l'exécution dans l'interface Airflow

## 📁 Structure du Projet

```
football_stat/
├── airflow/
│   ├── dags/
│   │   ├── football_elt_dag.py              # DAG original
│   │   └── football_elt_dag_enhanced.py     # DAG optimisé ✨
│   ├── logs/                                 # Logs Airflow
│   └── plugins/
│
├── extractor/
│   ├── foot_data.py                         # Extraction original
│   ├── foot_data_enhanced.py                # Extraction améliorée ✨
│   ├── load_postgres.py                     # Loading original
│   └── load_postgres_enhanced.py            # Loading amélioré ✨
│
├── dbt_football/
│   └── stat_foot/
│       ├── models/
│       │   ├── sources.yml                  # Source definitions
│       │   ├── silver/
│       │   │   ├── stg_matches.sql          # Staging matches ✨
│       │   │   ├── stg_teams.sql            # Staging teams ✨
│       │   │   └── schema.yaml
│       │   └── gold/
│       │       ├── fact_matches.sql         # Fact table ✨
│       │       ├── dim_teams.sql            # Dimension table ✨
│       │       ├── agg_team_performance.sql # Team stats ✨
│       │       ├── agg_competition_stats.sql # Competition stats ✨
│       │       └── schema.yaml
│       ├── tests/
│       │   ├── test_valid_scores.sql        # Custom test ✨
│       │   ├── test_halftime_vs_fulltime.sql # Custom test ✨
│       │   └── test_reasonable_dates.sql    # Custom test ✨
│       └── dbt_project.yml
│
├── dashboard/
│   ├── app.py                               # Streamlit dashboard ✨
│   └── requirements.txt
│
├── config/
│   └── settings.py                          # Configuration centralisée ✨
│
├── data/
│   ├── landing/                             # Données extraites (Parquet)
│   └── raw/                                 # Données brutes (JSON)
│
├── logs/                                    # Logs applicatifs
│
├── docker-compose.yaml                      # Orchestration Docker
├── Dockerfile                               # Image Docker
├── requirement.txt                          # Dépendances Python
├── .env.example                             # Template configuration ✨
├── .gitignore
└── README.md                                # Cette documentation ✨
```

## 🧪 Qualité des Données

### Tests DBT Implémentés

#### Tests de Base (sources.yml & schema.yaml)
- Unicité des IDs
- Non-nullité des champs critiques
- Valeurs acceptées pour les statuts

#### Tests Personnalisés

1. **test_valid_scores.sql** : Vérifie que les scores sont positifs
2. **test_halftime_vs_fulltime.sql** : Valide que score mi-temps ≤ score final
3. **test_reasonable_dates.sql** : Vérifie la cohérence des dates

### Monitoring et Logging

- **Logs d'extraction** : `logs/extraction.log`
- **Logs de loading** : `logs/loading.log`
- **Logs Airflow** : `airflow/logs/`
- **Logs DBT** : `dbt_football/stat_foot/logs/`

### Métriques de Qualité

Le DAG effectue automatiquement :
- Validation des fichiers extraits
- Comptage des enregistrements
- Vérification de la fraîcheur des données
- Tests de qualité DBT

## 📊 Dashboard

### Vues Disponibles

#### 1. Overview (Vue d'ensemble)
- Métriques clés : Total matches, goals, teams
- Matchs récents
- Distribution par compétition

#### 2. Competition Analysis
- Statistiques par compétition
- Home advantage analysis
- Tendances des buts
- Tableau détaillé

#### 3. Team Performance
- Classements par compétition
- Top scorers
- Meilleures défenses
- Tableau complet des standings

#### 4. Match Analysis
- Analyse des matchs à haut score
- Distribution des buts
- Performance domicile vs extérieur

#### 5. Team Deep Dive
- Analyse détaillée par équipe
- Statistiques de saison
- Forme récente
- Performance domicile/extérieur

### Captures d'écran

*Ajouter des screenshots du dashboard ici*

## 🎯 Bonnes Pratiques Implémentées

### Data Engineering

✅ **Architecture médaillée (Bronze/Silver/Gold)**
- Séparation claire des responsabilités
- Traçabilité des données
- Facilite le debugging

✅ **Idempotence**
- Réexécution sûre du pipeline
- Pas d'effets de bord

✅ **Error Handling**
- Try/except appropriés
- Logging détaillé
- Retry logic avec backoff

✅ **Configuration Management**
- Variables d'environnement
- Configuration centralisée
- Secrets management

✅ **Testing**
- Tests de qualité de données
- Tests de schéma
- Tests personnalisés

✅ **Monitoring**
- Logs structurés
- Métriques de pipeline
- Alertes sur échec

✅ **Documentation**
- Code documenté
- README complet
- Documentation DBT auto-générée

### Code Quality

✅ **Type Hints** pour Python 3.9+
✅ **Docstrings** pour toutes les fonctions
✅ **Logging** au lieu de print()
✅ **Classes** pour encapsulation
✅ **Configuration** séparée du code
✅ **Gestion des ressources** (with statements, close())

## 🔧 Troubleshooting

### Problème : API Rate Limit

```python
# Le code gère automatiquement avec retry
# Vérifier les logs : logs/extraction.log
```

### Problème : DBT Connection Error

```bash
# Tester la connexion
cd dbt_football/stat_foot
dbt debug --profiles-dir ~/.dbt

# Vérifier profiles.yml
cat ~/.dbt/profiles.yml
```

### Problème : Airflow DAG non visible

```bash
# Vérifier les logs
docker-compose logs airflow-scheduler

# Recharger les DAGs
docker-compose restart airflow-scheduler
```

### Problème : Dashboard ne charge pas les données

```python
# Vérifier la connexion DB
python -c "from dashboard.app import get_database_connection; get_database_connection()"

# Vérifier les données
psql -U football_user -d football_stats_db -c "SELECT COUNT(*) FROM gold.fact_matches;"
```

## 📈 Améliorations Futures

- [ ] CI/CD avec GitHub Actions
- [ ] Tests unitaires avec pytest
- [ ] Alertes email configurables
- [ ] Support pour plus de compétitions
- [ ] Machine Learning (prédictions de matchs)
- [ ] API REST pour exposer les données
- [ ] Déploiement cloud (AWS/GCP/Azure)
- [ ] Monitoring avec Prometheus/Grafana

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 License

Ce projet est sous licence MIT.

## 👨‍💻 Auteur

**Kabbstat**
- GitHub: [@kabbstat](https://github.com/kabbstat)
- LinkedIn: [Votre profil LinkedIn]

## 🙏 Remerciements

- [Football-Data.org](https://www.football-data.org/) pour l'API
- Apache Airflow community
- dbt Labs
- Streamlit team

---

⭐ Si ce projet vous a été utile, n'hésitez pas à lui donner une étoile !
