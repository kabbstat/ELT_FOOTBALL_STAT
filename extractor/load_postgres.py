import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.types import JSON
import os 
from dotenv import load_dotenv
import numpy as np 
import json

load_dotenv()
from urllib.parse import quote_plus

db_pass = quote_plus(os.environ['DB_PASS'])
db_url = f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
engine = create_engine(db_url)

def get_data_dir():
    """Retourne le bon chemin selon l'environnement"""
    # Dans Docker Airflow - chercher dans landing/
    if os.path.exists('/opt/airflow/data/landing'):
        return '/opt/airflow/data/landing'  
    elif os.path.exists('/opt/airflow/data'):
        return '/opt/airflow/data'
    else:
        return os.getenv("DATA_DIR", "./landing")

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
            if isinstance(sample, (list, dict, np.ndarray)):
                df[col] = df[col].apply(lambda x: json.dumps(x, default=str) if isinstance(x, (list, dict, np.ndarray)) else None)
    return df

def get_dtype_mapping(df):
    """Force les colonnes détectées comme JSON à utiliser le type JSON de Postgres"""
    dtypes = {}
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else ""
            if isinstance(sample, str) and (sample.startswith('{') or sample.startswith('[')):
                dtypes[col] = JSON
    return dtypes

def load_parquet_to_postgres(schema='bronze', season=2023):
    """
    Charge les fichiers Parquet dans PostgreSQL
    
    Args:
        schema (str): Schema PostgreSQL (bronze, silver, gold)
        season (int): Année de la saison (2023, 2024, etc.)
    """
    data_dir = get_data_dir()
    print(f"📂 Répertoire de données: {data_dir}")
    
    #  Liste des fichiers à charger avec leur nom dynamique
    files_to_load = [
        f'all_matches_{season}.parquet',  #  Fichier dynamique selon saison
        'competitions.parquet'             #  Fichier des compétitions
    ]
    
    for file in files_to_load:
        file_path = os.path.join(data_dir, file)
        
        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            print(f"⚠️ Fichier introuvable: {file_path}")
            continue
        
        # Nom de la table = nom du fichier sans extension
        # all_matches_2023.parquet → all_matches (on garde juste le préfixe)
        if file.startswith('all_matches'):
            table_name = 'all_matches'  #  Toujours la même table
        else:
            table_name = file.replace('.parquet', '')
        
        print(f"📥 Chargement: {file} → {schema}.{table_name}")
        
        # Charger et nettoyer les données
        df = pd.read_parquet(file_path)
        df = clean_data(df)
        dtype_mapping = get_dtype_mapping(df)
        
        # Charger dans PostgreSQL
        df.to_sql(
            table_name, 
            engine, 
            schema=schema,  #  Utiliser le schema (bronze, silver, gold)
            if_exists='append',  #  APPEND au lieu de REPLACE pour cumuler les saisons
            index=False, 
            dtype=dtype_mapping
        )
        
        print(f" Table {schema}.{table_name} chargée avec succès ({len(df)} lignes)")
    
    print(f" Chargement terminé pour la saison {season}")

if __name__ == "__main__":
    load_parquet_to_postgres()