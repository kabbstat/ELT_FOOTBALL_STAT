"""
Enhanced Football Data Extractor with Logging and Error Handling
"""
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import pandas as pd
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
API_BASE = "https://api.football-data.org/v4"
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"
RAW_DIR = DATA_DIR / "raw"
API_TOKEN = os.environ.get("FOOTBALL_API_TOKEN")

# Validate configuration
if not API_TOKEN:
    logger.error("FOOTBALL_API_TOKEN not found in environment variables")
    raise ValueError("FOOTBALL_API_TOKEN is required")

HEADERS = {"X-Auth-Token": API_TOKEN}

# Ensure directories exist
LANDING_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)


class FootballDataExtractor:
    """Extract football data from API with proper error handling and retry logic"""
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 60):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = httpx.Client(timeout=60, headers=HEADERS)
        logger.info("FootballDataExtractor initialized")
    
    def _make_request(self, url: str, retry_count: int = 0) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        try:
            logger.info(f"Making request to: {url}")
            response = self.client.get(url)
            
            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < self.max_retries:
                    logger.warning(f"Rate limit hit. Waiting {self.retry_delay}s before retry {retry_count + 1}/{self.max_retries}")
                    time.sleep(self.retry_delay)
                    return self._make_request(url, retry_count + 1)
                else:
                    logger.error(f"Max retries reached for {url}")
                    raise httpx.HTTPStatusError(f"Rate limit exceeded", request=response.request, response=response)
            
            response.raise_for_status()
            logger.info(f"Request successful: {url}")
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            raise
    
    def _save_json(self, data: Dict[str, Any], filename: str) -> Path:
        """Save data as JSON with metadata"""
        try:
            path = LANDING_DIR / filename
            enriched = {
                "extracted_at": datetime.now().isoformat(),
                "data": data,
                "record_count": len(data.get("matches", [])) if "matches" in data else len(data.get("competitions", []))
            }
            path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"Data saved to {path}")
            return path
        except Exception as e:
            logger.error(f"Error saving JSON to {filename}: {e}")
            raise
    
    def _save_parquet(self, df: pd.DataFrame, filename: str) -> Path:
        """Save DataFrame as Parquet"""
        try:
            path = LANDING_DIR / filename
            df.to_parquet(path, index=False)
            logger.info(f"Parquet saved to {path} with {len(df)} records")
            return path
        except Exception as e:
            logger.error(f"Error saving Parquet to {filename}: {e}")
            raise
    
    def fetch_competitions(self) -> pd.DataFrame:
        """Fetch competitions from API"""
        logger.info("Fetching competitions...")
        url = f"{API_BASE}/competitions"
        
        try:
            data = self._make_request(url)
            
            if "competitions" not in data:
                logger.warning("No competitions found in response")
                return pd.DataFrame()
            
            # Normalize and save
            df = pd.json_normalize(data["competitions"])
            self._save_parquet(df, "competitions.parquet")
            
            logger.info(f"Fetched {len(df)} competitions")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch competitions: {e}")
            raise
    
    def fetch_matches_for_league(self, league_code: str, season: int) -> pd.DataFrame:
        """Fetch matches for a specific league and season"""
        logger.info(f"Fetching matches for {league_code} - Season {season}")
        url = f"{API_BASE}/competitions/{league_code}/matches?season={season}"
        
        try:
            data = self._make_request(url)
            
            # Save raw JSON
            self._save_json(data, f"matches_{league_code}_{season}.json")
            
            # Process matches
            if "matches" not in data or not data["matches"]:
                logger.warning(f"No matches found for {league_code} - {season}")
                return pd.DataFrame()
            
            matches = pd.json_normalize(data["matches"], sep="_")
            matches["competition_code"] = league_code
            matches["season_year"] = season
            
            logger.info(f"Fetched {len(matches)} matches for {league_code}")
            return matches
            
        except Exception as e:
            logger.error(f"Failed to fetch matches for {league_code} - {season}: {e}")
            # Return empty DataFrame to continue with other leagues
            return pd.DataFrame()
    
    def fetch_all_matches(self, leagues: List[str] = None, seasons: List[int] = None) -> pd.DataFrame:
        """Fetch matches for multiple leagues and seasons"""
        if leagues is None:
            leagues = ["PL", "FL1", "PD"]
        if seasons is None:
            seasons = [2023, 2024]
        
        logger.info(f"Starting extraction for leagues: {leagues}, seasons: {seasons}")
        
        all_frames = []
        failed_extractions = []
        
        for season in seasons:
            for league in leagues:
                try:
                    df = self.fetch_matches_for_league(league, season)
                    if not df.empty:
                        all_frames.append(df)
                    
                    # Rate limiting delay between requests
                    time.sleep(6)
                    
                except Exception as e:
                    logger.error(f"Extraction failed for {league} - {season}: {e}")
                    failed_extractions.append(f"{league}_{season}")
                    continue
        
        # Combine all data
        if all_frames:
            combined = pd.concat(all_frames, ignore_index=True)
            
            # Save combined data
            for season in seasons:
                season_data = combined[combined['season_year'] == season]
                if not season_data.empty:
                    self._save_parquet(season_data, f"all_matches_{season}.parquet")
            
            logger.info(f"Total matches extracted: {len(combined)}")
            
            if failed_extractions:
                logger.warning(f"Failed extractions: {', '.join(failed_extractions)}")
            
            return combined
        else:
            logger.error("No data extracted from any source")
            raise ValueError("All extractions failed")
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
        logger.info("FootballDataExtractor closed")


def main():
    """Main extraction function"""
    extractor = FootballDataExtractor()
    
    try:
        # Fetch competitions
        logger.info("=" * 50)
        logger.info("Starting Competitions Extraction")
        logger.info("=" * 50)
        extractor.fetch_competitions()
        
        # Fetch matches
        logger.info("=" * 50)
        logger.info("Starting Matches Extraction")
        logger.info("=" * 50)
        extractor.fetch_all_matches()
        
        logger.info("=" * 50)
        logger.info("Extraction completed successfully")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Extraction pipeline failed: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
