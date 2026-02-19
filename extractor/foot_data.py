from dotenv import load_dotenv
load_dotenv()
import os 
import pandas as pd
import httpx
from pathlib import Path
from datetime import datetime
import json

# configuration des chemins
API_BASE = "https://api.football-data.org/v4"
DATA_DIR = Path(os.getenv("DATA_DIR"))
LANDING_DIR = DATA_DIR / "landing"
RAW_DIR = DATA_DIR / "raw"

# création des dossiers si inexistants
LANDING_DIR.mkdir(parents=True, exist_ok= True)
RAW_DIR.mkdir(parents=True, exist_ok= True)

# HEADERS POUR L'API
HEADERS = {"X-Auth-Token": os.environ["FOOTBALL_API_TOKEN"]}

def _save_json(data, file_path)-> Path:
    """SAVE DATA AS JSON FILE"""
    path = RAW_DIR / file_path
    enriched = {"extracted_at": datetime.now().isoformat(), "data": data}
    path.write_text(json.dumps(enriched, indent =2, ensure_ascii= False), encoding = "utf-8")
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
def fetch_matches_save(season: int = 2024, leagues : list = None):
    if leagues is None: 
        leagues = ["PL", "FL1", "PD"]
    saved =[]
    frames = []
    try:
        with httpx.Client(timeout=60) as client:
            for code in leagues:
                print(f"récupération des matches pour {code}...")
                url = f"{API_BASE}/competitions/{code}/matches?season={season}"
                response = client.get(url, headers=HEADERS)
                response.raise_for_status()
                data= response.json()
                
                # sauvegarde du JSON brut
                saved.append(_save_json(data, f"matches_{code}_{season}.json"))
                # normalisation minimale
                matches = pd.json_normalize(data.get("matches", []))
                if not matches.empty:
                    matches["competitions"]= code
                    frames.append(matches)
                    print(f"{len(matches)} matches pour {code} récupérés.")
                else:
                    print(f"Aucun match trouvé pour {code}.")
            if frames:
                df = pd.concat(frames, ignore_index = True)
                df.to_parquet(LANDING_DIR / f"matches_{season}.parquet", index =False)
                print(f"Total de {len(df)} matches sauvegardés pour la saison {season}.")
            else:
                print("Aucun match récupéré pour les ligues spécifiées.")
    except httpx.HTTPError as e:
        print(f"Erreur lors de la récupération des matches: {e}")
        raise
if __name__ == "__main__":
    print("Démarrage de l'extraction des données footballistiques...")
    fetch_competitions()
    fetch_matches_save()