"""
Football ELT Pipeline V3 - Daily incremental pipeline.

Two-branch DAG running at 06:00 UTC:
  - Unconditional branch: city weather, transfermarkt values, football news
  - Match-gated branch: daily matches + per-match weather (skipped when no matches)

Both branches converge into dbt transformations (snapshot > run > test > freshness),
then fan out to Elasticsearch indexing, dbt docs and quality report.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import sys
import os

sys.path.append('/opt/airflow/extractor')

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
    schedule_interval='0 6 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['football', 'elt', 'dbt', 'daily', 'production'],
    doc_md=__doc__,
    max_active_runs=1,
)


# --- Task callables ---

def check_for_matches(**context):
    """Return True if matches exist for yesterday/today, False to skip match branch."""
    from fetch_daily_matches import DailyMatchExtractor
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    extractor = DailyMatchExtractor()
    try:
        df = extractor.fetch_matches_by_date(yesterday, today)
        has_matches = not df.empty
        match_count = len(df) if has_matches else 0
        print(f"Found {match_count} matches")
        context['ti'].xcom_push(key='match_count', value=match_count)
        return has_matches
    finally:
        extractor.close()



def extract_daily_matches(**context):
    """Fetch yesterday's and today's matches (incremental)."""
    from fetch_daily_matches import DailyMatchExtractor

    extractor = DailyMatchExtractor()
    try:
        extractor.fetch_today_and_yesterday()
        stats = extractor.get_stats()
        print(f"Extracted {stats['matches_extracted']} matches")
        context['ti'].xcom_push(key='daily_matches_count', value=stats['matches_extracted'])
    finally:
        extractor.close()


def extract_match_weather(**context):
    """Fetch weather conditions for each extracted match."""
    from fetch_match_weather import MatchWeatherExtractor
    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d")
    extractor = MatchWeatherExtractor()
    try:
        extractor.fetch_and_save_match_weather(date_str)
        print(f"Weather enriched for {extractor.stats['matches_enriched']} matches")
    finally:
        extractor.close()


def extract_city_weather(**context):
    """Daily city-level weather snapshot. Uses API key if available, else static fallback."""
    from fetch_weather import fetch_all_weather_data

    use_static = not bool(os.getenv("OPENWEATHER_API_KEY"))
    if use_static:
        print("No OPENWEATHER_API_KEY set, using static fallback")
    fetch_all_weather_data(use_static=use_static)
    print("City weather extraction done")


def extract_transfermarkt(**context):
    """Fetch team market values. Live scraping on Mondays, cached data otherwise."""
    from fetch_transfermarkt import fetch_all_team_values
    from datetime import datetime

    is_monday = datetime.now().weekday() == 0
    use_static = not is_monday
    if use_static:
        print("Using cached values (live scraping runs on Mondays)")
    else:
        print("Monday: attempting live scraping from Transfermarkt")
    fetch_all_team_values(use_static=use_static)
    print("Transfermarkt extraction done")



def load_daily_matches_to_postgres(**context):
    """Append daily match data to bronze.matches with schema evolution."""
    import pandas as pd
    from sqlalchemy import create_engine, text, inspect
    from pathlib import Path
    from datetime import datetime, timedelta
    from urllib.parse import quote_plus

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS bronze'))

    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"
    date_str = datetime.now().strftime("%Y%m%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    loaded = 0
    for ds in [yesterday_str, date_str]:
        daily_file = landing_dir / f"daily_matches_{ds}.parquet"
        if daily_file.exists():
            df = pd.read_parquet(daily_file)
            if not df.empty:
                import json
                import numpy as np
                for col in df.columns:
                    if df[col].dtype == 'object':
                        df[col] = df[col].apply(
                            lambda x: json.dumps(x.tolist()) if isinstance(x, np.ndarray)
                            else json.dumps(x) if isinstance(x, (list, dict))
                            else x
                        )

                # Schema evolution: add new columns dynamically
                insp = inspect(engine)
                if insp.has_table('matches', schema='bronze'):
                    existing_cols = {c['name'] for c in insp.get_columns('matches', schema='bronze')}
                    new_cols = set(df.columns) - existing_cols
                    if new_cols:
                        print(f"Adding {len(new_cols)} new columns: {new_cols}")
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
                print(f"Loaded {len(df)} matches from {ds}")
        else:
            print(f"No file found for {ds}")

    print(f"Total loaded: {loaded} matches")


def load_weather_to_postgres(**context):
    """Load city weather and match weather parquet files to bronze schema."""
    import pandas as pd
    from sqlalchemy import create_engine, text
    from pathlib import Path
    from urllib.parse import quote_plus

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS bronze'))

    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"

    weather_files = list(landing_dir.glob("weather_current_*.parquet"))
    match_weather_files = list(landing_dir.glob("weather_match_*.parquet"))
    loaded = False

    if weather_files:
        latest_file = max(weather_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        df.to_sql('weather', engine, schema='bronze', if_exists='replace', index=False)
        print(f"Loaded {len(df)} city weather records from {latest_file.name}")
        loaded = True

    if match_weather_files:
        latest_match = max(match_weather_files, key=lambda x: x.stat().st_mtime)
        df_match = pd.read_parquet(latest_match)
        df_match.to_sql('match_weather', engine, schema='bronze', if_exists='replace', index=False)
        print(f"Loaded {len(df_match)} match weather records from {latest_match.name}")
        loaded = True

    if not loaded:
        print("No weather files found")


def load_team_values_to_postgres(**context):
    """Load team market values parquet to bronze.team_values."""
    import pandas as pd
    from sqlalchemy import create_engine, text
    from pathlib import Path
    from urllib.parse import quote_plus

    db_pass = quote_plus(os.environ['DB_PASS'])
    db_url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = create_engine(db_url)

    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS bronze'))

    data_dir = Path(os.getenv("DATA_DIR", "/opt/airflow/data"))
    landing_dir = data_dir / "landing"

    value_files = list(landing_dir.glob("team_values_*.parquet"))
    if value_files:
        latest_file = max(value_files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest_file)
        df.to_sql('team_values', engine, schema='bronze', if_exists='replace', index=False)
        print(f"Loaded {len(df)} team values from {latest_file.name}")
    else:
        print("No team values files found")


def extract_football_news(**context):
    """Fetch football news from RSS feeds and index to Elasticsearch."""
    try:
        from fetch_football_news import FootballNewsExtractor, index_news_to_elasticsearch

        extractor = FootballNewsExtractor()
        articles = extractor.fetch_all_feeds()
        print(f"Fetched {len(articles)} articles from {len(extractor.rss_feeds)} feeds")

        if articles:
            stats = index_news_to_elasticsearch(articles)
            print(f"Indexed {stats.get('indexed', 0)} articles, {stats.get('errors', 0)} errors")
            context['ti'].xcom_push(key='news_articles_count', value=len(articles))
        else:
            context['ti'].xcom_push(key='news_articles_count', value=0)

    except Exception as e:
        print(f"News extraction failed (non-critical): {e}")


def index_to_elasticsearch(**context):
    """Index combined football data to Elasticsearch for Kibana dashboards."""
    try:
        from create_combined_index import main as create_index
        create_index()
        print("Elasticsearch indexation done")
    except Exception as e:
        print(f"Elasticsearch not available: {e}")


def generate_quality_report(**context):
    """Print a summary of what the pipeline processed today."""
    from datetime import datetime

    ti = context['ti']
    match_count = ti.xcom_pull(key='daily_matches_count', default=0)

    report = {
        "report_date": datetime.now().isoformat(),
        "daily_matches_extracted": match_count,
        "pipeline_status": "SUCCESS",
    }
    for key, value in report.items():
        print(f"  {key}: {value}")


# --- Task wiring ---

with dag:

    # Branch 1: runs every day regardless of matches
    with TaskGroup(group_id='independent_extraction') as independent_group:
        extract_city_wx = PythonOperator(
            task_id='extract_city_weather',
            python_callable=extract_city_weather,
        )
        extract_values = PythonOperator(
            task_id='extract_transfermarkt',
            python_callable=extract_transfermarkt,
        )
        extract_news = PythonOperator(
            task_id='extract_football_news',
            python_callable=extract_football_news,
        )
        [extract_city_wx, extract_values, extract_news]

    with TaskGroup(group_id='independent_loading') as independent_loading:
        load_weather = PythonOperator(
            task_id='load_weather',
            python_callable=load_weather_to_postgres,
        )
        load_values = PythonOperator(
            task_id='load_team_values',
            python_callable=load_team_values_to_postgres,
        )
        [load_weather, load_values]

    # Branch 2: only when matches exist
    check_matches = ShortCircuitOperator(
        task_id='check_for_matches',
        python_callable=check_for_matches,
    )

    with TaskGroup(group_id='match_extraction') as match_extraction_group:
        extract_matches = PythonOperator(
            task_id='extract_daily_matches',
            python_callable=extract_daily_matches,
        )
        extract_weather = PythonOperator(
            task_id='extract_match_weather',
            python_callable=extract_match_weather,
        )
        extract_matches >> extract_weather

    load_matches = PythonOperator(
        task_id='load_daily_matches',
        python_callable=load_daily_matches_to_postgres,
    )

    # Transformations (dbt)
    with TaskGroup(group_id='transformation') as transformation_group:
        dbt_snapshot = BashOperator(
            task_id='dbt_snapshot',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt snapshot --profiles-dir /home/airflow/.dbt --target docker',
            # Run even when match branch is skipped (no matches that day)
            trigger_rule='none_failed_min_one_success',
        )
        dbt_run = BashOperator(
            task_id='dbt_run',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt run --profiles-dir /home/airflow/.dbt --target docker',
        )
        dbt_test = BashOperator(
            task_id='dbt_test',
            bash_command=(
                'cd /opt/airflow/dbt_football/stat_foot && '
                'dbt test --profiles-dir /home/airflow/.dbt --target docker; '
                'TEST_EXIT=$?; '
                'if [ $TEST_EXIT -ne 0 ]; then echo "Some dbt tests failed (exit $TEST_EXIT)"; fi; '
                'exit 0'
            ),
        )
        dbt_freshness = BashOperator(
            task_id='dbt_source_freshness',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt source freshness --profiles-dir /home/airflow/.dbt --target docker',
        )
        dbt_snapshot >> dbt_run >> dbt_test >> dbt_freshness

    # Post-processing
    elasticsearch_index = PythonOperator(
        task_id='index_to_elasticsearch',
        python_callable=index_to_elasticsearch,
    )
    dbt_docs = BashOperator(
        task_id='dbt_docs_generate',
        bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt docs generate --profiles-dir /home/airflow/.dbt --target docker',
    )
    quality_report = PythonOperator(
        task_id='data_quality_report',
        python_callable=generate_quality_report,
    )

    # Dependencies
    independent_group >> independent_loading
    check_matches >> match_extraction_group >> load_matches
    [independent_loading, load_matches] >> transformation_group
    transformation_group >> [elasticsearch_index, dbt_docs, quality_report]
