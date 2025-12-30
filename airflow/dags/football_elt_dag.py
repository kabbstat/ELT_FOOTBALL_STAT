from airflow import DAG 
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.append('/opt/airflow/extractor')
default_args = {
    'owner': "data_eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    'footbal_elt_pipeline',
    default_args = default_args,
    description = 'A simple football ELT pipeline',
    schedule_interval = '@weekly',
    start_date = datetime(2023, 1, 1),
    catchup = False,
    tags = ['football', 'elt', 'dbt'],
)
# task 1 : Extract from API 
def extract_football_data(**context):
    from foot_data import fetch_competitions, fetch_matches_save
    print("🏆 Fetching competitions...")
    fetch_competitions()
    
    print("⚽ Fetching matches 2023...")
    fetch_matches_save(season=2023)
    
    print("⚽ Fetching matches 2024...")
    fetch_matches_save(season=2024)
    
    print("✅ Extraction completed")
extract_task = PythonOperator(
    task_id = 'extract_football_data',
    python_callable = extract_football_data,
    dag = dag,
)
# Task 2 : load to postgresql bronze
def load_to_bronze(**context):
    from load_postgres import load_parquet_to_postgres
    print("📥 Loading data to PostgreSQL Bronze...")
    load_parquet_to_postgres(schema='bronze', season=2023)
    load_parquet_to_postgres(schema='bronze', season=2024)
    print("✅ Loading to Bronze completed")

load_bronze_task= PythonOperator(
    task_id = 'load_to_bronze',
    python_callable = load_to_bronze,
    dag = dag,
)
# Task 3 : DBT : transformation bronze - Gold
dbt_run = BashOperator(
    task_id = 'dbt_transformation',
    bash_command ='cd /opt/airflow/dbt_football/stat_foot && dbt run --profiles-dir /home/airflow/.dbt',
    dag = dag,
)
# task 4 : DBT : run test
dbt_test = BashOperator(
    task_id = 'db_test',
    bash_command = 'cd /opt/airflow/dbt_football/stat_foot && dbt test --profiles-dir /home/airflow/.dbt',
    dag = dag,
)
# task 5 : DBT : generate doc 
dbt_doc = BashOperator(
    task_id = 'dbt_docs_generate',
    bash_command = 'cd /opt/airflow/dbt_football/stat_foot && dbt docs generate --profiles-dir /home/airflow/.dbt',
    dag= dag,
)
extract_task >> load_bronze_task >> dbt_run >> dbt_test >> dbt_doc
    