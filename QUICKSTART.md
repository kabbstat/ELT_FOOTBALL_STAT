# Guide de Démarrage Rapide

## Installation Rapide (15 minutes)

### 1. Configuration Initiale

```bash
# Cloner le repo
git clone https://github.com/kabbstat/ELT_FOOTBALL_STAT.git
cd ELT_FOOTBALL_STAT

# Configuration
cp .env.example .env
# Éditer .env avec vos credentials
```

### 2. Base de Données

```bash
# Créer la DB
psql -U postgres -c "CREATE DATABASE football_stats_db;"
psql -U postgres -c "CREATE USER football_user WITH PASSWORD 'yourpassword';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE football_stats_db TO football_user;"

# Créer les schémas
psql -U football_user -d football_stats_db << EOF
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
EOF
```

### 3. Première Extraction

```bash
# Installer les dépendances
pip install -r requirement.txt

# Exécuter l'extraction
python extractor/foot_data_enhanced.py

# Charger dans PostgreSQL
python extractor/load_postgres_enhanced.py
```

### 4. Transformations DBT

```bash
cd dbt_football/stat_foot
dbt run --profiles-dir ~/.dbt
dbt test --profiles-dir ~/.dbt
```

### 5. Lancer le Dashboard

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Accéder à `http://localhost:8501` 🎉

## Commandes Essentielles

```bash
# Démarrer Airflow
docker-compose up -d

# Arrêter Airflow
docker-compose down

# Voir les logs
docker-compose logs -f

# Tester DBT
dbt test --profiles-dir ~/.dbt

# Lancer le dashboard
streamlit run dashboard/app.py

# Exécuter l'extraction manuellement
python extractor/foot_data_enhanced.py
```

## Structure des Données

### Bronze Layer (Raw)
- `bronze.matches` : Tous les matchs bruts
- `bronze.competitions` : Informations des compétitions

### Silver Layer (Cleaned)
- `silver.stg_matches` : Matchs nettoyés
- `silver.stg_teams` : Équipes standardisées

### Gold Layer (Business)
- `gold.fact_matches` : Table de faits des matchs
- `gold.dim_teams` : Dimension des équipes
- `gold.agg_team_performance` : Agrégations par équipe
- `gold.agg_competition_stats` : Stats par compétition

## Requêtes SQL Utiles

```sql
-- Voir les matchs récents
SELECT * FROM gold.fact_matches 
ORDER BY match_date DESC 
LIMIT 10;

-- Classement d'une compétition
SELECT team_name, total_points, goal_difference
FROM gold.agg_team_performance
WHERE competition_code = 'PL'
ORDER BY total_points DESC;

-- Stats par compétition
SELECT * FROM gold.agg_competition_stats;
```

## Vérification de Santé

```bash
# Vérifier PostgreSQL
psql -U football_user -d football_stats_db -c "SELECT 1;"

# Vérifier Airflow
curl http://localhost:8080/health

# Vérifier les données
psql -U football_user -d football_stats_db -c "SELECT COUNT(*) FROM gold.fact_matches;"
```

## Support

En cas de problème, consulter le [README complet](README.md) section Troubleshooting.
