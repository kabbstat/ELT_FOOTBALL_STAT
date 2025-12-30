from dotenv import load_dotenv 
import os 
import pandas as pd
import httpx
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from pathlib import Path 
from sqlalchemy import create_engine
from typing import Optional, Dict, Any 

load_dotenv()
API_BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token" : os.environ["FOOTBALL_API_TOKEN"]}
SNOWFLAKE_CONFIG ={
    'user': os.environ["SNOWFLAKE_USER"],
    'password': os.environ["SNOWFLAKE_PASSWORD"],
    'account' : os.environ["SNOWFLAKE_ACCOUNT"],
    'warehouse' : os.environ["SNOWFLAKE_WAREHOUSE"],
    'database' : 'FOOTBALL_STATS',
    'schema' : 'RAW',

}
def get_snowflake_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

def fetch_load_competitions():
    url = f"{API_BASE}/competitions"
    with httpx.Client(timeout=60) as client : 
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
    competitions = data.get('competitions', [])
    df = pd.DataFrame(competitions)
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE IF EXISTS RAW.COMPETITIONS")
    write_pandas(
            conn = conn, 
            df= df,
            table_name = 'COMPETITIONS',
            database = 'FOOTBALL_STATS',
            schema ='RAW',
            auto_create_table = True,
            overwrite = False
        )
    conn.close()
    print(f"{len(df)} competitions chargé dans snowflake")
    return [comp['id'] for comp in competitions]

def fetch_and_load_matches(seasons=[]):
    competitions_ids = fetch_load_competitions()
    all_matches =[]
    for season in seasons : 
        for comp_id in competitions_ids:
            print(f"extraction saison {season}")
            url = f"{API_BASE}/competitions/{comp_id}/matches?season={season}"
            with httpx.Client(timeout=60) as client:
                response = client.get(url, headers = HEADERS)
                response.raise_for_status()
                data = response.json()
            matches = data.get('matches', [])
            for match in matches:
                match['season'] = season
                match['competition_id'] = comp_id
            all_matches.extend(matches)
    df = pd.DataFrame(all_matches)
    with get_snowflake_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE IF EXISTS RAW.MATCHES")
            write_pandas(
                conn = conn, 
                df = df,
                table_name= 'MATCHES',
                database = 'FOOTBALL_STATS',
                schema = 'RAW',
                auto_create_table = True,
                overwrite = False
        )
if __name__== "__main__":
    fetch_load_competitions()
    fetch_and_load_matches(seasons=[2021, 2022, 2023, 2024])
