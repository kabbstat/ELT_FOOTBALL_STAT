from dotenv import load_dotenv
import os 
import pandas as pd
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json
import time  # Import nécessaire pour le rate limiting
load_dotenv()

# Configuration
API_BASE = "https://api.football-data.org/v4"
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))# Valeur par défaut par sécurité
LANDING_DIR = DATA_DIR / "landing"
RAW_DIR = DATA_DIR / "raw"
HEADERS = {"X-Auth-Token": os.environ["FOOTBALL_API_TOKEN"]}
# Création des dossiers
LANDING_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

def _save_json(data, filename: str) -> Path:
    path = LANDING_DIR / filename
    enriched = {"extracted_at": datetime.now().isoformat(), "data": data}
    path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False),encoding="utf-8")
    return path 
def fetch_competitions():
    """FETCH COMPETITONS FROM THE API"""
    url = f"{API_BASE}/competitions"
    try: 
        with httpx.Client(timeout=60) as client :
            response = client.get(url, headers = HEADERS)
            response.raise_for_status()
            data = response.json()
        # Normalisation minimale
        if "competitions" in data:
            comp = pd.json_normalize(data["competitions"])
            comp.to_parquet(LANDING_DIR / "competitions.parquet", index=False)
            print(f"comp saved with {len(comp)} records.")
        else: 
            print("No competitions data found in the response.")
    except httpx.HTTPError as e:
        print(f"Error fetching competitions: {e}")
        raise
def fetch_matches_save(season: int = 2024, leagues: list = None):
    if leagues is None :
        leagues= ["PL","FL1","PD"]
    frames = []
    with httpx.Client(timeout=60) as client: 
        for code in leagues: 
            print(f"Récupération des matches pour {code}")
            try :
                    url = f"{API_BASE}/competitions/{code}/matches?season={season}"
                    response = client.get(url , headers = HEADERS)
                    if response.status_code == 429:
                        print (f"Rate limit atteint pour {code}. Pause de 60s...")
                        time.sleep(61)
                        response = client.get(url, headers=HEADERS) # Retry
                    response.raise_for_status()
                    data = response.json()
                    _save_json(data, f"matches_{code}_{season}.json")
                    # Aplatissement avec séparateur pour éviter les conflits de noms
                    matches = pd.json_normalize(data.get("matches", []), sep="_")
                    if not matches.empty:
                        matches["competition_code"] = code
                        frames.append(matches)
                        print(f"{len(matches)} matches récupérés.")
                    time.sleep(6) 
            except httpx.HTTPError as e:
                    print(f"Erreur lors de la récupération des matches pour {code} : {e}")
                    continue
        if frames:
            all_matches = pd.concat(frames, ignore_index= True)
            output_path = LANDING_DIR / f"all_matches_{season}.parquet"
            all_matches.to_parquet(output_path, index= False)
            print(f"Tous les matches sauvegardés dans {output_path}")
if __name__ == "__main__":
    fetch_competitions()
    fetch_matches_save()
