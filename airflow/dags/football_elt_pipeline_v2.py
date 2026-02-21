"""
Football ELT Pipeline V2 - Complete Data Pipeline
=================================================

This DAG implements a complete end-to-end data pipeline:
1. EXTRACTION: Football API + OpenWeather API + Transfermarkt
2. LOADING: PostgreSQL (Bronze layer) + Elasticsearch
3. TRANSFORMATION: DBT (Silver → Gold layers)
4. INDEXATION: Elasticsearch for Kibana dashboards

Architecture:
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │  Football API   │   │  OpenWeather    │   │  Transfermarkt  │
    └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
             │                     │                     │
             └──────────────┬──────┴──────────────┬──────┘
                            │                     │
                            ▼                     ▼
                    ┌───────────────┐     ┌───────────────┐
                    │   PostgreSQL  │     │ Elasticsearch │
                    │    (Bronze)   │     │               │
                    └───────┬───────┘     └───────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   DBT (Gold)  │
                    │  Combination  │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    Kibana     │
                    │   Dashboard   │
                    └───────────────┘

Schedule: Daily at 6:00 AM
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import sys
import os

# Add extractor path
sys.path.append('/opt/airflow/extractor')

# =============================================================================
# DAG Configuration
# =============================================================================

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
}

dag = DAG(
    'football_elt_pipeline_v2',
    default_args=default_args,
    description='Complete Football ELT Pipeline with 3 data sources + Elasticsearch',
    schedule_interval='0 6 * * *',  # Daily at 6 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['football', 'elt', 'dbt', 'elasticsearch', 'production'],
    doc_md=__doc__,
)


# =============================================================================
# TASK DEFINITIONS
# =============================================================================

# -----------------------------------------------------------------------------
# EXTRACTION TASKS
# -----------------------------------------------------------------------------

def extract_football_api(**context):
    """
    Extract football data from Football-Data.org API.
    Fetches competitions and matches for 2023-2024 seasons.
    """
    from foot_data import fetch_competitions, fetch_matches_save
    
    print("🏆 EXTRACTION: Football API")
    print("=" * 50)
    
    # Fetch competitions
    print("\n📋 Fetching competitions...")
    fetch_competitions()
    
    # Fetch matches for multiple seasons
    for season in [2023, 2024]:
        print(f"\n⚽ Fetching matches for season {season}...")
        fetch_matches_save(season=season)
    
    print("\n✅ Football API extraction completed!")


def extract_weather_api(**context):
    """
    Extract weather data from OpenWeather API.
    Fetches current weather for all major football cities.
    """
    from fetch_weather import fetch_all_weather_data
    
    print("🌤️ EXTRACTION: OpenWeather API")
    print("=" * 50)
    
    fetch_all_weather_data()
    
    print("\n✅ Weather extraction completed!")


def extract_transfermarkt(**context):
    """
    Extract team market values from Transfermarkt.
    Uses static data for reliability (web scraping can be blocked).
    """
    from fetch_transfermarkt import fetch_all_team_values
    
    print("💰 EXTRACTION: Transfermarkt")
    print("=" * 50)
    
    # Use static data (more reliable than scraping)
    fetch_all_team_values(use_static=True)
    
    print("\n✅ Transfermarkt extraction completed!")


# -----------------------------------------------------------------------------
# LOADING TASKS
# -----------------------------------------------------------------------------

def load_to_postgres(**context):
    """
    Load all extracted data into PostgreSQL Bronze layer.
    """
    from load_postgres import load_parquet_to_postgres
    
    print("📥 LOADING: PostgreSQL Bronze")
    print("=" * 50)
    
    # Load matches
    for season in [2023, 2024]:
        print(f"\n📊 Loading matches {season}...")
        load_parquet_to_postgres(schema='bronze', season=season)
    
    print("\n✅ PostgreSQL loading completed!")


def load_weather_to_postgres(**context):
    """
    Load weather data into PostgreSQL Bronze layer.
    """
    import pandas as pd
    from sqlalchemy import create_engine
    from pathlib import Path
    import os
    from glob import glob
    
    print("🌤️ LOADING: Weather to PostgreSQL")
    print("=" * 50)
    
    # Get database connection
    from urllib.parse import quote_plus
    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    engine = create_engine(db_url)
    
    # Find weather files
    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"
    
    # Load current weather
    weather_files = list(landing_dir.glob("weather_current_*.parquet"))
    if weather_files:
        latest_file = max(weather_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        df.to_sql('weather', engine, schema='bronze', if_exists='replace', index=False)
        print(f"✅ Loaded {len(df)} weather records")
    else:
        print("⚠️ No weather files found")
    
    print("\n✅ Weather loading completed!")


def load_team_values_to_postgres(**context):
    """
    Load team market values into PostgreSQL Bronze layer.
    """
    import pandas as pd
    from sqlalchemy import create_engine
    from pathlib import Path
    import os
    from glob import glob
    
    print("💰 LOADING: Team Values to PostgreSQL")
    print("=" * 50)
    
    # Get database connection
    from urllib.parse import quote_plus
    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    engine = create_engine(db_url)
    
    # Find team values files
    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"
    
    value_files = list(landing_dir.glob("team_values_*.parquet"))
    if value_files:
        latest_file = max(value_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        df.to_sql('team_values', engine, schema='bronze', if_exists='replace', index=False)
        print(f"✅ Loaded {len(df)} team values")
    else:
        print("⚠️ No team values files found")
    
    print("\n✅ Team values loading completed!")


def load_to_elasticsearch(**context):
    """
    Index all data into Elasticsearch for Kibana dashboards.
    """
    from load_elasticsearch import index_all_data
    
    print("🔍 INDEXATION: Elasticsearch")
    print("=" * 50)
    
    try:
        index_all_data()
        print("\n✅ Elasticsearch indexation completed!")
    except ConnectionError as e:
        print(f"⚠️ Elasticsearch not available: {e}")
        print("Skipping Elasticsearch indexation...")


# =============================================================================
# TASK INSTANTIATION
# =============================================================================

with dag:
    
    # -------------------------------------------------------------------------
    # EXTRACTION GROUP - Parallel extraction from all sources
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='extraction', tooltip='Extract data from all sources') as extraction_group:
        
        extract_football = PythonOperator(
            task_id='extract_football_api',
            python_callable=extract_football_api,
            doc_md="Extract competitions and matches from Football-Data.org API",
        )
        
        extract_weather = PythonOperator(
            task_id='extract_weather_api',
            python_callable=extract_weather_api,
            doc_md="Extract weather data from OpenWeather API",
        )
        
        extract_values = PythonOperator(
            task_id='extract_transfermarkt',
            python_callable=extract_transfermarkt,
            doc_md="Extract team market values from Transfermarkt",
        )
        
        # These can run in parallel
        [extract_football, extract_weather, extract_values]
    
    # -------------------------------------------------------------------------
    # LOADING GROUP - Load to PostgreSQL and Elasticsearch
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='loading', tooltip='Load data to destinations') as loading_group:
        
        load_matches_postgres = PythonOperator(
            task_id='load_matches_postgres',
            python_callable=load_to_postgres,
            doc_md="Load matches to PostgreSQL Bronze layer",
        )
        
        load_weather_postgres = PythonOperator(
            task_id='load_weather_postgres',
            python_callable=load_weather_to_postgres,
            doc_md="Load weather data to PostgreSQL Bronze layer",
        )
        
        load_values_postgres = PythonOperator(
            task_id='load_team_values_postgres',
            python_callable=load_team_values_to_postgres,
            doc_md="Load team values to PostgreSQL Bronze layer",
        )
        
        # Run in sequence to avoid connection issues
        load_matches_postgres >> load_weather_postgres >> load_values_postgres
    
    # -------------------------------------------------------------------------
    # DBT TRANSFORMATION
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='transformation', tooltip='DBT transformations') as transformation_group:
        
        dbt_run = BashOperator(
            task_id='dbt_run',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt run --profiles-dir /home/airflow/.dbt --target docker
            ''',
            doc_md="Run DBT models (Silver + Gold layers)",
        )
        
        dbt_test = BashOperator(
            task_id='dbt_test',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt test --profiles-dir /home/airflow/.dbt --target docker
            ''',
            doc_md="Run DBT tests for data quality",
        )
        
        dbt_run >> dbt_test
    
    # -------------------------------------------------------------------------
    # ELASTICSEARCH INDEXATION
    # -------------------------------------------------------------------------
    elasticsearch_index = PythonOperator(
        task_id='index_to_elasticsearch',
        python_callable=load_to_elasticsearch,
        doc_md="Index combined data to Elasticsearch for Kibana",
    )
    
    # -------------------------------------------------------------------------
    # DBT DOCUMENTATION (Optional)
    # -------------------------------------------------------------------------
    dbt_docs = BashOperator(
        task_id='dbt_docs_generate',
        bash_command='''
            cd /opt/airflow/dbt_football/stat_foot && \
            dbt docs generate --profiles-dir /home/airflow/.dbt --target docker
        ''',
        doc_md="Generate DBT documentation",
    )
    
    # =========================================================================
    # DAG DEPENDENCIES
    # =========================================================================
    # 
    # extraction_group (parallel)
    #        │
    #        ▼
    # loading_group (sequences)
    #        │
    #        ▼
    # transformation_group (dbt_run → dbt_test)
    #        │
    #        ├───────────────────┐
    #        ▼                   ▼
    # elasticsearch_index    dbt_docs
    #
    
    extraction_group >> loading_group >> transformation_group
    transformation_group >> [elasticsearch_index, dbt_docs]
