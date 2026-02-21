"""
OpenWeather API Extractor
Récupère les données météo pour les villes des matchs de football.
"""
from dotenv import load_dotenv
import os
import pandas as pd
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json
import time

load_dotenv()

# Configuration
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"

# Création des dossiers
LANDING_DIR.mkdir(parents=True, exist_ok=True)

# Mapping des équipes vers leurs villes avec coordonnées
TEAM_CITIES = {
    # Premier League (Angleterre)
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
    
    # La Liga (Espagne)
    "FC Barcelona": {"city": "Barcelona", "lat": 41.3809, "lon": 2.1228},
    "Real Madrid CF": {"city": "Madrid", "lat": 40.4531, "lon": -3.6883},
    "Atlético de Madrid": {"city": "Madrid", "lat": 40.4361, "lon": -3.5994},
    "Sevilla FC": {"city": "Sevilla", "lat": 37.3840, "lon": -5.9705},
    "Real Sociedad de Fútbol": {"city": "San Sebastian", "lat": 43.3015, "lon": -1.9736},
    "Real Betis Balompié": {"city": "Sevilla", "lat": 37.3567, "lon": -5.9818},
    "Villarreal CF": {"city": "Villarreal", "lat": 39.9440, "lon": -0.1036},
    "Athletic Club": {"city": "Bilbao", "lat": 43.2641, "lon": -2.9494},
    "Valencia CF": {"city": "Valencia", "lat": 39.4746, "lon": -0.3583},
    
    # Ligue 1 (France)
    "Paris Saint-Germain FC": {"city": "Paris", "lat": 48.8414, "lon": 2.2530},
    "Olympique de Marseille": {"city": "Marseille", "lat": 43.2699, "lon": 5.3958},
    "Olympique Lyonnais": {"city": "Lyon", "lat": 45.7654, "lon": 4.9820},
    "AS Monaco FC": {"city": "Monaco", "lat": 43.7274, "lon": 7.4157},
    "LOSC Lille": {"city": "Lille", "lat": 50.6120, "lon": 3.1305},
    "OGC Nice": {"city": "Nice", "lat": 43.7050, "lon": 7.1926},
    "Stade Rennais FC 1901": {"city": "Rennes", "lat": 48.1075, "lon": -1.7129},
    "RC Lens": {"city": "Lens", "lat": 50.4327, "lon": 2.8151},
    "FC Nantes": {"city": "Nantes", "lat": 47.2558, "lon": -1.5247},
    "Montpellier HSC": {"city": "Montpellier", "lat": 43.6220, "lon": 3.8115},
    "RC Strasbourg Alsace": {"city": "Strasbourg", "lat": 48.5600, "lon": 7.7550},
    "Stade Brestois 29": {"city": "Brest", "lat": 48.4025, "lon": -4.4615},
    "Toulouse FC": {"city": "Toulouse", "lat": 43.5833, "lon": 1.4347},
    "Stade de Reims": {"city": "Reims", "lat": 49.2469, "lon": 4.0249},
}

# Villes principales couvertes (pour météo générale)
MAIN_CITIES = [
    {"city": "London", "lat": 51.5074, "lon": -0.1278, "country": "UK"},
    {"city": "Manchester", "lat": 53.4808, "lon": -2.2426, "country": "UK"},
    {"city": "Liverpool", "lat": 53.4084, "lon": -2.9916, "country": "UK"},
    {"city": "Paris", "lat": 48.8566, "lon": 2.3522, "country": "FR"},
    {"city": "Lyon", "lat": 45.7640, "lon": 4.8357, "country": "FR"},
    {"city": "Marseille", "lat": 43.2965, "lon": 5.3698, "country": "FR"},
    {"city": "Madrid", "lat": 40.4168, "lon": -3.7038, "country": "ES"},
    {"city": "Barcelona", "lat": 41.3851, "lon": 2.1734, "country": "ES"},
    {"city": "Sevilla", "lat": 37.3891, "lon": -5.9845, "country": "ES"},
]

# Données météo statiques (fallback si API non disponible)
# Données typiques pour février dans chaque ville
STATIC_WEATHER_DATA = {
    "London": {"temperature": 8.5, "feels_like": 6.2, "humidity": 78, "pressure": 1015, 
               "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 4.5, 
               "wind_deg": 220, "clouds": 75, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
               "country": "UK", "lat": 51.5074, "lon": -0.1278},
    "Manchester": {"temperature": 7.2, "feels_like": 4.8, "humidity": 82, "pressure": 1012,
                   "weather_main": "Rain", "weather_description": "pluie légère", "wind_speed": 5.2,
                   "wind_deg": 245, "clouds": 90, "visibility": 8000, "rain_1h": 0.5, "snow_1h": 0,
                   "country": "UK", "lat": 53.4808, "lon": -2.2426},
    "Liverpool": {"temperature": 7.8, "feels_like": 5.1, "humidity": 80, "pressure": 1013,
                  "weather_main": "Clouds", "weather_description": "couvert", "wind_speed": 4.8,
                  "wind_deg": 230, "clouds": 85, "visibility": 9000, "rain_1h": 0, "snow_1h": 0,
                  "country": "UK", "lat": 53.4084, "lon": -2.9916},
    "Paris": {"temperature": 9.5, "feels_like": 7.8, "humidity": 72, "pressure": 1018,
              "weather_main": "Clear", "weather_description": "ciel dégagé", "wind_speed": 3.2,
              "wind_deg": 180, "clouds": 15, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
              "country": "FR", "lat": 48.8566, "lon": 2.3522},
    "Lyon": {"temperature": 8.2, "feels_like": 6.5, "humidity": 68, "pressure": 1020,
             "weather_main": "Clouds", "weather_description": "partiellement nuageux", "wind_speed": 2.8,
             "wind_deg": 160, "clouds": 40, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
             "country": "FR", "lat": 45.7640, "lon": 4.8357},
    "Marseille": {"temperature": 12.5, "feels_like": 11.2, "humidity": 65, "pressure": 1019,
                  "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 4.5,
                  "wind_deg": 320, "clouds": 10, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                  "country": "FR", "lat": 43.2965, "lon": 5.3698},
    "Madrid": {"temperature": 11.8, "feels_like": 10.5, "humidity": 55, "pressure": 1022,
               "weather_main": "Clear", "weather_description": "ciel dégagé", "wind_speed": 3.5,
               "wind_deg": 200, "clouds": 5, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
               "country": "ES", "lat": 40.4168, "lon": -3.7038},
    "Barcelona": {"temperature": 14.2, "feels_like": 13.5, "humidity": 62, "pressure": 1020,
                  "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 2.5,
                  "wind_deg": 150, "clouds": 8, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                  "country": "ES", "lat": 41.3851, "lon": 2.1734},
    "Sevilla": {"temperature": 16.5, "feels_like": 15.8, "humidity": 58, "pressure": 1018,
                "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 3.0,
                "wind_deg": 180, "clouds": 5, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                "country": "ES", "lat": 37.3891, "lon": -5.9845},
    "Birmingham": {"temperature": 7.5, "feels_like": 5.2, "humidity": 79, "pressure": 1014,
                   "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 4.0,
                   "wind_deg": 210, "clouds": 70, "visibility": 9500, "rain_1h": 0, "snow_1h": 0,
                   "country": "UK", "lat": 52.5090, "lon": -1.8848},
    "Newcastle": {"temperature": 6.2, "feels_like": 3.5, "humidity": 85, "pressure": 1010,
                  "weather_main": "Rain", "weather_description": "pluie", "wind_speed": 5.5,
                  "wind_deg": 260, "clouds": 95, "visibility": 7000, "rain_1h": 1.2, "snow_1h": 0,
                  "country": "UK", "lat": 54.9756, "lon": -1.6217},
    "Brighton": {"temperature": 9.0, "feels_like": 7.5, "humidity": 75, "pressure": 1016,
                 "weather_main": "Clouds", "weather_description": "partiellement nuageux", "wind_speed": 5.0,
                 "wind_deg": 200, "clouds": 50, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                 "country": "UK", "lat": 50.8619, "lon": -0.0832},
    "Nottingham": {"temperature": 7.0, "feels_like": 4.8, "humidity": 81, "pressure": 1013,
                   "weather_main": "Clouds", "weather_description": "couvert", "wind_speed": 4.2,
                   "wind_deg": 225, "clouds": 80, "visibility": 9000, "rain_1h": 0, "snow_1h": 0,
                   "country": "UK", "lat": 52.9400, "lon": -1.1329},
    "Wolverhampton": {"temperature": 7.3, "feels_like": 5.0, "humidity": 80, "pressure": 1014,
                      "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 4.0,
                      "wind_deg": 215, "clouds": 72, "visibility": 9200, "rain_1h": 0, "snow_1h": 0,
                      "country": "UK", "lat": 52.5903, "lon": -2.1305},
    "Bournemouth": {"temperature": 9.5, "feels_like": 8.0, "humidity": 74, "pressure": 1017,
                    "weather_main": "Clouds", "weather_description": "partiellement nuageux", "wind_speed": 4.5,
                    "wind_deg": 195, "clouds": 45, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                    "country": "UK", "lat": 50.7353, "lon": -1.8384},
    "San Sebastian": {"temperature": 10.5, "feels_like": 9.2, "humidity": 70, "pressure": 1016,
                      "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 3.5,
                      "wind_deg": 270, "clouds": 60, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                      "country": "ES", "lat": 43.3015, "lon": -1.9736},
    "Bilbao": {"temperature": 11.0, "feels_like": 9.8, "humidity": 72, "pressure": 1015,
               "weather_main": "Rain", "weather_description": "pluie légère", "wind_speed": 3.8,
               "wind_deg": 280, "clouds": 75, "visibility": 8500, "rain_1h": 0.3, "snow_1h": 0,
               "country": "ES", "lat": 43.2641, "lon": -2.9494},
    "Valencia": {"temperature": 15.0, "feels_like": 14.2, "humidity": 60, "pressure": 1019,
                 "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 2.8,
                 "wind_deg": 160, "clouds": 10, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                 "country": "ES", "lat": 39.4746, "lon": -0.3583},
    "Villarreal": {"temperature": 14.5, "feels_like": 13.8, "humidity": 62, "pressure": 1019,
                   "weather_main": "Clear", "weather_description": "ciel dégagé", "wind_speed": 2.5,
                   "wind_deg": 150, "clouds": 8, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                   "country": "ES", "lat": 39.9440, "lon": -0.1036},
    "Monaco": {"temperature": 13.5, "feels_like": 12.8, "humidity": 65, "pressure": 1018,
               "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 3.0,
               "wind_deg": 140, "clouds": 12, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
               "country": "FR", "lat": 43.7274, "lon": 7.4157},
    "Nice": {"temperature": 13.0, "feels_like": 12.2, "humidity": 64, "pressure": 1019,
             "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 2.8,
             "wind_deg": 135, "clouds": 10, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
             "country": "FR", "lat": 43.7050, "lon": 7.1926},
    "Lille": {"temperature": 7.8, "feels_like": 5.5, "humidity": 80, "pressure": 1014,
              "weather_main": "Clouds", "weather_description": "couvert", "wind_speed": 4.5,
              "wind_deg": 240, "clouds": 85, "visibility": 9000, "rain_1h": 0, "snow_1h": 0,
              "country": "FR", "lat": 50.6120, "lon": 3.1305},
    "Lens": {"temperature": 7.5, "feels_like": 5.0, "humidity": 82, "pressure": 1013,
             "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 4.8,
             "wind_deg": 235, "clouds": 80, "visibility": 8800, "rain_1h": 0, "snow_1h": 0,
             "country": "FR", "lat": 50.4327, "lon": 2.8151},
    "Rennes": {"temperature": 9.5, "feels_like": 7.8, "humidity": 78, "pressure": 1016,
               "weather_main": "Clouds", "weather_description": "partiellement nuageux", "wind_speed": 4.0,
               "wind_deg": 220, "clouds": 55, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
               "country": "FR", "lat": 48.1075, "lon": -1.7129},
    "Nantes": {"temperature": 10.2, "feels_like": 8.8, "humidity": 76, "pressure": 1017,
               "weather_main": "Clouds", "weather_description": "partiellement nuageux", "wind_speed": 3.8,
               "wind_deg": 215, "clouds": 50, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
               "country": "FR", "lat": 47.2558, "lon": -1.5247},
    "Montpellier": {"temperature": 12.8, "feels_like": 12.0, "humidity": 62, "pressure": 1019,
                    "weather_main": "Clear", "weather_description": "ensoleillé", "wind_speed": 3.2,
                    "wind_deg": 170, "clouds": 15, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                    "country": "FR", "lat": 43.6220, "lon": 3.8115},
    "Strasbourg": {"temperature": 6.5, "feels_like": 4.0, "humidity": 75, "pressure": 1018,
                   "weather_main": "Clouds", "weather_description": "nuageux", "wind_speed": 3.5,
                   "wind_deg": 190, "clouds": 65, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                   "country": "FR", "lat": 48.5600, "lon": 7.7550},
    "Brest": {"temperature": 10.0, "feels_like": 8.2, "humidity": 82, "pressure": 1012,
              "weather_main": "Rain", "weather_description": "pluie légère", "wind_speed": 5.5,
              "wind_deg": 260, "clouds": 90, "visibility": 7500, "rain_1h": 0.8, "snow_1h": 0,
              "country": "FR", "lat": 48.4025, "lon": -4.4615},
    "Toulouse": {"temperature": 11.5, "feels_like": 10.5, "humidity": 68, "pressure": 1018,
                 "weather_main": "Clear", "weather_description": "ciel dégagé", "wind_speed": 3.0,
                 "wind_deg": 175, "clouds": 20, "visibility": 10000, "rain_1h": 0, "snow_1h": 0,
                 "country": "FR", "lat": 43.5833, "lon": 1.4347},
    "Reims": {"temperature": 7.0, "feels_like": 5.0, "humidity": 78, "pressure": 1016,
              "weather_main": "Clouds", "weather_description": "couvert", "wind_speed": 3.8,
              "wind_deg": 200, "clouds": 75, "visibility": 9500, "rain_1h": 0, "snow_1h": 0,
              "country": "FR", "lat": 49.2469, "lon": 4.0249},
}


def _save_json(data: dict, filename: str) -> Path:
    """Sauvegarde les données JSON avec métadonnées"""
    path = LANDING_DIR / filename
    enriched = {
        "extracted_at": datetime.now().isoformat(),
        "source": "openweather_api",
        "data": data
    }
    path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def fetch_current_weather(lat: float, lon: float, city: str) -> Optional[Dict]:
    """
    Récupère la météo actuelle pour une ville donnée.
    
    Args:
        lat: Latitude
        lon: Longitude
        city: Nom de la ville
    
    Returns:
        Dict avec les données météo ou None si erreur
    """
    if not OPENWEATHER_API_KEY:
        print("⚠️ OPENWEATHER_API_KEY non configurée")
        return None
    
    url = f"{OPENWEATHER_BASE_URL}/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",  # Celsius
        "lang": "fr"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "city": city,
                "lat": lat,
                "lon": lon,
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "weather_main": data["weather"][0]["main"] if data["weather"] else None,
                "weather_description": data["weather"][0]["description"] if data["weather"] else None,
                "weather_icon": data["weather"][0]["icon"] if data["weather"] else None,
                "wind_speed": data["wind"]["speed"],
                "wind_deg": data["wind"].get("deg", 0),
                "clouds": data["clouds"]["all"],
                "visibility": data.get("visibility", 0),
                "rain_1h": data.get("rain", {}).get("1h", 0),
                "snow_1h": data.get("snow", {}).get("1h", 0),
                "timestamp": datetime.utcfromtimestamp(data["dt"]).isoformat(),
                "sunrise": datetime.utcfromtimestamp(data["sys"]["sunrise"]).isoformat(),
                "sunset": datetime.utcfromtimestamp(data["sys"]["sunset"]).isoformat(),
                "fetched_at": datetime.now().isoformat()
            }
    
    except httpx.HTTPError as e:
        print(f"❌ Erreur météo pour {city}: {e}")
        return None


def fetch_forecast_5days(lat: float, lon: float, city: str) -> Optional[List[Dict]]:
    """
    Récupère les prévisions météo sur 5 jours (par tranches de 3h).
    
    Args:
        lat: Latitude
        lon: Longitude  
        city: Nom de la ville
    
    Returns:
        Liste des prévisions ou None si erreur
    """
    if not OPENWEATHER_API_KEY:
        print("⚠️ OPENWEATHER_API_KEY non configurée")
        return None
    
    url = f"{OPENWEATHER_BASE_URL}/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "fr"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            forecasts = []
            for item in data.get("list", []):
                forecasts.append({
                    "city": city,
                    "lat": lat,
                    "lon": lon,
                    "forecast_dt": datetime.utcfromtimestamp(item["dt"]).isoformat(),
                    "temperature": item["main"]["temp"],
                    "feels_like": item["main"]["feels_like"],
                    "humidity": item["main"]["humidity"],
                    "weather_main": item["weather"][0]["main"] if item["weather"] else None,
                    "weather_description": item["weather"][0]["description"] if item["weather"] else None,
                    "wind_speed": item["wind"]["speed"],
                    "clouds": item["clouds"]["all"],
                    "rain_3h": item.get("rain", {}).get("3h", 0),
                    "snow_3h": item.get("snow", {}).get("3h", 0),
                    "pop": item.get("pop", 0),  # Probability of precipitation
                    "fetched_at": datetime.now().isoformat()
                })
            
            return forecasts
    
    except httpx.HTTPError as e:
        print(f"❌ Erreur prévisions pour {city}: {e}")
        return None


def fetch_all_cities_weather() -> pd.DataFrame:
    """
    Récupère la météo actuelle pour toutes les villes principales.
    
    Returns:
        DataFrame avec la météo de toutes les villes
    """
    print("🌤️ Récupération météo pour les villes principales...")
    
    weather_data = []
    
    for city_info in MAIN_CITIES:
        print(f"  📍 {city_info['city']}...")
        weather = fetch_current_weather(
            lat=city_info["lat"],
            lon=city_info["lon"],
            city=city_info["city"]
        )
        
        if weather:
            weather["country"] = city_info["country"]
            weather_data.append(weather)
        
        time.sleep(1)  # Rate limiting (60 req/min pour free tier)
    
    if weather_data:
        df = pd.DataFrame(weather_data)
        
        # Sauvegarder en JSON brut
        _save_json(weather_data, f"weather_current_{datetime.now().strftime('%Y%m%d')}.json")
        
        # Sauvegarder en Parquet
        output_path = LANDING_DIR / f"weather_current_{datetime.now().strftime('%Y%m%d')}.parquet"
        df.to_parquet(output_path, index=False)
        print(f"✅ Météo sauvegardée: {output_path} ({len(df)} villes)")
        
        return df
    
    return pd.DataFrame()


def fetch_weather_for_teams() -> pd.DataFrame:
    """
    Récupère la météo pour les villes de toutes les équipes.
    
    Returns:
        DataFrame avec la météo par équipe/ville
    """
    print("🌤️ Récupération météo pour les équipes...")
    
    weather_data = []
    cities_done = set()  # Éviter les doublons de ville
    
    for team_name, team_info in TEAM_CITIES.items():
        city = team_info["city"]
        
        # Éviter de récupérer plusieurs fois la même ville
        if city in cities_done:
            continue
        
        print(f"  📍 {city} ({team_name})...")
        weather = fetch_current_weather(
            lat=team_info["lat"],
            lon=team_info["lon"],
            city=city
        )
        
        if weather:
            weather_data.append(weather)
            cities_done.add(city)
        
        time.sleep(1)  # Rate limiting
    
    if weather_data:
        df = pd.DataFrame(weather_data)
        
        # Sauvegarder
        _save_json(weather_data, f"weather_teams_{datetime.now().strftime('%Y%m%d')}.json")
        
        output_path = LANDING_DIR / f"weather_teams_{datetime.now().strftime('%Y%m%d')}.parquet"
        df.to_parquet(output_path, index=False)
        print(f"✅ Météo équipes sauvegardée: {output_path} ({len(df)} villes)")
        
        return df
    
    return pd.DataFrame()


def get_static_weather_data(use_static: bool = True) -> pd.DataFrame:
    """
    Retourne les données météo statiques (fallback si API indisponible).
    
    Args:
        use_static: Si True, utilise les données statiques
        
    Returns:
        DataFrame avec les données météo statiques
    """
    if not use_static:
        return pd.DataFrame()
    
    print("📦 Utilisation des données météo STATIQUES (fallback)...")
    
    weather_records = []
    fetch_time = datetime.now().isoformat()
    
    for city, data in STATIC_WEATHER_DATA.items():
        record = {
            "city": city,
            "lat": data["lat"],
            "lon": data["lon"],
            "country": data["country"],
            "temperature": data["temperature"],
            "feels_like": data["feels_like"],
            "humidity": data["humidity"],
            "pressure": data["pressure"],
            "weather_main": data["weather_main"],
            "weather_description": data["weather_description"],
            "wind_speed": data["wind_speed"],
            "wind_deg": data["wind_deg"],
            "clouds": data["clouds"],
            "visibility": data["visibility"],
            "rain_1h": data["rain_1h"],
            "snow_1h": data["snow_1h"],
            "fetched_at": fetch_time,
            "data_source": "static_fallback"
        }
        weather_records.append(record)
    
    df = pd.DataFrame(weather_records)
    
    # Sauvegarder
    output_path = LANDING_DIR / f"weather_current_{datetime.now().strftime('%Y%m%d')}.parquet"
    df.to_parquet(output_path, index=False)
    print(f"✅ Météo statique sauvegardée: {output_path} ({len(df)} villes)")
    
    # Sauvegarder aussi en JSON
    _save_json(weather_records, f"weather_current_{datetime.now().strftime('%Y%m%d')}.json")
    
    return df


def fetch_all_weather_data(use_static: bool = False):
    """
    Fonction principale: récupère toutes les données météo.
    
    Args:
        use_static: Si True, utilise directement les données statiques
                   Si False, tente l'API puis fallback sur statique si échec
    
    - Météo actuelle des villes principales
    - Météo des villes des équipes
    - Prévisions 5 jours (principales villes seulement)
    """
    print("=" * 50)
    print("🌦️ EXTRACTION OPENWEATHER API")
    print("=" * 50)
    
    # Option: utiliser directement les données statiques
    if use_static:
        df = get_static_weather_data(use_static=True)
        print("\n" + "=" * 50)
        print("✅ EXTRACTION MÉTÉO TERMINÉE (données statiques)")
        print("=" * 50)
        return df
    
    # 1. Météo actuelle
    df_current = fetch_all_cities_weather()
    
    # Si l'API a échoué (DataFrame vide), utiliser les données statiques
    if df_current.empty:
        print("\n⚠️ API indisponible - Basculement sur données statiques...")
        df_current = get_static_weather_data(use_static=True)
        print("\n" + "=" * 50)
        print("✅ EXTRACTION MÉTÉO TERMINÉE (fallback statique)")
        print("=" * 50)
        return df_current
    
    # 2. Météo équipes
    df_teams = fetch_weather_for_teams()
    
    # 3. Prévisions (seulement 3 villes pour éviter rate limit)
    print("\n📅 Récupération des prévisions 5 jours...")
    all_forecasts = []
    
    for city_info in MAIN_CITIES[:3]:  # Limité à 3 villes
        print(f"  📍 Prévisions {city_info['city']}...")
        forecasts = fetch_forecast_5days(
            lat=city_info["lat"],
            lon=city_info["lon"],
            city=city_info["city"]
        )
        if forecasts:
            all_forecasts.extend(forecasts)
        time.sleep(1)
    
    if all_forecasts:
        df_forecasts = pd.DataFrame(all_forecasts)
        output_path = LANDING_DIR / f"weather_forecast_{datetime.now().strftime('%Y%m%d')}.parquet"
        df_forecasts.to_parquet(output_path, index=False)
        print(f"✅ Prévisions sauvegardées: {output_path} ({len(df_forecasts)} entrées)")
    
    print("\n" + "=" * 50)
    print("✅ EXTRACTION MÉTÉO TERMINÉE")
    print("=" * 50)
    
    return df_current


if __name__ == "__main__":
    import sys
    # Usage: python fetch_weather.py [--static]
    use_static = "--static" in sys.argv
    fetch_all_weather_data(use_static=use_static)
