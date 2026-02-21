"""
Match-Level Weather Extractor
==============================
Fetches weather data for each match based on the home team's city and match date/time.
Unlike the city-snapshot approach, this associates weather directly to each match.

Usage:
    python fetch_match_weather.py                          # weather for today's matches
    python fetch_match_weather.py --date 2024-03-15        # weather for a specific date
    python fetch_match_weather.py --from-parquet daily_matches_20240315.parquet
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
        logging.FileHandler('logs/weather_match.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"

# Ensure directories exist
LANDING_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

# Comprehensive team → city+coords mapping
TEAM_LOCATIONS = {
    # Premier League
    "Arsenal FC": {"city": "London", "lat": 51.5549, "lon": -0.1084},
    "Aston Villa FC": {"city": "Birmingham", "lat": 52.5090, "lon": -1.8848},
    "Chelsea FC": {"city": "London", "lat": 51.4817, "lon": -0.1910},
    "Liverpool FC": {"city": "Liverpool", "lat": 53.4308, "lon": -2.9608},
    "Manchester City FC": {"city": "Manchester", "lat": 53.4831, "lon": -2.2004},
    "Manchester United FC": {"city": "Manchester", "lat": 53.4631, "lon": -2.2913},
    "Tottenham Hotspur FC": {"city": "London", "lat": 51.6043, "lon": -0.0660},
    "Newcastle United FC": {"city": "Newcastle", "lat": 54.9756, "lon": -1.6217},
    "Brighton & Hove Albion FC": {"city": "Brighton", "lat": 50.8619, "lon": -0.0832},
    "Everton FC": {"city": "Liverpool", "lat": 53.4388, "lon": -2.9664},
    "Brentford FC": {"city": "London", "lat": 51.4907, "lon": -0.2886},
    "Fulham FC": {"city": "London", "lat": 51.4749, "lon": -0.2217},
    "Crystal Palace FC": {"city": "London", "lat": 51.3983, "lon": -0.0855},
    "West Ham United FC": {"city": "London", "lat": 51.5386, "lon": 0.0166},
    "Wolverhampton Wanderers FC": {"city": "Wolverhampton", "lat": 52.5903, "lon": -2.1305},
    "Nottingham Forest FC": {"city": "Nottingham", "lat": 52.9400, "lon": -1.1329},
    "AFC Bournemouth": {"city": "Bournemouth", "lat": 50.7353, "lon": -1.8384},
    "Burnley FC": {"city": "Burnley", "lat": 53.7890, "lon": -2.2302},
    "Sheffield United FC": {"city": "Sheffield", "lat": 53.3703, "lon": -1.4710},
    "Luton Town FC": {"city": "Luton", "lat": 51.8841, "lon": -0.4316},
    "Ipswich Town FC": {"city": "Ipswich", "lat": 52.0548, "lon": 1.1447},
    "Leicester City FC": {"city": "Leicester", "lat": 52.6204, "lon": -1.1422},
    "Southampton FC": {"city": "Southampton", "lat": 50.9058, "lon": -1.3909},
    # La Liga
    "FC Barcelona": {"city": "Barcelona", "lat": 41.3809, "lon": 2.1228},
    "Real Madrid CF": {"city": "Madrid", "lat": 40.4531, "lon": -3.6883},
    "Atlético de Madrid": {"city": "Madrid", "lat": 40.4361, "lon": -3.5994},
    "Club Atlético de Madrid": {"city": "Madrid", "lat": 40.4361, "lon": -3.5994},
    "Sevilla FC": {"city": "Sevilla", "lat": 37.3840, "lon": -5.9705},
    "Real Sociedad de Fútbol": {"city": "San Sebastian", "lat": 43.3015, "lon": -1.9736},
    "Real Betis Balompié": {"city": "Sevilla", "lat": 37.3567, "lon": -5.9818},
    "Villarreal CF": {"city": "Villarreal", "lat": 39.9440, "lon": -0.1036},
    "Athletic Club": {"city": "Bilbao", "lat": 43.2641, "lon": -2.9494},
    "Valencia CF": {"city": "Valencia", "lat": 39.4746, "lon": -0.3583},
    "Girona FC": {"city": "Girona", "lat": 41.9607, "lon": 2.8286},
    "CA Osasuna": {"city": "Pamplona", "lat": 42.7967, "lon": -1.6372},
    "Getafe CF": {"city": "Madrid", "lat": 40.3256, "lon": -3.7148},
    "RCD Mallorca": {"city": "Palma", "lat": 39.5904, "lon": 2.6301},
    "Rayo Vallecano de Madrid": {"city": "Madrid", "lat": 40.3918, "lon": -3.6589},
    "RC Celta de Vigo": {"city": "Vigo", "lat": 42.2118, "lon": -8.7394},
    "UD Las Palmas": {"city": "Las Palmas", "lat": 28.1001, "lon": -15.4571},
    "CD Leganés": {"city": "Madrid", "lat": 40.3571, "lon": -3.7608},
    "Deportivo Alavés": {"city": "Vitoria", "lat": 42.8371, "lon": -2.6882},
    "RCD Espanyol de Barcelona": {"city": "Barcelona", "lat": 41.3479, "lon": 2.0756},
    "Real Valladolid CF": {"city": "Valladolid", "lat": 41.6445, "lon": -4.7613},
    # Ligue 1
    "Paris Saint-Germain FC": {"city": "Paris", "lat": 48.8414, "lon": 2.2530},
    "Olympique de Marseille": {"city": "Marseille", "lat": 43.2699, "lon": 5.3958},
    "Olympique Lyonnais": {"city": "Lyon", "lat": 45.7654, "lon": 4.9820},
    "AS Monaco FC": {"city": "Monaco", "lat": 43.7274, "lon": 7.4157},
    "LOSC Lille": {"city": "Lille", "lat": 50.6120, "lon": 3.1305},
    "Lille OSC": {"city": "Lille", "lat": 50.6120, "lon": 3.1305},
    "OGC Nice": {"city": "Nice", "lat": 43.7050, "lon": 7.1926},
    "Stade Rennais FC 1901": {"city": "Rennes", "lat": 48.1075, "lon": -1.7129},
    "RC Lens": {"city": "Lens", "lat": 50.4327, "lon": 2.8151},
    "FC Nantes": {"city": "Nantes", "lat": 47.2558, "lon": -1.5247},
    "Montpellier HSC": {"city": "Montpellier", "lat": 43.6220, "lon": 3.8115},
    "RC Strasbourg Alsace": {"city": "Strasbourg", "lat": 48.5600, "lon": 7.7550},
    "Stade Brestois 29": {"city": "Brest", "lat": 48.4025, "lon": -4.4615},
    "Toulouse FC": {"city": "Toulouse", "lat": 43.5833, "lon": 1.4347},
    "Stade de Reims": {"city": "Reims", "lat": 49.2469, "lon": 4.0249},
    "Clermont Foot 63": {"city": "Clermont-Ferrand", "lat": 45.8159, "lon": 3.1266},
    "Le Havre AC": {"city": "Le Havre", "lat": 49.4987, "lon": 0.1694},
    "AJ Auxerre": {"city": "Auxerre", "lat": 47.7967, "lon": 3.5684},
    "AS Saint-Étienne": {"city": "Saint-Etienne", "lat": 45.4607, "lon": 4.3900},
    "Angers SCO": {"city": "Angers", "lat": 47.4605, "lon": -0.5326},
    "FC Lorient": {"city": "Lorient", "lat": 47.7502, "lon": -3.3663},
    "FC Metz": {"city": "Metz", "lat": 49.1097, "lon": 6.1828},
}


class MatchWeatherExtractor:
    """Fetch weather for each individual match based on home team location."""

    def __init__(self):
        self.client = httpx.Client(timeout=30)
        self.stats = {"api_calls": 0, "matches_enriched": 0, "fallbacks": 0, "errors": 0}

    def _get_team_location(self, team_name: str) -> Optional[Dict]:
        """Look up team location by name."""
        location = TEAM_LOCATIONS.get(team_name)
        if not location:
            # Try fuzzy match
            for key, val in TEAM_LOCATIONS.items():
                if key.lower() in team_name.lower() or team_name.lower() in key.lower():
                    return val
            logger.warning(f"No location found for team: {team_name}")
            return None
        return location

    def fetch_weather_for_location(self, lat: float, lon: float, city: str) -> Optional[Dict]:
        """Fetch current weather for given coordinates."""
        if not OPENWEATHER_API_KEY:
            logger.warning("OPENWEATHER_API_KEY not configured, using None")
            return None

        url = f"{OPENWEATHER_BASE_URL}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "fr",
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            self.stats["api_calls"] += 1
            data = response.json()

            return {
                "weather_city": city,
                "weather_lat": lat,
                "weather_lon": lon,
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "weather_main": data["weather"][0]["main"] if data.get("weather") else None,
                "weather_description": (
                    data["weather"][0]["description"] if data.get("weather") else None
                ),
                "wind_speed": data["wind"]["speed"],
                "wind_deg": data["wind"].get("deg", 0),
                "clouds": data["clouds"]["all"],
                "visibility": data.get("visibility", 0),
                "rain_1h": data.get("rain", {}).get("1h", 0),
                "snow_1h": data.get("snow", {}).get("1h", 0),
                "weather_fetched_at": datetime.now().isoformat(),
            }

        except httpx.HTTPError as e:
            logger.error(f"Weather API error for {city}: {e}")
            self.stats["errors"] += 1
            return None

    def enrich_matches_with_weather(self, matches_df: pd.DataFrame) -> pd.DataFrame:
        """
        For each match, fetch weather at the home team's city and merge.

        Args:
            matches_df: DataFrame with match data (must have homeTeam_name or home_team_name)

        Returns:
            DataFrame with weather columns added per match
        """
        if matches_df.empty:
            return matches_df

        # Determine home team column
        home_col = None
        for col in ["homeTeam_name", "home_team_name", "home_team"]:
            if col in matches_df.columns:
                home_col = col
                break

        if not home_col:
            logger.error(f"No home team column found. Columns: {matches_df.columns.tolist()}")
            return matches_df

        # Determine match id column
        id_col = None
        for col in ["id", "match_id"]:
            if col in matches_df.columns:
                id_col = col
                break

        logger.info(f"Enriching {len(matches_df)} matches with weather data")

        weather_records = []
        cities_cache = {}  # Cache weather by city to avoid duplicate API calls

        for idx, match in matches_df.iterrows():
            match_id = match.get(id_col, idx) if id_col else idx
            home_team = match[home_col]

            location = self._get_team_location(home_team)
            if not location:
                weather_records.append({"_match_idx": idx})
                self.stats["fallbacks"] += 1
                continue

            city = location["city"]

            # Use cache if same city already fetched today
            if city not in cities_cache:
                weather = self.fetch_weather_for_location(
                    location["lat"], location["lon"], city
                )
                cities_cache[city] = weather
                time.sleep(0.5)  # Rate limiting: stay well under 60 req/min
            else:
                weather = cities_cache[city]

            if weather:
                weather["_match_idx"] = idx
                weather_records.append(weather)
                self.stats["matches_enriched"] += 1
            else:
                weather_records.append({"_match_idx": idx})
                self.stats["fallbacks"] += 1

        # Merge weather data back to matches
        weather_df = pd.DataFrame(weather_records)
        if "_match_idx" in weather_df.columns:
            weather_df = weather_df.set_index("_match_idx")
            enriched = matches_df.join(weather_df, how="left")
        else:
            enriched = matches_df

        logger.info(f"Weather enrichment complete. Stats: {self.stats}")
        return enriched

    def fetch_and_save_match_weather(
        self, date_str: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load daily matches parquet, enrich with weather, and save.

        Args:
            date_str: Date string YYYYMMDD. If None, uses today.

        Returns:
            Enriched DataFrame
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        # Try to find matching daily matches file
        matches_file = LANDING_DIR / f"daily_matches_{date_str}.parquet"
        if not matches_file.exists():
            # Fallback: try all_matches files
            for year in [2024, 2023]:
                alt_file = LANDING_DIR / f"all_matches_{year}.parquet"
                if alt_file.exists():
                    matches_file = alt_file
                    break

        if not matches_file.exists():
            logger.error(f"No matches file found for date {date_str}")
            return pd.DataFrame()

        logger.info(f"Loading matches from {matches_file}")
        matches_df = pd.read_parquet(matches_file)

        # Enrich with weather
        enriched = self.enrich_matches_with_weather(matches_df)

        # Save enriched data
        output_path = LANDING_DIR / f"match_weather_{date_str}.parquet"
        enriched.to_parquet(output_path, index=False)
        logger.info(f"Saved match weather to {output_path}")

        # Also save standalone weather records for bronze loading
        weather_cols = [
            c for c in enriched.columns
            if c.startswith("weather_") or c in [
                "temperature", "feels_like", "humidity", "pressure",
                "wind_speed", "wind_deg", "clouds", "visibility",
                "rain_1h", "snow_1h",
            ]
        ]

        if weather_cols:
            # Add match identifiers
            id_col = "id" if "id" in enriched.columns else "match_id"
            if id_col in enriched.columns:
                weather_cols.insert(0, id_col)

            weather_only = enriched[weather_cols].dropna(subset=["temperature"])
            weather_output = LANDING_DIR / f"weather_match_{date_str}.parquet"
            weather_only.to_parquet(weather_output, index=False)
            logger.info(f"Saved {len(weather_only)} weather records to {weather_output}")

        return enriched

    def close(self):
        """Close HTTP client."""
        self.client.close()
        logger.info(f"MatchWeatherExtractor closed. Stats: {self.stats}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Match-Level Weather Extractor")
    parser.add_argument("--date", help="Date YYYYMMDD")
    parser.add_argument("--from-parquet", help="Path to matches parquet file")
    args = parser.parse_args()

    extractor = MatchWeatherExtractor()

    try:
        if args.from_parquet:
            df = pd.read_parquet(args.from_parquet)
            enriched = extractor.enrich_matches_with_weather(df)
            output = Path(args.from_parquet).stem + "_with_weather.parquet"
            enriched.to_parquet(LANDING_DIR / output, index=False)
            logger.info(f"Saved to {output}")
        else:
            extractor.fetch_and_save_match_weather(args.date)

    except Exception as e:
        logger.error(f"Match weather extraction failed: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
