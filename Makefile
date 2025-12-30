# Makefile for Football ELT Project
# Facilite les commandes courantes

.PHONY: help install setup-db start-airflow stop-airflow run-extraction run-dbt run-dashboard test clean

help:
	@echo "Football ELT Pipeline - Commandes disponibles:"
	@echo ""
	@echo "  make install        - Installer les dépendances Python"
	@echo "  make setup-db       - Créer la base de données et les schémas"
	@echo "  make start-airflow  - Démarrer Airflow avec Docker"
	@echo "  make stop-airflow   - Arrêter Airflow"
	@echo "  make run-extraction - Exécuter l'extraction de données"
	@echo "  make run-dbt        - Exécuter les transformations DBT"
	@echo "  make run-dashboard  - Lancer le dashboard Streamlit"
	@echo "  make test           - Exécuter les tests DBT"
	@echo "  make clean          - Nettoyer les fichiers temporaires"
	@echo "  make logs           - Voir les logs Airflow"

install:
	@echo "Installation des dépendances..."
	pip install -r requirement.txt
	@echo "✅ Installation terminée"

setup-db:
	@echo "Configuration de la base de données..."
	@psql -U postgres -c "CREATE DATABASE football_stats_db;" || echo "DB existe déjà"
	@psql -U postgres -c "CREATE USER football_user WITH PASSWORD 'football123';" || echo "User existe déjà"
	@psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE football_stats_db TO football_user;"
	@psql -U football_user -d football_stats_db -c "CREATE SCHEMA IF NOT EXISTS bronze;"
	@psql -U football_user -d football_stats_db -c "CREATE SCHEMA IF NOT EXISTS silver;"
	@psql -U football_user -d football_stats_db -c "CREATE SCHEMA IF NOT EXISTS gold;"
	@echo "✅ Base de données configurée"

start-airflow:
	@echo "Démarrage d'Airflow..."
	docker-compose up -d
	@echo "✅ Airflow démarré sur http://localhost:8080"

stop-airflow:
	@echo "Arrêt d'Airflow..."
	docker-compose down
	@echo "✅ Airflow arrêté"

logs:
	docker-compose logs -f

run-extraction:
	@echo "Extraction des données..."
	python extractor/foot_data_enhanced.py
	python extractor/load_postgres_enhanced.py
	@echo "✅ Extraction terminée"

run-dbt:
	@echo "Exécution des transformations DBT..."
	cd dbt_football/stat_foot && dbt run --profiles-dir ~/.dbt
	@echo "✅ Transformations terminées"

test:
	@echo "Exécution des tests DBT..."
	cd dbt_football/stat_foot && dbt test --profiles-dir ~/.dbt
	@echo "✅ Tests terminés"

run-dashboard:
	@echo "Lancement du dashboard..."
	cd dashboard && streamlit run app.py

clean:
	@echo "Nettoyage des fichiers temporaires..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete
	cd dbt_football/stat_foot && dbt clean
	@echo "✅ Nettoyage terminé"

validate-config:
	@echo "Validation de la configuration..."
	python config/settings.py
	@echo "✅ Configuration validée"
