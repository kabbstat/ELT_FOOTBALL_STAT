"""
Elasticsearch Data Loader
Charge les données combinées football + météo + valeurs marchandes dans Elasticsearch.
"""
from dotenv import load_dotenv
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Generator
import json
from elasticsearch import Elasticsearch, helpers

load_dotenv()

# Configuration
ES_HOST = os.getenv("ES_HOST", "localhost")
ES_PORT = os.getenv("ES_PORT", "9200")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"

# Index names
INDEX_MATCHES = "football_matches"
INDEX_WEATHER = "football_weather"
INDEX_TEAM_VALUES = "football_team_values"
INDEX_COMBINED = "football_analytics"


def get_es_client() -> Elasticsearch:
    """
    Crée une connexion Elasticsearch.
    
    Returns:
        Client Elasticsearch
    """
    es = Elasticsearch(
        [f"http://{ES_HOST}:{ES_PORT}"],
        request_timeout=60,
        retry_on_timeout=True,
        max_retries=3
    )
    
    # Vérifier la connexion
    if not es.ping():
        raise ConnectionError(f"Impossible de se connecter à Elasticsearch ({ES_HOST}:{ES_PORT})")
    
    print(f"✅ Connecté à Elasticsearch ({ES_HOST}:{ES_PORT})")
    return es


def create_indices(es: Elasticsearch):
    """
    Crée tous les indices nécessaires avec leurs mappings optimisés.
    """
    
    # 1. Index des matchs
    matches_mapping = {
        "mappings": {
            "properties": {
                "match_id": {"type": "keyword"},
                "competition_code": {"type": "keyword"},
                "competition_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "season": {"type": "integer"},
                "matchday": {"type": "integer"},
                "status": {"type": "keyword"},
                "utc_date": {"type": "date"},
                "home_team": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "short_name": {"type": "keyword"},
                        "crest": {"type": "keyword"}
                    }
                },
                "away_team": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "short_name": {"type": "keyword"},
                        "crest": {"type": "keyword"}
                    }
                },
                "score": {
                    "properties": {
                        "home_halftime": {"type": "integer"},
                        "away_halftime": {"type": "integer"},
                        "home_fulltime": {"type": "integer"},
                        "away_fulltime": {"type": "integer"},
                        "winner": {"type": "keyword"},
                        "total_goals": {"type": "integer"}
                    }
                },
                "indexed_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "5s"
        }
    }
    
    # 2. Index météo
    weather_mapping = {
        "mappings": {
            "properties": {
                "city": {"type": "keyword"},
                "country": {"type": "keyword"},
                "location": {"type": "geo_point"},
                "temperature": {"type": "float"},
                "feels_like": {"type": "float"},
                "humidity": {"type": "integer"},
                "pressure": {"type": "integer"},
                "weather_main": {"type": "keyword"},
                "weather_description": {"type": "text"},
                "wind_speed": {"type": "float"},
                "wind_deg": {"type": "integer"},
                "clouds": {"type": "integer"},
                "visibility": {"type": "integer"},
                "rain_1h": {"type": "float"},
                "snow_1h": {"type": "float"},
                "timestamp": {"type": "date"},
                "fetched_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    # 3. Index valeurs marchandes
    team_values_mapping = {
        "mappings": {
            "properties": {
                "team_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "competition_code": {"type": "keyword"},
                "competition_name": {"type": "text"},
                "country": {"type": "keyword"},
                "squad_size": {"type": "integer"},
                "avg_age": {"type": "float"},
                "market_value_eur": {"type": "long"},
                "avg_player_value_eur": {"type": "long"},
                "data_source": {"type": "keyword"},
                "fetched_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    # 4. Index combiné (analytics)
    combined_mapping = {
        "mappings": {
            "properties": {
                "match_id": {"type": "keyword"},
                "competition_code": {"type": "keyword"},
                "season": {"type": "integer"},
                "matchday": {"type": "integer"},
                "match_date": {"type": "date"},
                "home_team_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "away_team_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "home_score": {"type": "integer"},
                "away_score": {"type": "integer"},
                "total_goals": {"type": "integer"},
                "winner": {"type": "keyword"},
                "result_type": {"type": "keyword"},  # home_win, away_win, draw
                
                # Météo
                "weather": {
                    "properties": {
                        "temperature": {"type": "float"},
                        "condition": {"type": "keyword"},
                        "humidity": {"type": "integer"},
                        "wind_speed": {"type": "float"},
                        "is_rainy": {"type": "boolean"},
                        "is_cold": {"type": "boolean"}
                    }
                },
                
                # Valeurs marchandes
                "market_values": {
                    "properties": {
                        "home_team_value": {"type": "long"},
                        "away_team_value": {"type": "long"},
                        "value_difference": {"type": "long"},
                        "value_ratio": {"type": "float"},
                        "favorite": {"type": "keyword"},
                        "upset": {"type": "boolean"}
                    }
                },
                
                # KPIs calculés
                "kpis": {
                    "properties": {
                        "goals_per_match": {"type": "float"},
                        "home_advantage": {"type": "boolean"},
                        "weather_impact": {"type": "keyword"}
                    }
                },
                
                "indexed_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "5s"
        }
    }
    
    indices = {
        INDEX_MATCHES: matches_mapping,
        INDEX_WEATHER: weather_mapping,
        INDEX_TEAM_VALUES: team_values_mapping,
        INDEX_COMBINED: combined_mapping
    }
    
    for index_name, mapping in indices.items():
        if es.indices.exists(index=index_name):
            print(f"  ♻️ Suppression index existant: {index_name}")
            es.indices.delete(index=index_name)
        
        es.indices.create(index=index_name, body=mapping)
        print(f"  ✅ Index créé: {index_name}")


def load_matches_to_es(es: Elasticsearch, season: int = 2024) -> int:
    """
    Charge les matchs dans Elasticsearch.
    
    Args:
        es: Client Elasticsearch
        season: Saison à charger
    
    Returns:
        Nombre de documents indexés
    """
    parquet_path = LANDING_DIR / f"all_matches_{season}.parquet"
    
    if not parquet_path.exists():
        print(f"  ⚠️ Fichier non trouvé: {parquet_path}")
        return 0
    
    df = pd.read_parquet(parquet_path)
    print(f"  📊 {len(df)} matchs à indexer pour {season}")
    
    def generate_docs() -> Generator[Dict, None, None]:
        for _, row in df.iterrows():
            doc = {
                "_index": INDEX_MATCHES,
                "_id": f"{row.get('id', '')}_{season}",
                "_source": {
                    "match_id": str(row.get('id', '')),
                    "competition_code": row.get('competition_code', ''),
                    "season": season,
                    "matchday": int(row.get('matchday', 0)) if pd.notna(row.get('matchday')) else 0,
                    "status": row.get('status', ''),
                    "utc_date": row.get('utcDate', ''),
                    "home_team": {
                        "id": str(row.get('homeTeam_id', '')),
                        "name": row.get('homeTeam_name', ''),
                        "short_name": row.get('homeTeam_shortName', ''),
                        "crest": row.get('homeTeam_crest', '')
                    },
                    "away_team": {
                        "id": str(row.get('awayTeam_id', '')),
                        "name": row.get('awayTeam_name', ''),
                        "short_name": row.get('awayTeam_shortName', ''),
                        "crest": row.get('awayTeam_crest', '')
                    },
                    "score": {
                        "home_halftime": int(row.get('score_halfTime_home', 0)) if pd.notna(row.get('score_halfTime_home')) else 0,
                        "away_halftime": int(row.get('score_halfTime_away', 0)) if pd.notna(row.get('score_halfTime_away')) else 0,
                        "home_fulltime": int(row.get('score_fullTime_home', 0)) if pd.notna(row.get('score_fullTime_home')) else 0,
                        "away_fulltime": int(row.get('score_fullTime_away', 0)) if pd.notna(row.get('score_fullTime_away')) else 0,
                        "winner": row.get('score_winner', ''),
                        "total_goals": int((row.get('score_fullTime_home', 0) or 0) + (row.get('score_fullTime_away', 0) or 0))
                    },
                    "indexed_at": datetime.utcnow().isoformat()
                }
            }
            yield doc
    
    success, errors = helpers.bulk(es, generate_docs(), raise_on_error=False)
    
    if errors:
        print(f"  ⚠️ {len(errors)} erreurs d'indexation")
    
    return success


def load_weather_to_es(es: Elasticsearch) -> int:
    """
    Charge les données météo dans Elasticsearch.
    """
    # Chercher le fichier météo le plus récent
    weather_files = list(LANDING_DIR.glob("weather_current_*.parquet"))
    
    if not weather_files:
        print("  ⚠️ Aucun fichier météo trouvé")
        return 0
    
    latest_file = max(weather_files, key=lambda x: x.stat().st_mtime)
    df = pd.read_parquet(latest_file)
    print(f"  📊 {len(df)} enregistrements météo à indexer")
    
    def generate_docs() -> Generator[Dict, None, None]:
        for _, row in df.iterrows():
            doc = {
                "_index": INDEX_WEATHER,
                "_id": f"{row.get('city', '')}_{row.get('timestamp', '')}",
                "_source": {
                    "city": row.get('city', ''),
                    "country": row.get('country', ''),
                    "location": {
                        "lat": float(row.get('lat', 0)),
                        "lon": float(row.get('lon', 0))
                    },
                    "temperature": float(row.get('temperature', 0)),
                    "feels_like": float(row.get('feels_like', 0)),
                    "humidity": int(row.get('humidity', 0)),
                    "pressure": int(row.get('pressure', 0)),
                    "weather_main": row.get('weather_main', ''),
                    "weather_description": row.get('weather_description', ''),
                    "wind_speed": float(row.get('wind_speed', 0)),
                    "wind_deg": int(row.get('wind_deg', 0)),
                    "clouds": int(row.get('clouds', 0)),
                    "visibility": int(row.get('visibility', 0)),
                    "rain_1h": float(row.get('rain_1h', 0)),
                    "snow_1h": float(row.get('snow_1h', 0)),
                    "timestamp": row.get('timestamp', ''),
                    "fetched_at": row.get('fetched_at', datetime.utcnow().isoformat())
                }
            }
            yield doc
    
    success, errors = helpers.bulk(es, generate_docs(), raise_on_error=False)
    return success


def load_team_values_to_es(es: Elasticsearch) -> int:
    """
    Charge les valeurs marchandes dans Elasticsearch.
    """
    # Chercher le fichier le plus récent
    value_files = list(LANDING_DIR.glob("team_values_*.parquet"))
    
    if not value_files:
        print("  ⚠️ Aucun fichier valeurs équipes trouvé")
        return 0
    
    latest_file = max(value_files, key=lambda x: x.stat().st_mtime)
    df = pd.read_parquet(latest_file)
    print(f"  📊 {len(df)} équipes à indexer")
    
    def generate_docs() -> Generator[Dict, None, None]:
        for _, row in df.iterrows():
            doc = {
                "_index": INDEX_TEAM_VALUES,
                "_id": row.get('team_name', '').replace(' ', '_'),
                "_source": {
                    "team_name": row.get('team_name', ''),
                    "competition_code": row.get('competition_code', ''),
                    "country": row.get('country', ''),
                    "squad_size": int(row.get('squad_size', 0)),
                    "avg_age": float(row.get('avg_age', 0)),
                    "market_value_eur": int(row.get('market_value_eur', 0)),
                    "avg_player_value_eur": int(row.get('avg_player_value_eur', 0)) if pd.notna(row.get('avg_player_value_eur')) else 0,
                    "data_source": row.get('data_source', 'unknown'),
                    "fetched_at": row.get('fetched_at', datetime.utcnow().isoformat())
                }
            }
            yield doc
    
    success, errors = helpers.bulk(es, generate_docs(), raise_on_error=False)
    return success


def create_combined_analytics(es: Elasticsearch) -> int:
    """
    Crée l'index combiné analytics avec matchs + météo + valeurs.
    Cet index est utilisé pour le dashboard Kibana.
    """
    print("  🔄 Création des données combinées...")
    
    # Récupérer les matchs depuis l'index
    matches_response = es.search(
        index=INDEX_MATCHES,
        body={"query": {"match_all": {}}, "size": 10000}
    )
    matches = [hit["_source"] for hit in matches_response["hits"]["hits"]]
    
    if not matches:
        print("  ⚠️ Aucun match trouvé")
        return 0
    
    # Récupérer les valeurs des équipes
    team_values = {}
    try:
        values_response = es.search(
            index=INDEX_TEAM_VALUES,
            body={"query": {"match_all": {}}, "size": 1000}
        )
        for hit in values_response["hits"]["hits"]:
            team_values[hit["_source"]["team_name"]] = hit["_source"]["market_value_eur"]
    except:
        print("  ⚠️ Index team_values non disponible")
    
    # Récupérer la météo
    weather_data = {}
    try:
        weather_response = es.search(
            index=INDEX_WEATHER,
            body={"query": {"match_all": {}}, "size": 1000}
        )
        for hit in weather_response["hits"]["hits"]:
            weather_data[hit["_source"]["city"]] = hit["_source"]
    except:
        print("  ⚠️ Index weather non disponible")
    
    def generate_combined_docs() -> Generator[Dict, None, None]:
        for match in matches:
            home_team = match.get("home_team", {}).get("name", "")
            away_team = match.get("away_team", {}).get("name", "")
            home_score = match.get("score", {}).get("home_fulltime", 0)
            away_score = match.get("score", {}).get("away_fulltime", 0)
            
            # Valeurs marchandes
            home_value = team_values.get(home_team, 0)
            away_value = team_values.get(away_team, 0)
            value_diff = home_value - away_value
            value_ratio = home_value / away_value if away_value > 0 else 0
            
            # Déterminer le favori et si upset
            favorite = "home" if home_value > away_value else "away" if away_value > home_value else "equal"
            winner = match.get("score", {}).get("winner", "")
            upset = False
            if winner == "HOME_TEAM" and favorite == "away":
                upset = True
            elif winner == "AWAY_TEAM" and favorite == "home":
                upset = True
            
            # Résultat
            if winner == "HOME_TEAM":
                result_type = "home_win"
            elif winner == "AWAY_TEAM":
                result_type = "away_win"
            else:
                result_type = "draw"
            
            doc = {
                "_index": INDEX_COMBINED,
                "_id": match.get("match_id", ""),
                "_source": {
                    "match_id": match.get("match_id", ""),
                    "competition_code": match.get("competition_code", ""),
                    "season": match.get("season", 0),
                    "matchday": match.get("matchday", 0),
                    "match_date": match.get("utc_date", ""),
                    "home_team_name": home_team,
                    "away_team_name": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "total_goals": home_score + away_score,
                    "winner": winner,
                    "result_type": result_type,
                    "market_values": {
                        "home_team_value": home_value,
                        "away_team_value": away_value,
                        "value_difference": value_diff,
                        "value_ratio": round(value_ratio, 2),
                        "favorite": favorite,
                        "upset": upset
                    },
                    "kpis": {
                        "goals_per_match": home_score + away_score,
                        "home_advantage": winner == "HOME_TEAM"
                    },
                    "indexed_at": datetime.utcnow().isoformat()
                }
            }
            yield doc
    
    success, errors = helpers.bulk(es, generate_combined_docs(), raise_on_error=False)
    return success


def index_all_data():
    """
    Fonction principale: indexe toutes les données dans Elasticsearch.
    """
    print("=" * 60)
    print("🔍 INDEXATION ELASTICSEARCH")
    print("=" * 60)
    
    try:
        es = get_es_client()
        
        # 1. Créer les indices
        print("\n📋 Création des indices...")
        create_indices(es)
        
        # 2. Charger les matchs
        print("\n⚽ Indexation des matchs...")
        matches_2023 = load_matches_to_es(es, 2023)
        matches_2024 = load_matches_to_es(es, 2024)
        print(f"  ✅ Total matchs: {matches_2023 + matches_2024}")
        
        # 3. Charger la météo
        print("\n🌤️ Indexation météo...")
        weather_count = load_weather_to_es(es)
        print(f"  ✅ Enregistrements météo: {weather_count}")
        
        # 4. Charger les valeurs équipes
        print("\n💰 Indexation valeurs équipes...")
        teams_count = load_team_values_to_es(es)
        print(f"  ✅ Équipes: {teams_count}")
        
        # 5. Créer l'index combiné
        print("\n📊 Création index analytics combiné...")
        combined_count = create_combined_analytics(es)
        print(f"  ✅ Documents analytics: {combined_count}")
        
        print("\n" + "=" * 60)
        print("✅ INDEXATION ELASTICSEARCH TERMINÉE")
        print("=" * 60)
        print(f"\n📊 Accès Kibana: http://localhost:5601")
        print(f"📊 Accès Elasticsearch: http://localhost:9200")
        
    except ConnectionError as e:
        print(f"❌ Erreur de connexion: {e}")
        raise
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise


if __name__ == "__main__":
    index_all_data()
