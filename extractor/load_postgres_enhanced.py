"""
Enhanced PostgreSQL Loader with Error Handling and Data Validation
"""
import os
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/loading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'football_stats_db'),
    'user': os.getenv('DB_USER', 'football_user'),
    'password': os.getenv('DB_PASS')
}

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)


class PostgreSQLLoader:
    """Load data into PostgreSQL with proper error handling"""
    
    def __init__(self):
        self.engine = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            conn_string = (
                f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
                f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            )
            self.engine = create_engine(conn_string)
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info(f"Connected to database: {DB_CONFIG['database']}")
            
        except SQLAlchemyError as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _create_schema(self, schema_name: str):
        """Create schema if not exists"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                conn.commit()
            logger.info(f"Schema '{schema_name}' ensured")
        except SQLAlchemyError as e:
            logger.error(f"Failed to create schema '{schema_name}': {e}")
            raise
    
    def _validate_dataframe(self, df: pd.DataFrame, table_name: str) -> bool:
        """Validate DataFrame before loading"""
        if df.empty:
            logger.warning(f"DataFrame for {table_name} is empty")
            return False
        
        logger.info(f"Validating {len(df)} records for {table_name}")
        logger.info(f"Columns: {list(df.columns)}")
        
        # Check for all null rows
        all_null_rows = df.isnull().all(axis=1).sum()
        if all_null_rows > 0:
            logger.warning(f"Found {all_null_rows} completely null rows")
        
        return True
    
    def load_parquet_to_postgres(
        self, 
        parquet_file: str, 
        table_name: str, 
        schema: str = 'bronze',
        if_exists: str = 'replace'
    ) -> int:
        """Load Parquet file to PostgreSQL table"""
        
        file_path = LANDING_DIR / parquet_file
        
        try:
            # Check if file exists
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
            
            logger.info(f"Loading {file_path} to {schema}.{table_name}")
            
            # Read parquet
            df = pd.read_parquet(file_path)
            
            # Validate
            if not self._validate_dataframe(df, table_name):
                return 0
            
            # Ensure schema exists
            self._create_schema(schema)
            
            # Load to database
            rows_loaded = df.to_sql(
                name=table_name,
                con=self.engine,
                schema=schema,
                if_exists=if_exists,
                index=False,
                method='multi',
                chunksize=1000
            )
            
            logger.info(f"Successfully loaded {len(df)} rows to {schema}.{table_name}")
            return len(df)
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise
        except pd.errors.ParserError as e:
            logger.error(f"Error parsing Parquet file: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error while loading {table_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading {table_name}: {e}")
            raise
    
    def load_all_matches(self, seasons: list = None):
        """Load matches for multiple seasons"""
        if seasons is None:
            seasons = [2023, 2024]
        
        total_loaded = 0
        failed_loads = []
        
        for season in seasons:
            try:
                file_name = f"all_matches_{season}.parquet"
                rows = self.load_parquet_to_postgres(
                    parquet_file=file_name,
                    table_name='matches',
                    schema='bronze',
                    if_exists='append' if season != seasons[0] else 'replace'
                )
                total_loaded += rows
                
            except Exception as e:
                logger.error(f"Failed to load season {season}: {e}")
                failed_loads.append(season)
        
        logger.info(f"Total rows loaded: {total_loaded}")
        if failed_loads:
            logger.warning(f"Failed to load seasons: {failed_loads}")
        
        return total_loaded
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results"""
        try:
            with self.engine.connect() as conn:
                result = pd.read_sql(query, conn)
            logger.info(f"Query executed successfully, returned {len(result)} rows")
            return result
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def get_table_stats(self, schema: str, table: str) -> dict:
        """Get statistics about a table"""
        try:
            query = f"""
            SELECT 
                COUNT(*) as row_count,
                COUNT(DISTINCT id) as unique_ids
            FROM {schema}.{table}
            """
            result = self.execute_query(query)
            stats = result.iloc[0].to_dict()
            logger.info(f"Stats for {schema}.{table}: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Failed to get stats for {schema}.{table}: {e}")
            return {}
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


def main():
    """Main loading function"""
    loader = PostgreSQLLoader()
    
    try:
        logger.info("=" * 50)
        logger.info("Starting Data Loading")
        logger.info("=" * 50)
        
        # Load competitions
        try:
            loader.load_parquet_to_postgres(
                parquet_file='competitions.parquet',
                table_name='competitions',
                schema='bronze'
            )
        except Exception as e:
            logger.warning(f"Competition loading failed (non-critical): {e}")
        
        # Load matches
        loader.load_all_matches()
        
        # Get stats
        stats = loader.get_table_stats('bronze', 'matches')
        
        logger.info("=" * 50)
        logger.info("Loading completed successfully")
        logger.info(f"Final stats: {stats}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Loading pipeline failed: {e}")
        raise
    finally:
        loader.close()


if __name__ == "__main__":
    main()
