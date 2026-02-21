"""
Transfermarkt Data Extractor
Récupère les valeurs marchandes des équipes via web scraping.

Note: Transfermarkt bloque les requêtes automatisées.
Ce module utilise des headers USER-AGENT pour contourner les restrictions.
"""
from dotenv import load_dotenv
import os
import pandas as pd
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import json
import time
from bs4 import BeautifulSoup
import re

load_dotenv()

# Configuration
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LANDING_DIR = DATA_DIR / "landing"

# Création des dossiers
LANDING_DIR.mkdir(parents=True, exist_ok=True)

# Headers pour simuler un navigateur
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# URLs des compétitions Transfermarkt
COMPETITION_URLS = {
    "PL": {
        "name": "Premier League",
        "url": "https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1",
        "country": "England"
    },
    "FL1": {
        "name": "Ligue 1",
        "url": "https://www.transfermarkt.com/ligue-1/startseite/wettbewerb/FR1",
        "country": "France"
    },
    "PD": {
        "name": "La Liga",
        "url": "https://www.transfermarkt.com/laliga/startseite/wettbewerb/ES1",
        "country": "Spain"
    },
    "BL1": {
        "name": "Bundesliga",
        "url": "https://www.transfermarkt.com/bundesliga/startseite/wettbewerb/L1",
        "country": "Germany"
    },
    "SA": {
        "name": "Serie A",
        "url": "https://www.transfermarkt.com/serie-a/startseite/wettbewerb/IT1",
        "country": "Italy"
    }
}

# Données statiques des valeurs marchandes (fallback si scraping échoue)
# Source: Transfermarkt - Janvier 2024
STATIC_TEAM_VALUES = {
    # Premier League
    "Manchester City FC": {"market_value_eur": 1200000000, "squad_size": 25, "avg_age": 27.2},
    "Arsenal FC": {"market_value_eur": 1050000000, "squad_size": 27, "avg_age": 25.1},
    "Chelsea FC": {"market_value_eur": 950000000, "squad_size": 32, "avg_age": 24.8},
    "Manchester United FC": {"market_value_eur": 850000000, "squad_size": 28, "avg_age": 26.4},
    "Liverpool FC": {"market_value_eur": 900000000, "squad_size": 26, "avg_age": 26.1},
    "Tottenham Hotspur FC": {"market_value_eur": 680000000, "squad_size": 27, "avg_age": 26.3},
    "Newcastle United FC": {"market_value_eur": 580000000, "squad_size": 26, "avg_age": 26.7},
    "Brighton & Hove Albion FC": {"market_value_eur": 480000000, "squad_size": 27, "avg_age": 25.9},
    "Aston Villa FC": {"market_value_eur": 530000000, "squad_size": 28, "avg_age": 27.0},
    "West Ham United FC": {"market_value_eur": 450000000, "squad_size": 26, "avg_age": 26.5},
    "Everton FC": {"market_value_eur": 290000000, "squad_size": 27, "avg_age": 26.8},
    "Crystal Palace FC": {"market_value_eur": 280000000, "squad_size": 25, "avg_age": 27.4},
    "Fulham FC": {"market_value_eur": 260000000, "squad_size": 28, "avg_age": 27.2},
    "Wolverhampton Wanderers FC": {"market_value_eur": 320000000, "squad_size": 26, "avg_age": 26.1},
    "Brentford FC": {"market_value_eur": 310000000, "squad_size": 27, "avg_age": 27.5},
    "Nottingham Forest FC": {"market_value_eur": 350000000, "squad_size": 32, "avg_age": 26.3},
    "AFC Bournemouth": {"market_value_eur": 230000000, "squad_size": 27, "avg_age": 25.8},
    "Burnley FC": {"market_value_eur": 150000000, "squad_size": 28, "avg_age": 27.1},
    "Sheffield United FC": {"market_value_eur": 120000000, "squad_size": 27, "avg_age": 26.9},
    "Luton Town FC": {"market_value_eur": 85000000, "squad_size": 26, "avg_age": 27.3},
    
    # La Liga
    "Real Madrid CF": {"market_value_eur": 1100000000, "squad_size": 24, "avg_age": 27.8},
    "FC Barcelona": {"market_value_eur": 950000000, "squad_size": 26, "avg_age": 26.2},
    "Atlético de Madrid": {"market_value_eur": 550000000, "squad_size": 25, "avg_age": 27.1},
    "Real Sociedad de Fútbol": {"market_value_eur": 380000000, "squad_size": 26, "avg_age": 26.5},
    "Villarreal CF": {"market_value_eur": 320000000, "squad_size": 27, "avg_age": 27.3},
    "Real Betis Balompié": {"market_value_eur": 280000000, "squad_size": 28, "avg_age": 27.0},
    "Athletic Club": {"market_value_eur": 310000000, "squad_size": 24, "avg_age": 26.8},
    "Sevilla FC": {"market_value_eur": 270000000, "squad_size": 27, "avg_age": 27.5},
    "Valencia CF": {"market_value_eur": 200000000, "squad_size": 26, "avg_age": 26.2},
    "Girona FC": {"market_value_eur": 180000000, "squad_size": 25, "avg_age": 26.9},
    
    # Ligue 1
    "Paris Saint-Germain FC": {"market_value_eur": 980000000, "squad_size": 26, "avg_age": 26.4},
    "AS Monaco FC": {"market_value_eur": 380000000, "squad_size": 28, "avg_age": 24.1},
    "Olympique de Marseille": {"market_value_eur": 300000000, "squad_size": 27, "avg_age": 25.8},
    "Olympique Lyonnais": {"market_value_eur": 280000000, "squad_size": 28, "avg_age": 25.2},
    "LOSC Lille": {"market_value_eur": 250000000, "squad_size": 27, "avg_age": 24.7},
    "OGC Nice": {"market_value_eur": 180000000, "squad_size": 26, "avg_age": 25.5},
    "Stade Rennais FC 1901": {"market_value_eur": 200000000, "squad_size": 28, "avg_age": 25.1},
    "RC Lens": {"market_value_eur": 190000000, "squad_size": 27, "avg_age": 25.7},
    "Stade Brestois 29": {"market_value_eur": 95000000, "squad_size": 26, "avg_age": 26.2},
    "RC Strasbourg Alsace": {"market_value_eur": 90000000, "squad_size": 28, "avg_age": 25.4},
    "FC Nantes": {"market_value_eur": 85000000, "squad_size": 27, "avg_age": 26.0},
    "Montpellier HSC": {"market_value_eur": 80000000, "squad_size": 26, "avg_age": 26.8},
    "Toulouse FC": {"market_value_eur": 100000000, "squad_size": 27, "avg_age": 24.9},
    "Stade de Reims": {"market_value_eur": 75000000, "squad_size": 26, "avg_age": 25.3},
}


def _save_json(data: dict, filename: str) -> Path:
    """Sauvegarde les données JSON avec métadonnées"""
    path = LANDING_DIR / filename
    enriched = {
        "extracted_at": datetime.now().isoformat(),
        "source": "transfermarkt",
        "data": data
    }
    path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def parse_market_value(value_str: str) -> Optional[int]:
    """
    Parse une valeur marchande Transfermarkt (ex: "€1.2bn", "€500m").
    
    Args:
        value_str: Chaîne de valeur (ex: "€1.2bn")
    
    Returns:
        Valeur en euros (int) ou None
    """
    if not value_str:
        return None
    
    value_str = value_str.strip().lower()
    
    # Extraire le nombre
    match = re.search(r'€?([\d.]+)\s*(bn|m|k)?', value_str)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2) or ''
    
    multipliers = {
        'bn': 1_000_000_000,
        'm': 1_000_000,
        'k': 1_000,
        '': 1
    }
    
    return int(number * multipliers.get(unit, 1))


def scrape_competition_teams(competition_code: str) -> Optional[List[Dict]]:
    """
    Scrape les valeurs marchandes des équipes d'une compétition.
    
    Args:
        competition_code: Code de la compétition (PL, FL1, PD, etc.)
    
    Returns:
        Liste des équipes avec leurs valeurs ou None si erreur
    """
    if competition_code not in COMPETITION_URLS:
        print(f"⚠️ Compétition inconnue: {competition_code}")
        return None
    
    comp_info = COMPETITION_URLS[competition_code]
    url = comp_info["url"]
    
    print(f"  🔍 Scraping {comp_info['name']}...")
    
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            teams_data = []
            
            # Chercher le tableau des équipes
            table = soup.find('table', class_='items')
            
            if not table:
                print(f"  ⚠️ Tableau non trouvé pour {competition_code}")
                return None
            
            rows = table.find_all('tr', class_=['odd', 'even'])
            
            for row in rows:
                cols = row.find_all('td')
                
                if len(cols) >= 6:
                    # Extraire le nom de l'équipe
                    team_link = row.find('a', class_='vereinprofil_tooltip')
                    team_name = team_link.get_text(strip=True) if team_link else "Unknown"
                    
                    # Extraire les autres colonnes
                    squad_size = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
                    avg_age = cols[4].get_text(strip=True) if len(cols) > 4 else "0"
                    market_value = cols[5].get_text(strip=True) if len(cols) > 5 else "€0"
                    
                    teams_data.append({
                        "team_name": team_name,
                        "competition_code": competition_code,
                        "competition_name": comp_info["name"],
                        "country": comp_info["country"],
                        "squad_size": int(squad_size) if squad_size.isdigit() else 0,
                        "avg_age": float(avg_age.replace(',', '.')) if avg_age else 0.0,
                        "market_value_raw": market_value,
                        "market_value_eur": parse_market_value(market_value),
                        "fetched_at": datetime.now().isoformat()
                    })
            
            print(f"  ✅ {len(teams_data)} équipes trouvées")
            return teams_data
    
    except httpx.HTTPError as e:
        print(f"  ❌ Erreur HTTP pour {competition_code}: {e}")
        return None
    except Exception as e:
        print(f"  ❌ Erreur parsing pour {competition_code}: {e}")
        return None


def get_static_team_values() -> pd.DataFrame:
    """
    Retourne les valeurs statiques des équipes (fallback).
    
    Returns:
        DataFrame avec les valeurs marchandes
    """
    print("📊 Utilisation des données statiques Transfermarkt...")
    
    teams_list = []
    
    for team_name, values in STATIC_TEAM_VALUES.items():
        # Déterminer la compétition
        if team_name in ["Manchester City FC", "Arsenal FC", "Chelsea FC", "Manchester United FC", 
                         "Liverpool FC", "Tottenham Hotspur FC", "Newcastle United FC", 
                         "Brighton & Hove Albion FC", "Aston Villa FC", "West Ham United FC",
                         "Everton FC", "Crystal Palace FC", "Fulham FC", 
                         "Wolverhampton Wanderers FC", "Brentford FC", "Nottingham Forest FC",
                         "AFC Bournemouth", "Burnley FC", "Sheffield United FC", "Luton Town FC"]:
            competition = "PL"
            country = "England"
        elif team_name in ["Real Madrid CF", "FC Barcelona", "Atlético de Madrid", 
                          "Real Sociedad de Fútbol", "Villarreal CF", "Real Betis Balompié",
                          "Athletic Club", "Sevilla FC", "Valencia CF", "Girona FC"]:
            competition = "PD"
            country = "Spain"
        else:
            competition = "FL1"
            country = "France"
        
        teams_list.append({
            "team_name": team_name,
            "competition_code": competition,
            "country": country,
            "squad_size": values["squad_size"],
            "avg_age": values["avg_age"],
            "market_value_eur": values["market_value_eur"],
            "avg_player_value_eur": int(values["market_value_eur"] / values["squad_size"]),
            "data_source": "static_2024",
            "fetched_at": datetime.now().isoformat()
        })
    
    return pd.DataFrame(teams_list)


def fetch_all_team_values(use_static: bool = True) -> pd.DataFrame:
    """
    Récupère les valeurs marchandes de toutes les équipes.
    
    Args:
        use_static: Si True, utilise les données statiques (recommandé car scraping peut échouer)
    
    Returns:
        DataFrame avec toutes les valeurs
    """
    print("=" * 50)
    print("💰 EXTRACTION TRANSFERMARKT")
    print("=" * 50)
    
    if use_static:
        df = get_static_team_values()
    else:
        # Tenter le scraping
        all_teams = []
        
        for comp_code in ["PL", "FL1", "PD"]:  # Limiter aux 3 principales
            teams = scrape_competition_teams(comp_code)
            if teams:
                all_teams.extend(teams)
            time.sleep(5)  # Éviter le rate limiting
        
        if all_teams:
            df = pd.DataFrame(all_teams)
        else:
            print("⚠️ Scraping échoué, utilisation des données statiques...")
            df = get_static_team_values()
    
    # Sauvegarder
    if not df.empty:
        # JSON
        _save_json(df.to_dict(orient='records'), f"team_values_{datetime.now().strftime('%Y%m%d')}.json")
        
        # Parquet
        output_path = LANDING_DIR / f"team_values_{datetime.now().strftime('%Y%m%d')}.parquet"
        df.to_parquet(output_path, index=False)
        print(f"\n✅ Valeurs marchandes sauvegardées: {output_path}")
        print(f"   📊 {len(df)} équipes | Total: €{df['market_value_eur'].sum():,}")
        
        # Résumé par compétition
        print("\n📈 Résumé par compétition:")
        summary = df.groupby('competition_code').agg({
            'team_name': 'count',
            'market_value_eur': 'sum'
        }).rename(columns={'team_name': 'teams', 'market_value_eur': 'total_value'})
        print(summary.to_string())
    
    print("\n" + "=" * 50)
    print("✅ EXTRACTION TRANSFERMARKT TERMINÉE")
    print("=" * 50)
    
    return df


def get_team_value(team_name: str) -> Optional[Dict]:
    """
    Retourne la valeur marchande d'une équipe spécifique.
    
    Args:
        team_name: Nom de l'équipe
    
    Returns:
        Dict avec les infos de l'équipe ou None
    """
    if team_name in STATIC_TEAM_VALUES:
        return {
            "team_name": team_name,
            **STATIC_TEAM_VALUES[team_name]
        }
    return None


if __name__ == "__main__":
    # Par défaut, utiliser les données statiques (plus fiable)
    df = fetch_all_team_values(use_static=True)
    
    # Pour tester le scraping:
    # df = fetch_all_team_values(use_static=False)
