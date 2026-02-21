"""
Création d'un index Elasticsearch combiné avec toutes les sources de données croisées.
Pour chaque match: résultat + valeur marchande des 2 équipes + météo de la ville
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
import json

# Configuration
ES_HOST = "localhost"
ES_PORT = 9200
DATA_DIR = Path("./data/landing")

# Mapping équipe -> ville (COMPLET)
TEAM_TO_CITY = {
    # Premier League (toutes les équipes 2023-2024)
    "Arsenal FC": "London",
    "Aston Villa FC": "Birmingham", 
    "AFC Bournemouth": "Bournemouth",
    "Brentford FC": "London",
    "Brighton & Hove Albion FC": "Brighton",
    "Burnley FC": "Manchester",  # proche de Manchester
    "Chelsea FC": "London",
    "Crystal Palace FC": "London",
    "Everton FC": "Liverpool",
    "Fulham FC": "London",
    "Liverpool FC": "Liverpool",
    "Luton Town FC": "London",  # proche de Londres
    "Manchester City FC": "Manchester",
    "Manchester United FC": "Manchester",
    "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "Nottingham",
    "Sheffield United FC": "Manchester",  # proche
    "Tottenham Hotspur FC": "London",
    "West Ham United FC": "London",
    "Wolverhampton Wanderers FC": "Birmingham",  # proche
    "Ipswich Town FC": "London",  # Est de l'Angleterre
    "Leicester City FC": "Birmingham",  # Midlands
    "Southampton FC": "London",  # Sud
    
    # La Liga (toutes les équipes 2023-2024)
    "Athletic Club": "Bilbao",
    "Club Atlético de Madrid": "Madrid",
    "Atlético de Madrid": "Madrid",
    "CA Osasuna": "Bilbao",  # Nord Espagne
    "Cádiz CF": "Sevilla",  # Andalousie
    "CD Leganés": "Madrid",
    "Deportivo Alavés": "Bilbao",  # Pays Basque
    "FC Barcelona": "Barcelona",
    "Getafe CF": "Madrid",
    "Girona FC": "Barcelona",  # Catalogne
    "Granada CF": "Sevilla",  # Andalousie
    "UD Las Palmas": "Madrid",  # Pas de météo Canaries
    "RCD Mallorca": "Barcelona",  # Méditerranée
    "RCD Espanyol de Barcelona": "Barcelona",
    "Rayo Vallecano de Madrid": "Madrid",
    "Real Betis Balompié": "Sevilla",
    "Real Madrid CF": "Madrid",
    "Real Sociedad de Fútbol": "Bilbao",  # San Sebastian proche
    "Real Valladolid CF": "Madrid",  # Castille
    "RC Celta de Vigo": "Bilbao",  # Nord-Ouest
    "Sevilla FC": "Sevilla",
    "UD Almería": "Sevilla",  # Sud
    "Valencia CF": "Valencia",
    "Villarreal CF": "Valencia",  # Proche
    
    # Ligue 1 (toutes les équipes 2023-2024)
    "AS Monaco FC": "Nice",  # Côte d'Azur
    "FC Nantes": "Nantes",
    "FC Lorient": "Nantes",  # Bretagne
    "FC Metz": "Strasbourg",  # Est
    "LOSC Lille": "Lille",
    "Lille OSC": "Lille",
    "Montpellier HSC": "Marseille",  # Sud
    "OGC Nice": "Nice",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "Paris Saint-Germain FC": "Paris",
    "RC Lens": "Lille",  # Nord
    "Racing Club de Lens": "Lille",
    "RC Strasbourg Alsace": "Strasbourg",
    "Stade Brestois 29": "Nantes",  # Bretagne
    "Stade Rennais FC 1901": "Rennes",
    "Stade de Reims": "Paris",  # Nord-Est
    "Toulouse FC": "Toulouse",
    "Clermont Foot 63": "Lyon",  # Centre
    "Le Havre AC": "Paris",  # Normandie
    "AJ Auxerre": "Paris",  # Bourgogne
    "AS Saint-Étienne": "Lyon",  # Proche
    "Angers SCO": "Nantes",  # Ouest
}


def load_matches():
    """Charge tous les matchs depuis les fichiers parquet."""
    print("📊 Chargement des matchs...")
    
    all_matches = []
    for year in [2023, 2024]:
        path = DATA_DIR / f"all_matches_{year}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            df['season'] = year
            all_matches.append(df)
            print(f"  ✅ {len(df)} matchs pour {year}")
    
    if all_matches:
        return pd.concat(all_matches, ignore_index=True)
    return pd.DataFrame()


def load_team_values():
    """Charge les valeurs marchandes des équipes."""
    print("💰 Chargement des valeurs marchandes...")
    
    # Chercher le fichier le plus récent
    files = list(DATA_DIR.glob("team_values_*.parquet"))
    if files:
        latest = max(files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest)
        print(f"  ✅ {len(df)} équipes chargées")
        return df
    return pd.DataFrame()


def load_weather():
    """Charge les données météo."""
    print("🌤️ Chargement de la météo...")
    
    # Chercher le fichier météo courant
    files = list(DATA_DIR.glob("weather_current_*.parquet"))
    if files:
        latest = max(files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest)
        print(f"  ✅ {len(df)} villes chargées")
        return df
    
    # Sinon météo équipes
    files = list(DATA_DIR.glob("weather_teams_*.parquet"))
    if files:
        latest = max(files, key=lambda x: x.stat().st_mtime)
        df = pd.read_parquet(latest)
        print(f"  ✅ {len(df)} villes chargées")
        return df
    
    return pd.DataFrame()


def create_combined_data(df_matches, df_values, df_weather):
    """
    Croise les données: chaque match enrichi avec valeurs d'équipes et météo.
    """
    print("\n🔄 Croisement des données...")
    
    # Créer un dict pour lookup rapide des valeurs
    values_by_team = {}
    if not df_values.empty:
        for _, row in df_values.iterrows():
            values_by_team[row['team_name']] = {
                'market_value': row.get('market_value_eur', row.get('market_value', 0)),
                'squad_size': row.get('squad_size', 0),
                'avg_age': row.get('avg_age', 0),
                'avg_player_value': row.get('avg_player_value_eur', row.get('avg_player_value', 0))
            }
        print(f"  📊 {len(values_by_team)} équipes mappées: {list(values_by_team.keys())[:5]}...")
    
    # Créer un dict pour lookup rapide de la météo par ville
    weather_by_city = {}
    if not df_weather.empty:
        for _, row in df_weather.iterrows():
            city = row.get('city', '')
            weather_by_city[city] = {
                'temperature': row.get('temperature', None),
                'humidity': row.get('humidity', None),
                'weather_main': row.get('weather_main', None),
                'weather_description': row.get('weather_description', None),
                'wind_speed': row.get('wind_speed', None),
                'clouds': row.get('clouds', None),
                'rain_1h': row.get('rain_1h', 0),
            }
    
    combined_records = []
    
    for _, match in df_matches.iterrows():
        # Données de base du match
        home_team = match.get('homeTeam_name', match.get('home_team_name', match.get('home_team', '')))
        away_team = match.get('awayTeam_name', match.get('away_team_name', match.get('away_team', '')))
        
        # Récupérer les valeurs marchandes
        home_value = values_by_team.get(home_team, {})
        away_value = values_by_team.get(away_team, {})
        
        # Récupérer la météo de la ville (match à domicile)
        home_city = TEAM_TO_CITY.get(home_team, "Unknown")
        weather = weather_by_city.get(home_city, {})
        
        # Calculer des métriques
        home_market_value = home_value.get('market_value', 0) or 0
        away_market_value = away_value.get('market_value', 0) or 0
        
        # Ratio de valeur (équipe la plus chère vs moins chère)
        if home_market_value > 0 and away_market_value > 0:
            value_ratio = max(home_market_value, away_market_value) / min(home_market_value, away_market_value)
        else:
            value_ratio = 1.0
        
        # Différence de valeur
        value_diff = home_market_value - away_market_value
        
        # Qui devrait gagner selon la valeur?
        if home_market_value > away_market_value:
            expected_winner = "HOME"
        elif away_market_value > home_market_value:
            expected_winner = "AWAY"
        else:
            expected_winner = "DRAW"
        
        # Résultat réel
        home_score = match.get('score_fullTime_home', match.get('home_score', 0))
        away_score = match.get('score_fullTime_away', match.get('away_score', 0))
        
        # Gérer les valeurs None
        home_score = int(home_score) if pd.notna(home_score) else 0
        away_score = int(away_score) if pd.notna(away_score) else 0
        
        if home_score > away_score:
            actual_winner = "HOME"
        elif away_score > home_score:
            actual_winner = "AWAY"
        else:
            actual_winner = "DRAW"
        
        # Upset detection (équipe moins valorisée gagne)
        is_upset = (expected_winner != actual_winner) and (expected_winner != "DRAW") and (actual_winner != "DRAW")
        
        # Créer l'enregistrement combiné
        # Gérer la date
        match_date = match.get('utcDate', match.get('utc_date', ''))
        if pd.notna(match_date) and match_date:
            match_date = str(match_date)
        else:
            match_date = None
        
        record = {
            # Identifiants
            "match_id": str(match.get('id', match.get('match_id', ''))),
            "match_date": match_date,
            "season": int(match.get('season', 2024)),
            "matchday": int(match.get('matchday', 0)) if pd.notna(match.get('matchday')) else 0,
            
            # Compétition
            "competition_code": match.get('competition_code', match.get('competition', '')),
            "competition_name": match.get('competition_name', ''),
            
            # Équipes
            "home_team": home_team,
            "away_team": away_team,
            "home_city": home_city,
            
            # Scores
            "home_score": int(home_score),
            "away_score": int(away_score),
            "total_goals": int(home_score + away_score),
            "goal_difference": int(home_score - away_score),
            "actual_winner": actual_winner,
            
            # Valeurs marchandes
            "home_market_value": home_market_value,
            "away_market_value": away_market_value,
            "combined_market_value": home_market_value + away_market_value,
            "market_value_ratio": round(value_ratio, 2),
            "market_value_diff": value_diff,
            "expected_winner": expected_winner,
            
            # Analytics
            "is_upset": is_upset,
            "upset_value": value_diff if is_upset and actual_winner == "AWAY" else (-value_diff if is_upset and actual_winner == "HOME" else 0),
            
            # Météo
            "weather_city": home_city,
            "temperature": weather.get('temperature'),
            "humidity": weather.get('humidity'),
            "weather_condition": weather.get('weather_main'),
            "weather_description": weather.get('weather_description'),
            "wind_speed": weather.get('wind_speed'),
            "clouds": weather.get('clouds'),
            "rain": weather.get('rain_1h', 0),
            
            # Métadonnées
            "indexed_at": datetime.now().isoformat(),
            "data_sources": ["football_api", "transfermarkt", "openweather"]
        }
        
        combined_records.append(record)
    
    print(f"  ✅ {len(combined_records)} matchs enrichis créés")
    
    # Stats
    upsets = sum(1 for r in combined_records if r['is_upset'])
    with_values = sum(1 for r in combined_records if r['home_market_value'] > 0)
    with_weather = sum(1 for r in combined_records if r['temperature'] is not None)
    
    print(f"\n📊 Statistiques du croisement:")
    print(f"   - Matchs avec valeurs marchandes: {with_values}/{len(combined_records)}")
    print(f"   - Matchs avec météo: {with_weather}/{len(combined_records)}")
    print(f"   - Upsets détectés: {upsets}")
    
    return combined_records


def index_to_elasticsearch(records):
    """Indexe les données combinées dans Elasticsearch."""
    print("\n📤 Indexation dans Elasticsearch...")
    
    es = Elasticsearch([f"http://{ES_HOST}:{ES_PORT}"])
    
    if not es.ping():
        print("❌ Impossible de se connecter à Elasticsearch")
        return False
    
    # Supprimer l'ancien index s'il existe
    index_name = "football_combined"
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"  🗑️ Index {index_name} supprimé")
    
    # Créer le mapping
    mapping = {
        "mappings": {
            "properties": {
                "match_id": {"type": "keyword"},
                "match_date": {"type": "date"},
                "season": {"type": "integer"},
                "matchday": {"type": "integer"},
                "competition_code": {"type": "keyword"},
                "competition_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "home_team": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "away_team": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "home_city": {"type": "keyword"},
                "home_score": {"type": "integer"},
                "away_score": {"type": "integer"},
                "total_goals": {"type": "integer"},
                "goal_difference": {"type": "integer"},
                "actual_winner": {"type": "keyword"},
                "home_market_value": {"type": "long"},
                "away_market_value": {"type": "long"},
                "combined_market_value": {"type": "long"},
                "market_value_ratio": {"type": "float"},
                "market_value_diff": {"type": "long"},
                "expected_winner": {"type": "keyword"},
                "is_upset": {"type": "boolean"},
                "upset_value": {"type": "long"},
                "weather_city": {"type": "keyword"},
                "temperature": {"type": "float"},
                "humidity": {"type": "integer"},
                "weather_condition": {"type": "keyword"},
                "weather_description": {"type": "text"},
                "wind_speed": {"type": "float"},
                "clouds": {"type": "integer"},
                "rain": {"type": "float"},
                "indexed_at": {"type": "date"},
                "data_sources": {"type": "keyword"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    es.indices.create(index=index_name, body=mapping)
    print(f"  ✅ Index {index_name} créé")
    
    # Indexer par bulk
    def generate_actions():
        for record in records:
            yield {
                "_index": index_name,
                "_id": f"{record['match_id']}_{record['season']}",
                "_source": record
            }
    
    success, failed = helpers.bulk(es, generate_actions(), stats_only=True)
    print(f"  ✅ {success} documents indexés")
    if failed:
        print(f"  ⚠️ {failed} échecs")
    
    return True


def create_kibana_data_view():
    """Crée le Data View Kibana pour l'index combiné."""
    import requests
    
    print("\n📊 Création du Data View Kibana...")
    
    data_view = {
        "data_view": {
            "title": "football_combined",
            "name": "Football Combined Analytics",
            "timeFieldName": "match_date"
        }
    }
    
    response = requests.post(
        "http://localhost:5601/api/data_views/data_view",
        headers={"kbn-xsrf": "true", "Content-Type": "application/json"},
        json=data_view
    )
    
    if response.status_code in [200, 201]:
        print("  ✅ Data View 'Football Combined Analytics' créé")
    else:
        print(f"  ⚠️ Data View: {response.status_code}")


def main():
    print("=" * 60)
    print("🔗 CRÉATION INDEX COMBINÉ - TOUTES SOURCES")
    print("=" * 60)
    print("Sources: Football API + Transfermarkt + OpenWeather")
    print("=" * 60)
    
    # 1. Charger les données
    df_matches = load_matches()
    df_values = load_team_values()
    df_weather = load_weather()
    
    if df_matches.empty:
        print("❌ Aucun match trouvé!")
        return
    
    # 2. Créer les données combinées
    combined = create_combined_data(df_matches, df_values, df_weather)
    
    # 3. Indexer dans Elasticsearch
    index_to_elasticsearch(combined)
    
    # 4. Créer le Data View Kibana
    create_kibana_data_view()
    
    # 5. Instructions
    print("\n" + "=" * 60)
    print("✅ INDEX COMBINÉ CRÉÉ AVEC SUCCÈS!")
    print("=" * 60)
    print("""
🎯 Dans Kibana:
   1. Rafraîchir la page (F5)
   2. Sélectionner "Football Combined Analytics"
   3. Tu as maintenant TOUTES les données croisées!

📊 Champs disponibles pour dashboards:
   
   MATCHS:
   - competition_code → PL, FL1, PD
   - home_team, away_team
   - home_score, away_score, total_goals
   - actual_winner → HOME, AWAY, DRAW
   
   VALEURS MARCHANDES:
   - home_market_value, away_market_value
   - combined_market_value (total des 2 équipes)
   - market_value_ratio (richest/poorest)
   - is_upset (équipe moins chère a gagné!)
   
   MÉTÉO:
   - temperature, humidity
   - weather_condition (Clear, Rain, Clouds...)
   - wind_speed, rain
   
📈 Idées de visualisations:
   1. Pie chart: actual_winner (victoires dom/ext/nul)
   2. Bar chart: total_goals par competition_code
   3. Metric: Moyenne de combined_market_value
   4. Heatmap: temperature vs total_goals
   5. Data table: Top 10 upsets (is_upset=true)
""")


if __name__ == "__main__":
    main()
