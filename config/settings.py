"""
Configuration Management Module
Centralized configuration for the Football ELT Pipeline
"""
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )
    
    @classmethod
    def from_env(cls):
        """Create from environment variables"""
        return cls(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 5432)),
            database=os.getenv('DB_NAME', 'football_stats_db'),
            user=os.getenv('DB_USER', 'football_user'),
            password=os.getenv('DB_PASS', '')
        )


@dataclass
class APIConfig:
    """API configuration"""
    base_url: str
    token: str
    timeout: int
    max_retries: int
    retry_delay: int
    
    @property
    def headers(self) -> dict:
        """Get API headers"""
        return {"X-Auth-Token": self.token}
    
    @classmethod
    def from_env(cls):
        """Create from environment variables"""
        return cls(
            base_url=os.getenv('API_BASE_URL', 'https://api.football-data.org/v4'),
            token=os.getenv('FOOTBALL_API_TOKEN', ''),
            timeout=int(os.getenv('API_TIMEOUT', 60)),
            max_retries=int(os.getenv('API_MAX_RETRIES', 3)),
            retry_delay=int(os.getenv('API_RETRY_DELAY', 60))
        )


@dataclass
class PathConfig:
    """Path configuration"""
    project_root: Path
    data_dir: Path
    landing_dir: Path
    raw_dir: Path
    logs_dir: Path
    
    @classmethod
    def from_env(cls):
        """Create from environment variables"""
        project_root = Path(__file__).parent.parent
        data_dir = Path(os.getenv('DATA_DIR', project_root / 'data'))
        
        return cls(
            project_root=project_root,
            data_dir=data_dir,
            landing_dir=data_dir / 'landing',
            raw_dir=data_dir / 'raw',
            logs_dir=project_root / 'logs'
        )
    
    def ensure_dirs(self):
        """Create directories if they don't exist"""
        for dir_path in [self.landing_dir, self.raw_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str
    format: str
    
    @classmethod
    def from_env(cls):
        """Create from environment variables"""
        return cls(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            format=os.getenv(
                'LOG_FORMAT',
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )


@dataclass
class PipelineConfig:
    """Pipeline configuration"""
    leagues: list
    seasons: list
    schedule: str
    
    @classmethod
    def from_env(cls):
        """Create from environment variables"""
        return cls(
            leagues=os.getenv('LEAGUES', 'PL,FL1,PD').split(','),
            seasons=[int(y) for y in os.getenv('SEASONS', '2023,2024').split(',')],
            schedule=os.getenv('PIPELINE_SCHEDULE', '@weekly')
        )


class Config:
    """Main configuration class"""
    
    def __init__(self):
        self.database = DatabaseConfig.from_env()
        self.api = APIConfig.from_env()
        self.paths = PathConfig.from_env()
        self.logging = LoggingConfig.from_env()
        self.pipeline = PipelineConfig.from_env()
        
        # Ensure directories exist
        self.paths.ensure_dirs()
    
    def validate(self) -> bool:
        """Validate configuration"""
        errors = []
        
        # Check required API token
        if not self.api.token:
            errors.append("FOOTBALL_API_TOKEN is not set")
        
        # Check database password
        if not self.database.password:
            errors.append("DB_PASS is not set")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True


# Global configuration instance
config = Config()


# Convenience functions
def get_db_connection_string() -> str:
    """Get database connection string"""
    return config.database.connection_string


def get_api_headers() -> dict:
    """Get API headers"""
    return config.api.headers


def get_landing_dir() -> Path:
    """Get landing directory path"""
    return config.paths.landing_dir


def get_logs_dir() -> Path:
    """Get logs directory path"""
    return config.paths.logs_dir


if __name__ == "__main__":
    # Test configuration
    print("=== Configuration Test ===")
    print(f"Database: {config.database.database}")
    print(f"API Base URL: {config.api.base_url}")
    print(f"Leagues: {config.pipeline.leagues}")
    print(f"Seasons: {config.pipeline.seasons}")
    print(f"Logs Dir: {config.paths.logs_dir}")
    
    try:
        config.validate()
        print("✅ Configuration is valid")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
