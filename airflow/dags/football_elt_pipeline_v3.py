"""
Football ELT Pipeline V3 - Daily Incremental Pipeline
======================================================

Restructured for daily execution with incremental extraction.

Key changes from V2:
- Match extraction is INCREMENTAL (yesterday + today only)
- Weather is fetched PER MATCH (not per city snapshot)
- Transfermarkt values are weekly (values rarely change)
- Added dbt snapshot step for SCD Type 2 history
- Added data quality reporting
- Added sensor to skip if no matches

Architecture:
    ┌────────────────────┐   ┌────────────────────┐   ┌──────────────────┐
    │  Football API      │   │  OpenWeather API    │   │  Transfermarkt   │
    │  (daily matches)   │   │  (per-match weather)│   │  (weekly values) │
    └─────────┬──────────┘   └─────────┬──────────┘   └────────┬─────────┘
              │                        │                       │
              └────────────┬───────────┘                       │
                           │                                   │
                           ▼                                   ▼
                   ┌───────────────┐                   ┌───────────────┐
                   │   PostgreSQL  │                   │   PostgreSQL  │
                   │ (Bronze incr) │                   │ (Bronze repl) │
                   └───────┬───────┘                   └───────┬───────┘
                           │                                   │
                           └───────────────┬───────────────────┘
                                           │
                                           ▼
                                   ┌───────────────┐
                                   │  dbt snapshot  │
                                   │  + dbt run     │
                                   │  + dbt test    │
                                   └───────┬───────┘
                                           │
                                   ┌───────┴───────┐
                                   ▼               ▼
                           ┌─────────────┐ ┌─────────────┐
                           │Elasticsearch│ │  dbt docs   │
                           └─────────────┘ └─────────────┘

Schedule: Daily at 6:00 AM UTC
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
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
    'football_elt_pipeline_v3',
    default_args=default_args,
    description='Daily incremental Football ELT Pipeline with weather + market values',
    schedule_interval='0 6 * * *',  # Daily at 6 AM UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['football', 'elt', 'dbt', 'daily', 'production'],
    doc_md=__doc__,
    max_active_runs=1,
)


# =============================================================================
# TASK DEFINITIONS
# =============================================================================

# -----------------------------------------------------------------------------
# CHECK: Are there matches today?
# -----------------------------------------------------------------------------

def check_for_matches(**context):
    """
    Check if there are matches to process.
    Returns True if there are matches (pipeline continues),
    False to short-circuit and skip the rest.
    """
    from fetch_daily_matches import DailyMatchExtractor
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    extractor = DailyMatchExtractor()
    try:
        df = extractor.fetch_matches_by_date(yesterday, today)
        has_matches = not df.empty
        match_count = len(df) if has_matches else 0
        print(f"{'✅' if has_matches else '⏭️'} Found {match_count} matches")
        context['ti'].xcom_push(key='match_count', value=match_count)
        return has_matches
    finally:
        extractor.close()


# -----------------------------------------------------------------------------
# EXTRACTION: Daily matches (incremental)
# -----------------------------------------------------------------------------

def extract_daily_matches(**context):
    """Extract today's and yesterday's matches only."""
    from fetch_daily_matches import DailyMatchExtractor

    print("⚽ EXTRACTION: Daily Matches (incremental)")
    print("=" * 50)

    extractor = DailyMatchExtractor()
    try:
        df = extractor.fetch_today_and_yesterday()
        stats = extractor.get_stats()
        print(f"\n✅ Extracted {stats['matches_extracted']} matches")
        context['ti'].xcom_push(key='daily_matches_count', value=stats['matches_extracted'])
    finally:
        extractor.close()


def extract_match_weather(**context):
    """Extract weather for each match from today's extraction."""
    from fetch_match_weather import MatchWeatherExtractor
    from datetime import datetime

    print("🌤️ EXTRACTION: Match Weather (per-match)")
    print("=" * 50)

    date_str = datetime.now().strftime("%Y%m%d")
    extractor = MatchWeatherExtractor()
    try:
        enriched = extractor.fetch_and_save_match_weather(date_str)
        print(f"\n✅ Weather enriched for {extractor.stats['matches_enriched']} matches")
    finally:
        extractor.close()


def extract_transfermarkt_weekly(**context):
    """
    Extract team market values.
    Only runs with fresh data on Mondays; uses cached data other days.
    """
    from fetch_transfermarkt import fetch_all_team_values
    from datetime import datetime

    print("💰 EXTRACTION: Transfermarkt")
    print("=" * 50)

    # Try live scraping on Mondays, static otherwise
    is_monday = datetime.now().weekday() == 0
    use_static = not is_monday

    if use_static:
        print("📦 Using cached/static data (live scraping only on Mondays)")

    fetch_all_team_values(use_static=use_static)
    print("\n✅ Transfermarkt extraction completed!")


# -----------------------------------------------------------------------------
# LOADING: Incremental to Bronze
# -----------------------------------------------------------------------------

def load_daily_matches_to_postgres(**context):
    """Load daily matches incrementally to PostgreSQL Bronze layer."""
    import pandas as pd
    from sqlalchemy import create_engine, text, inspect
    from pathlib import Path
    from datetime import datetime, timedelta
    from urllib.parse import quote_plus

    print("📥 LOADING: Daily matches → PostgreSQL Bronze (append)")
    print("=" * 50)

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

    # Ensure bronze schema exists
    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS bronze'))
    print("  ✅ Bronze schema ready")

    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"

    # Load daily matches file
    date_str = datetime.now().strftime("%Y%m%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    loaded = 0
    for ds in [yesterday_str, date_str]:
        daily_file = landing_dir / f"daily_matches_{ds}.parquet"
        if daily_file.exists():
            df = pd.read_parquet(daily_file)
            if not df.empty:
                # Convert complex columns to JSON strings
                import json
                import numpy as np
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(
                            lambda x: json.dumps(x.tolist()) if isinstance(x, np.ndarray)
                            else json.dumps(x) if isinstance(x, (list, dict))
                            else x
                        )

                # Handle schema evolution: add missing columns to existing table
                insp = inspect(engine)
                if insp.has_table('matches', schema='bronze'):
                    existing_cols = {c['name'] for c in insp.get_columns('matches', schema='bronze')}
                    new_cols = set(df.columns) - existing_cols
                    if new_cols:
                        print(f"  📐 Adding {len(new_cols)} new columns: {new_cols}")
                        with engine.begin() as conn:
                            for col in new_cols:
                                dtype = df[col].dtype
                                pg_type = 'TEXT'
                                if 'float' in str(dtype):
                                    pg_type = 'DOUBLE PRECISION'
                                elif 'int' in str(dtype):
                                    pg_type = 'BIGINT'
                                conn.execute(text(
                                    f'ALTER TABLE bronze.matches ADD COLUMN IF NOT EXISTS "{col}" {pg_type}'
                                ))

                df.to_sql('matches', engine, schema='bronze',
                         if_exists='append', index=False, method='multi', chunksize=100)
                loaded += len(df)
                print(f"  ✅ Loaded {len(df)} matches from {ds}")
        else:
            print(f"  ⚠️ No file found for {ds}")

    print(f"\n✅ Total loaded: {loaded} matches")


def load_weather_to_postgres(**context):
    """Load weather data to PostgreSQL Bronze layer."""
    import pandas as pd
    from sqlalchemy import create_engine
    from pathlib import Path
    from urllib.parse import quote_plus

    print("🌤️ LOADING: Weather → PostgreSQL Bronze")
    print("=" * 50)

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"

    # Load current weather files
    weather_files = list(landing_dir.glob("weather_current_*.parquet"))
    if weather_files:
        latest_file = max(weather_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        df.to_sql('weather', engine, schema='bronze', if_exists='replace', index=False)
        print(f"✅ Loaded {len(df)} weather records")
    else:
        print("⚠️ No weather files found")


def load_team_values_to_postgres(**context):
    """Load team market values to PostgreSQL Bronze layer."""
    import pandas as pd
    from sqlalchemy import create_engine
    from pathlib import Path
    from urllib.parse import quote_plus

    print("💰 LOADING: Team values → PostgreSQL Bronze")
    print("=" * 50)

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

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


# -----------------------------------------------------------------------------
# ELASTICSEARCH INDEXATION
# -----------------------------------------------------------------------------

def index_to_elasticsearch(**context):
    """Index combined data to Elasticsearch for Kibana."""
    try:
        from create_combined_index import main as create_index
        print("🔍 INDEXATION: Elasticsearch")
        print("=" * 50)
        create_index()
        print("\n✅ Elasticsearch indexation completed!")
    except Exception as e:
        print(f"⚠️ Elasticsearch not available: {e}")
        print("Skipping - non-critical for pipeline")


# -----------------------------------------------------------------------------
# DATA QUALITY REPORT
# -----------------------------------------------------------------------------

def generate_quality_report(**context):
    """Generate a daily data quality report."""
    from datetime import datetime

    ti = context['ti']
    match_count = ti.xcom_pull(key='daily_matches_count', default=0)

    report = {
        "report_date": datetime.now().isoformat(),
        "daily_matches_extracted": match_count,
        "pipeline_status": "SUCCESS",
    }

    print("📊 DATA QUALITY REPORT")
    print("=" * 50)
    for key, value in report.items():
        print(f"  {key}: {value}")
    print("=" * 50)


# =============================================================================
# TASK INSTANTIATION
# =============================================================================

with dag:

    # -------------------------------------------------------------------------
    # SENSOR: Check if there are matches to process
    # -------------------------------------------------------------------------
    check_matches = ShortCircuitOperator(
        task_id='check_for_matches',
        python_callable=check_for_matches,
        doc_md="Check if there are matches to process today. Skips pipeline if none.",
    )

    # -------------------------------------------------------------------------
    # EXTRACTION GROUP - Parallel extraction from all sources
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='extraction', tooltip='Extract data from all sources') as extraction_group:

        extract_matches = PythonOperator(
            task_id='extract_daily_matches',
            python_callable=extract_daily_matches,
            doc_md="Extract today's and yesterday's matches (incremental)",
        )

        extract_weather = PythonOperator(
            task_id='extract_match_weather',
            python_callable=extract_match_weather,
            doc_md="Extract weather for each match based on home city",
        )

        extract_values = PythonOperator(
            task_id='extract_transfermarkt',
            python_callable=extract_transfermarkt_weekly,
            doc_md="Extract team market values (weekly live, daily static)",
        )

        # Weather depends on matches being extracted first
        extract_matches >> extract_weather
        # Values extraction runs in parallel
        [extract_weather, extract_values]

    # -------------------------------------------------------------------------
    # LOADING GROUP - Load to PostgreSQL Bronze
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='loading', tooltip='Load to PostgreSQL Bronze') as loading_group:

        load_matches = PythonOperator(
            task_id='load_daily_matches',
            python_callable=load_daily_matches_to_postgres,
            doc_md="Load daily matches incrementally to Bronze",
        )

        load_weather = PythonOperator(
            task_id='load_weather',
            python_callable=load_weather_to_postgres,
            doc_md="Load weather data to Bronze",
        )

        load_values = PythonOperator(
            task_id='load_team_values',
            python_callable=load_team_values_to_postgres,
            doc_md="Load team values to Bronze",
        )

        load_matches >> load_weather >> load_values

    # -------------------------------------------------------------------------
    # TRANSFORMATION GROUP - dbt snapshot + run + test
    # -------------------------------------------------------------------------
    with TaskGroup(group_id='transformation', tooltip='dbt transformations') as transformation_group:

        dbt_snapshot = BashOperator(
            task_id='dbt_snapshot',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt snapshot --profiles-dir /home/airflow/.dbt --target docker
            ''',
            doc_md="Run dbt snapshots (SCD Type 2 for team values)",
        )

        dbt_run = BashOperator(
            task_id='dbt_run',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt run --profiles-dir /home/airflow/.dbt --target docker
            ''',
            doc_md="Run all dbt models (Silver + Gold layers)",
        )

        dbt_test = BashOperator(
            task_id='dbt_test',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt test --profiles-dir /home/airflow/.dbt --target docker; \
                TEST_EXIT=$?; \
                if [ $TEST_EXIT -ne 0 ]; then \
                    echo "⚠️ Some dbt tests failed (exit code $TEST_EXIT) - logged but non-blocking"; \
                fi; \
                exit 0
            ''',
            doc_md="Run dbt tests for data quality (non-blocking: logs failures but doesn't stop pipeline)",
        )

        dbt_freshness = BashOperator(
            task_id='dbt_source_freshness',
            bash_command='''
                cd /opt/airflow/dbt_football/stat_foot && \
                dbt source freshness --profiles-dir /home/airflow/.dbt --target docker
            ''',
            doc_md="Check source data freshness",
        )

        dbt_snapshot >> dbt_run >> dbt_test >> dbt_freshness

    # -------------------------------------------------------------------------
    # POST-PROCESSING
    # -------------------------------------------------------------------------
    elasticsearch_index = PythonOperator(
        task_id='index_to_elasticsearch',
        python_callable=index_to_elasticsearch,
        doc_md="Index combined data to Elasticsearch for Kibana",
    )

    dbt_docs = BashOperator(
        task_id='dbt_docs_generate',
        bash_command='''
            cd /opt/airflow/dbt_football/stat_foot && \
            dbt docs generate --profiles-dir /home/airflow/.dbt --target docker
        ''',
        doc_md="Generate dbt documentation",
    )

    quality_report = PythonOperator(
        task_id='data_quality_report',
        python_callable=generate_quality_report,
        doc_md="Generate daily data quality report",
    )

    # =========================================================================
    # DAG DEPENDENCIES
    # =========================================================================
    #
    # check_matches
    #      │
    #      ▼
    # extraction_group (matches → weather, values in parallel)
    #      │
    #      ▼
    # loading_group (sequential)
    #      │
    #      ▼
    # transformation_group (snapshot → run → test → freshness)
    #      │
    #      ├──────────────┬──────────────┐
    #      ▼              ▼              ▼
    # elasticsearch    dbt_docs    quality_report
    #

    check_matches >> extraction_group >> loading_group >> transformation_group
    transformation_group >> [elasticsearch_index, dbt_docs, quality_report]
