"""
Daily Incremental Football Data Extractor
==========================================
Fetches only today's and yesterday's matches instead of full season re-extraction.
Designed for daily Airflow scheduling.

Usage:
    python fetch_daily_matches.py                    # fetch yesterday + today
    python fetch_daily_matches.py --date 2024-03-15  # fetch specific date
    python fetch_daily_matches.py --backfill 7       # backfill last 7 days
"""
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import pandas as pd
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/extraction_daily.log'),
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

if not API_TOKEN:
    logger.error("FOOTBALL_API_TOKEN not found in environment variables")
    raise ValueError("FOOTBALL_API_TOKEN is required")

HEADERS = {"X-Auth-Token": API_TOKEN}

# Ensure directories exist
LANDING_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

# Leagues to monitor
DEFAULT_LEAGUES = ["PL", "FL1", "PD"]


class DailyMatchExtractor:
    """Extract only recent matches for incremental daily loading."""

    def __init__(self, max_retries: int = 3, retry_delay: int = 60):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = httpx.Client(timeout=60, headers=HEADERS)
        self.stats = {
            "api_calls": 0,
            "matches_extracted": 0,
            "errors": 0,
        }
        logger.info("DailyMatchExtractor initialized")

    def _make_request(self, url: str, retry_count: int = 0) -> Dict[str, Any]:
        """Make HTTP request with retry logic and rate limiting."""
        try:
            logger.info(f"API call #{self.stats['api_calls'] + 1}: {url}")
            self.stats["api_calls"] += 1
            response = self.client.get(url)

            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < self.max_retries:
                    wait_time = int(response.headers.get("X-RequestCounter-Reset", self.retry_delay))
                    logger.warning(
                        f"Rate limit hit. Waiting {wait_time}s before retry "
                        f"{retry_count + 1}/{self.max_retries}"
                    )
                    time.sleep(wait_time)
                    return self._make_request(url, retry_count + 1)
                else:
                    logger.error(f"Max retries reached for {url}")
                    raise httpx.HTTPStatusError(
                        "Rate limit exceeded", request=response.request, response=response
                    )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {url}: {e}")
            self.stats["errors"] += 1
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            self.stats["errors"] += 1
            raise

    def fetch_matches_by_date(
        self,
        date_from: str,
        date_to: str,
        leagues: List[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch matches within a date range (inclusive).

        Args:
            date_from: Start date in YYYY-MM-DD format
            date_to: End date in YYYY-MM-DD format
            leagues: List of league codes (default: PL, FL1, PD)

        Returns:
            DataFrame with all matches in the date range
        """
        if leagues is None:
            leagues = DEFAULT_LEAGUES

        logger.info(f"Fetching matches from {date_from} to {date_to} for {leagues}")
        all_frames = []

        for league in leagues:
            try:
                url = (
                    f"{API_BASE}/competitions/{league}/matches"
                    f"?dateFrom={date_from}&dateTo={date_to}"
                )
                data = self._make_request(url)

                # Save raw JSON backup
                raw_file = RAW_DIR / f"matches_{league}_{date_from}_{date_to}.json"
                raw_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )

                matches = data.get("matches", [])
                if not matches:
                    logger.info(f"No matches for {league} on {date_from} → {date_to}")
                    continue

                df = pd.json_normalize(matches, sep="_")
                df["competition_code"] = league
                df["extraction_date"] = datetime.now().isoformat()
                all_frames.append(df)

                logger.info(f"  {league}: {len(df)} matches found")
                self.stats["matches_extracted"] += len(df)

                # Rate limiting between league calls
                time.sleep(6)

            except Exception as e:
                logger.error(f"Failed to fetch {league} for {date_from}→{date_to}: {e}")
                continue

        if not all_frames:
            logger.info("No matches found for the specified date range")
            return pd.DataFrame()

        combined = pd.concat(all_frames, ignore_index=True)

        # Save to landing zone with date partition
        output_file = f"daily_matches_{date_from.replace('-', '')}.parquet"
        output_path = LANDING_DIR / output_file
        combined.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(combined)} matches to {output_path}")

        return combined

    def fetch_today_and_yesterday(self, leagues: List[str] = None) -> pd.DataFrame:
        """Convenience method: fetch matches from yesterday and today."""
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        return self.fetch_matches_by_date(yesterday, today, leagues)

    def fetch_last_n_days(self, n_days: int, leagues: List[str] = None) -> pd.DataFrame:
        """Backfill: fetch matches from the last N days."""
        today = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=n_days)).strftime("%Y-%m-%d")
        return self.fetch_matches_by_date(start, today, leagues)

    def get_stats(self) -> Dict[str, int]:
        """Return extraction statistics."""
        return self.stats.copy()

    def close(self):
        """Close HTTP client."""
        self.client.close()
        logger.info(f"DailyMatchExtractor closed. Stats: {self.stats}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Daily Football Match Extractor")
    parser.add_argument("--date", help="Specific date to fetch (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="Backfill last N days")
    parser.add_argument(
        "--leagues", nargs="+", default=DEFAULT_LEAGUES, help="League codes"
    )
    args = parser.parse_args()

    extractor = DailyMatchExtractor()

    try:
        if args.backfill:
            logger.info(f"Backfill mode: last {args.backfill} days")
            df = extractor.fetch_last_n_days(args.backfill, args.leagues)
        elif args.date:
            logger.info(f"Single date mode: {args.date}")
            df = extractor.fetch_matches_by_date(args.date, args.date, args.leagues)
        else:
            logger.info("Default mode: yesterday + today")
            df = extractor.fetch_today_and_yesterday(args.leagues)

        stats = extractor.get_stats()
        logger.info("=" * 50)
        logger.info(f"Extraction complete: {stats}")
        if not df.empty:
            logger.info(f"Total matches: {len(df)}")
            logger.info(f"Leagues: {df.get('competition_code', pd.Series()).unique().tolist()}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Daily extraction failed: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
