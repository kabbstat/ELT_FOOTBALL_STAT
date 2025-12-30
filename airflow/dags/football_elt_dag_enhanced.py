"""
Enhanced Football ELT DAG with Monitoring, Error Handling, and Data Quality Checks
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.utils.email import send_email
from datetime import datetime, timedelta
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add extractor to path
sys.path.append('/opt/airflow/extractor')

# Default arguments
default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'email': ['your-email@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

# DAG definition
dag = DAG(
    'football_elt_pipeline_enhanced',
    default_args=default_args,
    description='Production-grade Football ELT Pipeline with monitoring',
    schedule_interval='@weekly',  # Run every Saturday
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['football', 'elt', 'dbt', 'production'],
    max_active_runs=1,
)


def send_pipeline_notification(context):
    """Send custom notification on failure"""
    task_instance = context.get('task_instance')
    task_id = task_instance.task_id
    dag_id = task_instance.dag_id
    execution_date = context.get('execution_date')
    
    subject = f"Airflow Alert: {dag_id}.{task_id} Failed"
    body = f"""
    Task Failed:
    - DAG: {dag_id}
    - Task: {task_id}
    - Execution Date: {execution_date}
    - Log URL: {task_instance.log_url}
    """
    logger.error(body)


# ============================================================================
# EXTRACTION TASKS
# ============================================================================

def extract_football_data(**context):
    """Extract data from Football API"""
    from foot_data_enhanced import FootballDataExtractor
    
    logger.info("🏆 Starting data extraction...")
    
    extractor = FootballDataExtractor()
    
    try:
        # Fetch competitions
        logger.info("Fetching competitions...")
        competitions_df = extractor.fetch_competitions()
        context['ti'].xcom_push(key='competitions_count', value=len(competitions_df))
        
        # Fetch matches
        logger.info("Fetching matches for all leagues and seasons...")
        matches_df = extractor.fetch_all_matches(
            leagues=['PL', 'FL1', 'PD'],
            seasons=[2023, 2024]
        )
        context['ti'].xcom_push(key='matches_count', value=len(matches_df))
        
        logger.info(f"✅ Extraction completed: {len(matches_df)} matches extracted")
        
        return {
            'status': 'success',
            'competitions_count': len(competitions_df),
            'matches_count': len(matches_df)
        }
        
    except Exception as e:
        logger.error(f"❌ Extraction failed: {str(e)}")
        raise
    finally:
        extractor.close()


def validate_extracted_data(**context):
    """Validate extracted data before loading"""
    from pathlib import Path
    import pandas as pd
    
    logger.info("🔍 Validating extracted data...")
    
    data_dir = Path('/opt/airflow/data/landing')
    required_files = [
        'all_matches_2023.parquet',
        'all_matches_2024.parquet',
        'competitions.parquet'
    ]
    
    validation_results = {}
    
    for file_name in required_files:
        file_path = data_dir / file_name
        
        if not file_path.exists():
            logger.error(f"❌ Missing file: {file_name}")
            validation_results[file_name] = 'MISSING'
        else:
            try:
                df = pd.read_parquet(file_path)
                if df.empty:
                    logger.warning(f"⚠️ Empty file: {file_name}")
                    validation_results[file_name] = 'EMPTY'
                else:
                    logger.info(f"✅ Valid file: {file_name} ({len(df)} rows)")
                    validation_results[file_name] = f'OK ({len(df)} rows)'
            except Exception as e:
                logger.error(f"❌ Corrupted file: {file_name} - {str(e)}")
                validation_results[file_name] = 'CORRUPTED'
    
    context['ti'].xcom_push(key='validation_results', value=validation_results)
    
    # Fail if any critical file is missing or corrupted
    if any(status in ['MISSING', 'CORRUPTED'] for status in validation_results.values()):
        raise ValueError(f"Data validation failed: {validation_results}")
    
    logger.info("✅ Data validation passed")
    return validation_results


with dag:
    
    start = EmptyOperator(task_id='start')
    
    # Extraction group
    with TaskGroup('extraction', tooltip='Extract data from API') as extraction_group:
        
        extract_task = PythonOperator(
            task_id='extract_football_data',
            python_callable=extract_football_data,
            on_failure_callback=send_pipeline_notification,
        )
        
        validate_task = PythonOperator(
            task_id='validate_extracted_data',
            python_callable=validate_extracted_data,
        )
        
        extract_task >> validate_task
    
    # ============================================================================
    # LOADING TASKS
    # ============================================================================
    
    def load_to_bronze(**context):
        """Load data to PostgreSQL Bronze layer"""
        from load_postgres_enhanced import PostgreSQLLoader
        
        logger.info("📥 Loading data to Bronze layer...")
        
        loader = PostgreSQLLoader()
        
        try:
            # Load matches
            total_rows = loader.load_all_matches(seasons=[2023, 2024])
            
            # Load competitions
            try:
                loader.load_parquet_to_postgres(
                    parquet_file='competitions.parquet',
                    table_name='competitions',
                    schema='bronze'
                )
            except Exception as e:
                logger.warning(f"Competitions loading failed (non-critical): {e}")
            
            # Get table stats
            stats = loader.get_table_stats('bronze', 'matches')
            context['ti'].xcom_push(key='bronze_stats', value=stats)
            
            logger.info(f"✅ Loading to Bronze completed: {total_rows} rows loaded")
            
            return {'status': 'success', 'rows_loaded': total_rows, 'stats': stats}
            
        except Exception as e:
            logger.error(f"❌ Loading to Bronze failed: {str(e)}")
            raise
        finally:
            loader.close()
    
    
    load_bronze_task = PythonOperator(
        task_id='load_to_bronze',
        python_callable=load_to_bronze,
        on_failure_callback=send_pipeline_notification,
    )
    
    # ============================================================================
    # DBT TRANSFORMATION TASKS
    # ============================================================================
    
    with TaskGroup('dbt_transformation', tooltip='DBT transformations') as dbt_group:
        
        # Clean old artifacts
        dbt_clean = BashOperator(
            task_id='dbt_clean',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt clean --profiles-dir /home/airflow/.dbt',
        )
        
        # Install dependencies
        dbt_deps = BashOperator(
            task_id='dbt_deps',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt deps --profiles-dir /home/airflow/.dbt',
        )
        
        # Run transformations
        dbt_run = BashOperator(
            task_id='dbt_run',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt run --profiles-dir /home/airflow/.dbt',
            on_failure_callback=send_pipeline_notification,
        )
        
        # Test data quality
        dbt_test = BashOperator(
            task_id='dbt_test',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt test --profiles-dir /home/airflow/.dbt',
            on_failure_callback=send_pipeline_notification,
        )
        
        # Generate documentation
        dbt_docs = BashOperator(
            task_id='dbt_docs_generate',
            bash_command='cd /opt/airflow/dbt_football/stat_foot && dbt docs generate --profiles-dir /home/airflow/.dbt',
        )
        
        dbt_clean >> dbt_deps >> dbt_run >> dbt_test >> dbt_docs
    
    # ============================================================================
    # DATA QUALITY CHECKS
    # ============================================================================
    
    def run_data_quality_checks(**context):
        """Run custom data quality checks on Gold layer"""
        from load_postgres_enhanced import PostgreSQLLoader
        
        logger.info("🔍 Running data quality checks...")
        
        loader = PostgreSQLLoader()
        results = {}
        
        try:
            # Check 1: Verify gold tables exist and have data
            for table in ['fact_matches', 'dim_teams', 'agg_team_performance', 'agg_competition_stats']:
                try:
                    stats = loader.get_table_stats('gold', table)
                    results[table] = stats
                    
                    if stats.get('row_count', 0) == 0:
                        logger.warning(f"⚠️ Table {table} is empty")
                except Exception as e:
                    logger.error(f"❌ Failed to check table {table}: {e}")
                    results[table] = {'error': str(e)}
            
            # Check 2: Verify data freshness
            query = """
            SELECT MAX(loaded_at) as last_load
            FROM gold.fact_matches
            """
            freshness = loader.execute_query(query)
            results['data_freshness'] = str(freshness.iloc[0]['last_load'])
            
            # Check 3: Verify key metrics
            query = """
            SELECT 
                COUNT(DISTINCT match_id) as total_matches,
                COUNT(DISTINCT home_team_id) as unique_teams,
                SUM(total_goals) as total_goals
            FROM gold.fact_matches
            """
            metrics = loader.execute_query(query)
            results['key_metrics'] = metrics.iloc[0].to_dict()
            
            context['ti'].xcom_push(key='quality_check_results', value=results)
            
            logger.info(f"✅ Data quality checks passed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Data quality checks failed: {str(e)}")
            raise
        finally:
            loader.close()
    
    
    quality_check_task = PythonOperator(
        task_id='data_quality_checks',
        python_callable=run_data_quality_checks,
    )
    
    # ============================================================================
    # REPORTING
    # ============================================================================
    
    def send_success_report(**context):
        """Send pipeline success report"""
        ti = context['ti']
        
        matches_count = ti.xcom_pull(task_ids='extraction.extract_football_data', key='matches_count')
        bronze_stats = ti.xcom_pull(task_ids='load_to_bronze', key='bronze_stats')
        quality_results = ti.xcom_pull(task_ids='data_quality_checks', key='quality_check_results')
        
        logger.info("=" * 60)
        logger.info("📊 PIPELINE EXECUTION REPORT")
        logger.info("=" * 60)
        logger.info(f"✅ Status: SUCCESS")
        logger.info(f"📥 Matches Extracted: {matches_count}")
        logger.info(f"💾 Bronze Layer Stats: {bronze_stats}")
        logger.info(f"🎯 Quality Check Results: {quality_results}")
        logger.info("=" * 60)
    
    
    success_report = PythonOperator(
        task_id='send_success_report',
        python_callable=send_success_report,
    )
    
    end = EmptyOperator(task_id='end')
    
    # ============================================================================
    # DAG FLOW
    # ============================================================================
    
    start >> extraction_group >> load_bronze_task >> dbt_group >> quality_check_task >> success_report >> end
