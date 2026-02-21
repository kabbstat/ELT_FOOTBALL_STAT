# 🧪 Guide de Test - Football ELT Pipeline

## Tests Rapides (5 minutes)

### 1. Test de Configuration

```bash
# Vérifier la configuration
python config/settings.py
```

**Résultat attendu** : Affichage de la configuration et "✅ Configuration is valid"

### 2. Test d'Extraction (sans API)

```bash
# Créer un fichier de test
python -c "
import pandas as pd
from pathlib import Path

# Créer des données de test
data = {
    'id': [1, 2, 3],
    'hometeam_name': ['Team A', 'Team B', 'Team C'],
    'awayteam_name': ['Team X', 'Team Y', 'Team Z'],
    'score_fulltime_home': [2, 1, 3],
    'score_fulltime_away': [1, 1, 0]
}
df = pd.DataFrame(data)

# Sauvegarder
Path('data/landing').mkdir(parents=True, exist_ok=True)
df.to_parquet('data/landing/test_matches.parquet')
print('✅ Fichier de test créé')
"
```

### 3. Test de Chargement PostgreSQL

```bash
# Tester la connexion à la base de données
python extractor/test_db_connexion.py
```

## Tests Complets (30 minutes)

### Étape 1 : Setup et Validation

```bash
# Exécuter le script de setup
python setup.py

# Avec installation des dépendances
python setup.py --install
```

### Étape 2 : Test d'Extraction Réelle

```bash
# Activer l'environnement virtuel
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# Exécuter l'extraction améliorée
python extractor/foot_data_enhanced.py
```

**Vérifications** :
- ✅ Logs dans `logs/extraction.log`
- ✅ Fichiers créés dans `data/landing/`
- ✅ Pas d'erreurs critiques

### Étape 3 : Test de Chargement

```bash
# Charger les données dans PostgreSQL
python extractor/load_postgres_enhanced.py
```

**Vérifications** :
```sql
-- Vérifier les données chargées
psql -U football_user -d football_stats_db

-- Compter les lignes
SELECT COUNT(*) FROM bronze.matches;

-- Voir un échantillon
SELECT * FROM bronze.matches LIMIT 5;
```

### Étape 4 : Test DBT

```bash
cd dbt_football/stat_foot

# Test de connexion
dbt debug --profiles-dir ~/.dbt

# Installer les dépendances
dbt deps --profiles-dir ~/.dbt

# Exécuter les transformations
dbt run --profiles-dir ~/.dbt

# Exécuter les tests
dbt test --profiles-dir ~/.dbt
```

**Vérifications** :
```sql
-- Vérifier les tables créées
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_schema IN ('silver', 'gold')
ORDER BY table_schema, table_name;

-- Vérifier les données Silver
SELECT COUNT(*) FROM silver.stg_matches;
SELECT COUNT(*) FROM silver.stg_teams;

-- Vérifier les données Gold
SELECT COUNT(*) FROM gold.fact_matches;
SELECT COUNT(*) FROM gold.dim_teams;
SELECT * FROM gold.agg_team_performance LIMIT 10;
```

### Étape 5 : Test du Dashboard

```bash
cd dashboard

# Installer les dépendances
pip install -r requirements.txt

# Lancer le dashboard
streamlit run app.py
```

**Vérifications** :
- ✅ Dashboard accessible sur http://localhost:8501
- ✅ Données affichées dans toutes les vues
- ✅ Graphiques interactifs fonctionnent

### Étape 6 : Test Airflow

```bash
# Retour à la racine
cd ../..

# Démarrer Airflow
docker-compose up -d

# Attendre 2-3 minutes puis vérifier
docker-compose ps
```

**Vérifications** :
1. Accéder à http://localhost:8080
2. Login : admin / admin
3. Activer le DAG `football_elt_pipeline_enhanced`
4. Déclencher manuellement
5. Surveiller l'exécution

## Tests Unitaires

### Test 1 : Configuration

```python
# test_config.py
from config.settings import Config

def test_config():
    config = Config()
    assert config.database.database == 'football_stats_db'
    assert config.api.base_url
    print("✅ Configuration test passed")

if __name__ == "__main__":
    test_config()
```

### Test 2 : Extraction

```python
# test_extraction.py
from extractor.foot_data_enhanced import FootballDataExtractor
import pandas as pd

def test_extractor():
    extractor = FootballDataExtractor()
    
    # Test avec des données mockées
    # Note: nécessite une vraie API key pour test complet
    print("✅ Extractor initialized")
    
    extractor.close()
    print("✅ Extractor closed properly")

if __name__ == "__main__":
    test_extractor()
```

### Test 3 : Loading

```python
# test_loading.py
from extractor.load_postgres_enhanced import PostgreSQLLoader

def test_loader():
    loader = PostgreSQLLoader()
    
    # Test de connexion
    stats = loader.get_table_stats('bronze', 'matches')
    print(f"Bronze matches: {stats}")
    
    loader.close()
    print("✅ Loader test passed")

if __name__ == "__main__":
    test_loader()
```

## Tests de Qualité de Données

### Via DBT

```bash
cd dbt_football/stat_foot

# Tous les tests
dbt test --profiles-dir ~/.dbt

# Tests spécifiques
dbt test --select stg_matches --profiles-dir ~/.dbt
dbt test --select test_valid_scores --profiles-dir ~/.dbt
```

### Tests SQL Manuels

```sql
-- Test 1: Pas de scores négatifs
SELECT COUNT(*) as invalid_scores
FROM gold.fact_matches
WHERE fulltime_home_score < 0 OR fulltime_away_score < 0;
-- Résultat attendu: 0

-- Test 2: Mi-temps <= Temps plein
SELECT COUNT(*) as invalid_halftime
FROM gold.fact_matches
WHERE halftime_home_score > fulltime_home_score
   OR halftime_away_score > fulltime_away_score;
-- Résultat attendu: 0

-- Test 3: Dates cohérentes
SELECT COUNT(*) as invalid_dates
FROM gold.fact_matches
WHERE match_date > CURRENT_DATE + INTERVAL '30 days'
   OR match_date < '2020-01-01';
-- Résultat attendu: 0

-- Test 4: Pas de doublons
SELECT match_id, COUNT(*) 
FROM gold.fact_matches 
GROUP BY match_id 
HAVING COUNT(*) > 1;
-- Résultat attendu: 0 rows

-- Test 5: Intégrité référentielle
SELECT COUNT(*) 
FROM gold.fact_matches f
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_teams t 
    WHERE t.team_id = f.home_team_id
);
-- Résultat attendu: 0
```

## Tests de Performance

### Test 1 : Temps d'Extraction

```bash
time python extractor/foot_data_enhanced.py
```

**Attendu** : 2-3 minutes pour 3 ligues

### Test 2 : Temps de Loading

```bash
time python extractor/load_postgres_enhanced.py
```

**Attendu** : 30-60 secondes

### Test 3 : Temps de Transformation DBT

```bash
cd dbt_football/stat_foot
time dbt run --profiles-dir ~/.dbt
```

**Attendu** : 1-2 minutes

### Test 4 : Performance du Dashboard

```python
# Dans le dashboard Streamlit, ouvrir la console et vérifier :
# - Temps de chargement initial < 2 secondes
# - Temps de rafraîchissement < 1 seconde (avec cache)
```

## Checklist de Validation Complète

### ✅ Infrastructure
- [ ] PostgreSQL accessible
- [ ] Docker fonctionnel
- [ ] Python 3.9+ installé
- [ ] Variables d'environnement configurées

### ✅ Extraction
- [ ] API token valide
- [ ] Extraction sans erreur
- [ ] Fichiers Parquet créés
- [ ] Logs d'extraction propres

### ✅ Loading
- [ ] Connexion DB réussie
- [ ] Données chargées dans Bronze
- [ ] Schémas créés
- [ ] Stats cohérentes

### ✅ Transformation DBT
- [ ] `dbt debug` réussi
- [ ] `dbt run` sans erreur
- [ ] `dbt test` tous passés
- [ ] Tables Silver/Gold créées

### ✅ Qualité des Données
- [ ] Tous les tests DBT passent
- [ ] Pas de valeurs nulles inattendues
- [ ] Dates cohérentes
- [ ] Pas de doublons

### ✅ Dashboard
- [ ] Streamlit démarre
- [ ] Toutes les vues fonctionnent
- [ ] Graphiques affichés
- [ ] Filtres fonctionnels

### ✅ Orchestration Airflow
- [ ] Airflow accessible
- [ ] DAG visible
- [ ] Exécution manuelle réussie
- [ ] Toutes les tâches en succès

## Résolution de Problèmes Courants

### Erreur : "FOOTBALL_API_TOKEN not found"

```bash
# Vérifier .env
cat .env | grep FOOTBALL_API_TOKEN

# Si vide, ajouter votre token
echo "FOOTBALL_API_TOKEN=votre_token_ici" >> .env
```

### Erreur : "Connection refused" (PostgreSQL)

```bash
# Vérifier que PostgreSQL est démarré
# Windows:
net start postgresql-x64-15

# Linux:
sudo systemctl start postgresql

# Vérifier la connexion
psql -U football_user -d football_stats_db -c "SELECT 1;"
```

### Erreur : DBT "Could not connect"

```bash
# Vérifier le fichier profiles.yml
cat ~/.dbt/profiles.yml

# Tester manuellement
psql -h localhost -p 5432 -U football_user -d football_stats_db
```

### Dashboard : "No data"

```sql
-- Vérifier que les tables Gold existent et ont des données
SELECT 
    'fact_matches' as table_name, COUNT(*) as row_count 
FROM gold.fact_matches
UNION ALL
SELECT 'dim_teams', COUNT(*) FROM gold.dim_teams
UNION ALL
SELECT 'agg_team_performance', COUNT(*) FROM gold.agg_team_performance;
```

## Script de Test Automatique

```bash
#!/bin/bash
# run_tests.sh

echo "🧪 Starting Football ELT Tests..."

# Test 1: Configuration
echo "1. Testing configuration..."
python config/settings.py || exit 1

# Test 2: Database connection
echo "2. Testing database..."
psql -U football_user -d football_stats_db -c "SELECT 1;" || exit 1

# Test 3: Extraction (skip if no API token)
if [ -n "$FOOTBALL_API_TOKEN" ]; then
    echo "3. Testing extraction..."
    python extractor/foot_data_enhanced.py || exit 1
else
    echo "3. Skipping extraction (no API token)"
fi

# Test 4: DBT
echo "4. Testing DBT..."
cd dbt_football/stat_foot
dbt debug --profiles-dir ~/.dbt || exit 1
dbt run --profiles-dir ~/.dbt || exit 1
dbt test --profiles-dir ~/.dbt || exit 1

echo "✅ All tests passed!"
```

**Utilisation** :
```bash
chmod +x run_tests.sh
./run_tests.sh
```

---

## 🎯 Tests Recommandés par Ordre

1. **Setup** : `python setup.py`
2. **Configuration** : `python config/settings.py`
3. **DB Connection** : `python extractor/test_db_connexion.py`
4. **Extraction** : `python extractor/foot_data_enhanced.py`
5. **Loading** : `python extractor/load_postgres_enhanced.py`
6. **DBT** : `cd dbt_football/stat_foot && dbt run && dbt test`
7. **Dashboard** : `cd dashboard && streamlit run app.py`
8. **Airflow** : `docker-compose up -d`

Bonne chance avec les tests ! 🚀
