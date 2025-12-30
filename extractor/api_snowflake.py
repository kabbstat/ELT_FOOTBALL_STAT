from dotenv import load_dotenv 
import os 
import pandas as pd
import httpx
import json
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from pathlib import Path 
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine
from typing import Optional, Dict, Any 
import time

load_dotenv()
API_BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token" : os.environ["FOOTBALL_API_TOKEN"]}
def get_snowflake_engine():
    """Crée un moteur SQLAlchemy pour Snowflake"""
    return create_engine(URL(
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database='FOOTBALL_STATS',
        schema='RAW'
    ))


def fetch_load_competitions():
    url = f"{API_BASE}/competitions"
    with httpx.Client(timeout=60) as client : 
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
    competitions = data.get('competitions', [])
    df = pd.DataFrame(competitions)
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (dict,list))).any():
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict,list))else x)
    engine = get_snowflake_engine()
    df.to_sql(
        'competitions',
        engine,
        if_exists='replace',  # Remplace la table (TRUNCATE + INSERT)
        index=False,
        method='multi',
        chunksize=1000
    )
    print(f"{len(df)} competitions chargé dans snowflake")
    return [comp['id'] for comp in competitions]

def fetch_and_load_matches(seasons=[]):
    competitions_ids = fetch_load_competitions()
    all_matches =[]
    for season in seasons : 
        for comp_id in competitions_ids:
            print(f"extraction saison {season}")
            url = f"{API_BASE}/competitions/{comp_id}/matches?season={season}"
            try:    
                with httpx.Client(timeout=60) as client:
                    response = client.get(url, headers = HEADERS)
                    response.raise_for_status()
                    data = response.json()
                matches = data.get('matches', [])
                for match in matches:
                    match['season'] = season
                    match['competition_id'] = comp_id
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    print(f"  ⚠️ Accès refusé (plan gratuit) - compétition {comp_id}, saison {season}")
                elif e.response.status_code == 404:
                    print(f"  ⚠️ Pas de données - compétition {comp_id}, saison {season}")
                else:
                    print(f"  ❌ Erreur HTTP {e.response.status_code}")
                continue  # ✅ Passer à la compétition suivante
            all_matches.extend(matches)
            time.sleep(6)
    df = pd.DataFrame(all_matches)
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (dict,list))).any():
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x,(dict,list)) else x)
    engine = get_snowflake_engine()
    df.to_sql(
        'matches',
        engine,
        if_exists='replace',
        index=False,
        method='multi',
        chunksize=1000
    )
    print(f"✅ {len(df)} matchs chargés dans Snowflake RAW.MATCHES")
if __name__== "__main__":
    fetch_and_load_matches(seasons=[2021, 2022, 2023, 2024])
