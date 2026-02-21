"""
Script de requêtes Elasticsearch pour l'analyse des données football.
Exécute des requêtes analytiques et génère un rapport.
"""
import requests
import json
from datetime import datetime

ES_URL = "http://localhost:9200"
INDEX = "football_combined"


def query_es(query: dict) -> dict:
    """Exécute une requête Elasticsearch."""
    response = requests.post(
        f"{ES_URL}/{INDEX}/_search",
        headers={"Content-Type": "application/json"},
        json=query
    )
    return response.json()


def print_section(title: str):
    """Affiche un titre de section."""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print('='*60)


def analyze_competitions():
    """Analyse par compétition."""
    print_section("ANALYSE PAR COMPÉTITION")
    
    query = {
        "size": 0,
        "aggs": {
            "by_competition": {
                "terms": {"field": "competition_code"},
                "aggs": {
                    "total_matches": {"value_count": {"field": "match_id"}},
                    "avg_goals": {"avg": {"field": "total_goals"}},
                    "avg_home_goals": {"avg": {"field": "home_score"}},
                    "avg_away_goals": {"avg": {"field": "away_score"}},
                    "avg_market_value": {"avg": {"field": "combined_market_value"}},
                    "home_wins": {
                        "filter": {"term": {"actual_winner": "HOME"}}
                    },
                    "away_wins": {
                        "filter": {"term": {"actual_winner": "AWAY"}}
                    },
                    "draws": {
                        "filter": {"term": {"actual_winner": "DRAW"}}
                    }
                }
            }
        }
    }
    
    result = query_es(query)
    
    print(f"\n{'Compétition':<12} {'Matchs':>8} {'Buts/Match':>12} {'Dom':>6} {'Ext':>6} {'Nul':>6} {'Valeur Moy':>15}")
    print("-" * 70)
    
    for bucket in result["aggregations"]["by_competition"]["buckets"]:
        code = bucket["key"]
        matches = bucket["doc_count"]
        avg_goals = bucket["avg_goals"]["value"] or 0
        home_wins = bucket["home_wins"]["doc_count"]
        away_wins = bucket["away_wins"]["doc_count"]
        draws = bucket["draws"]["doc_count"]
        avg_value = bucket["avg_market_value"]["value"] or 0
        
        print(f"{code:<12} {matches:>8} {avg_goals:>12.2f} {home_wins:>6} {away_wins:>6} {draws:>6} {avg_value/1e6:>12.0f}M €")


def analyze_upsets():
    """Analyse des upsets (surprises)."""
    print_section("ANALYSE DES UPSETS (Équipe moins chère gagne)")
    
    # Taux d'upset par compétition
    query = {
        "size": 0,
        "aggs": {
            "by_competition": {
                "terms": {"field": "competition_code"},
                "aggs": {
                    "total": {"value_count": {"field": "match_id"}},
                    "upsets": {
                        "filter": {"term": {"is_upset": True}},
                        "aggs": {
                            "avg_value_diff": {"avg": {"field": "market_value_diff"}}
                        }
                    }
                }
            }
        }
    }
    
    result = query_es(query)
    
    print(f"\n{'Compétition':<12} {'Total Matchs':>12} {'Upsets':>10} {'Taux':>10}")
    print("-" * 50)
    
    for bucket in result["aggregations"]["by_competition"]["buckets"]:
        code = bucket["key"]
        total = bucket["total"]["value"]
        upsets = bucket["upsets"]["doc_count"]
        rate = (upsets / total * 100) if total > 0 else 0
        
        print(f"{code:<12} {total:>12} {upsets:>10} {rate:>9.1f}%")
    
    # Top 10 plus gros upsets
    print("\n📈 TOP 10 PLUS GROS UPSETS (différence de valeur):")
    
    query = {
        "size": 10,
        "query": {"term": {"is_upset": True}},
        "sort": [{"upset_value": {"order": "desc"}}],
        "_source": ["home_team", "away_team", "home_score", "away_score", 
                    "home_market_value", "away_market_value", "competition_code", "match_date"]
    }
    
    result = query_es(query)
    
    print(f"\n{'Match':<50} {'Score':>8} {'Diff Valeur':>15}")
    print("-" * 75)
    
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        match = f"{src['home_team'][:20]} vs {src['away_team'][:20]}"
        score = f"{src['home_score']}-{src['away_score']}"
        diff = abs(src.get('home_market_value', 0) - src.get('away_market_value', 0))
        print(f"{match:<50} {score:>8} {diff/1e6:>12.0f}M €")


def analyze_weather_impact():
    """Analyse de l'impact météo."""
    print_section("IMPACT DE LA MÉTÉO SUR LES MATCHS")
    
    query = {
        "size": 0,
        "query": {"exists": {"field": "temperature"}},
        "aggs": {
            "by_weather": {
                "terms": {"field": "weather_condition"},
                "aggs": {
                    "avg_goals": {"avg": {"field": "total_goals"}},
                    "home_wins": {"filter": {"term": {"actual_winner": "HOME"}}},
                    "away_wins": {"filter": {"term": {"actual_winner": "AWAY"}}},
                    "draws": {"filter": {"term": {"actual_winner": "DRAW"}}},
                    "avg_temp": {"avg": {"field": "temperature"}}
                }
            },
            "temp_ranges": {
                "range": {
                    "field": "temperature",
                    "ranges": [
                        {"key": "Froid (<10°C)", "to": 10},
                        {"key": "Tempéré (10-20°C)", "from": 10, "to": 20},
                        {"key": "Chaud (>20°C)", "from": 20}
                    ]
                },
                "aggs": {
                    "avg_goals": {"avg": {"field": "total_goals"}}
                }
            }
        }
    }
    
    result = query_es(query)
    
    print(f"\n{'Condition':<15} {'Matchs':>8} {'Buts/Match':>12} {'Temp Moy':>10} {'Dom%':>8} {'Ext%':>8}")
    print("-" * 65)
    
    for bucket in result["aggregations"]["by_weather"]["buckets"]:
        condition = bucket["key"]
        matches = bucket["doc_count"]
        avg_goals = bucket["avg_goals"]["value"] or 0
        avg_temp = bucket["avg_temp"]["value"] or 0
        home_pct = (bucket["home_wins"]["doc_count"] / matches * 100) if matches > 0 else 0
        away_pct = (bucket["away_wins"]["doc_count"] / matches * 100) if matches > 0 else 0
        
        print(f"{condition:<15} {matches:>8} {avg_goals:>12.2f} {avg_temp:>8.1f}°C {home_pct:>7.1f}% {away_pct:>7.1f}%")
    
    print("\n📊 Par plage de température:")
    print(f"{'Température':<20} {'Matchs':>8} {'Buts/Match':>12}")
    print("-" * 45)
    
    for bucket in result["aggregations"]["temp_ranges"]["buckets"]:
        temp_range = bucket["key"]
        matches = bucket["doc_count"]
        avg_goals = bucket["avg_goals"]["value"] or 0
        print(f"{temp_range:<20} {matches:>8} {avg_goals:>12.2f}")


def analyze_teams():
    """Analyse des équipes."""
    print_section("ANALYSE DES ÉQUIPES")
    
    # Top équipes à domicile
    print("\n🏠 TOP 10 ÉQUIPES À DOMICILE (victoires):")
    
    query = {
        "size": 0,
        "aggs": {
            "by_home_team": {
                "terms": {"field": "home_team.keyword", "size": 10},
                "aggs": {
                    "wins": {"filter": {"term": {"actual_winner": "HOME"}}},
                    "avg_goals_scored": {"avg": {"field": "home_score"}},
                    "avg_market_value": {"avg": {"field": "home_market_value"}}
                }
            }
        }
    }
    
    result = query_es(query)
    
    teams = []
    for bucket in result["aggregations"]["by_home_team"]["buckets"]:
        teams.append({
            "name": bucket["key"],
            "matches": bucket["doc_count"],
            "wins": bucket["wins"]["doc_count"],
            "win_rate": bucket["wins"]["doc_count"] / bucket["doc_count"] * 100,
            "avg_goals": bucket["avg_goals_scored"]["value"] or 0,
            "value": bucket["avg_market_value"]["value"] or 0
        })
    
    teams.sort(key=lambda x: x["win_rate"], reverse=True)
    
    print(f"\n{'Équipe':<30} {'Matchs':>8} {'Victoires':>10} {'Taux':>8} {'Buts/M':>8}")
    print("-" * 70)
    
    for team in teams[:10]:
        print(f"{team['name'][:28]:<30} {team['matches']:>8} {team['wins']:>10} {team['win_rate']:>7.1f}% {team['avg_goals']:>8.2f}")


def analyze_goals_distribution():
    """Distribution des buts."""
    print_section("DISTRIBUTION DES BUTS")
    
    query = {
        "size": 0,
        "aggs": {
            "goals_histogram": {
                "histogram": {
                    "field": "total_goals",
                    "interval": 1
                }
            },
            "stats": {
                "stats": {"field": "total_goals"}
            }
        }
    }
    
    result = query_es(query)
    
    stats = result["aggregations"]["stats"]
    print(f"\n📈 Statistiques générales:")
    print(f"   - Minimum: {stats['min']:.0f} buts")
    print(f"   - Maximum: {stats['max']:.0f} buts")
    print(f"   - Moyenne: {stats['avg']:.2f} buts")
    print(f"   - Total matchs: {stats['count']:.0f}")
    
    print(f"\n{'Buts':<8} {'Matchs':>10} {'Pourcentage':>12}")
    print("-" * 35)
    
    total = stats['count']
    for bucket in result["aggregations"]["goals_histogram"]["buckets"]:
        goals = int(bucket["key"])
        count = bucket["doc_count"]
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"{goals:<8} {count:>10} {pct:>10.1f}% {bar}")


def analyze_value_performance():
    """Corrélation valeur marchande et performance."""
    print_section("VALEUR MARCHANDE VS PERFORMANCE")
    
    query = {
        "size": 0,
        "query": {"range": {"combined_market_value": {"gt": 0}}},
        "aggs": {
            "value_ranges": {
                "range": {
                    "field": "combined_market_value",
                    "ranges": [
                        {"key": "< 500M €", "to": 500000000},
                        {"key": "500M - 1B €", "from": 500000000, "to": 1000000000},
                        {"key": "1B - 1.5B €", "from": 1000000000, "to": 1500000000},
                        {"key": "> 1.5B €", "from": 1500000000}
                    ]
                },
                "aggs": {
                    "avg_goals": {"avg": {"field": "total_goals"}},
                    "upsets": {"filter": {"term": {"is_upset": True}}}
                }
            }
        }
    }
    
    result = query_es(query)
    
    print(f"\n{'Valeur combinée':<20} {'Matchs':>10} {'Buts/Match':>12} {'Upsets':>10}")
    print("-" * 55)
    
    for bucket in result["aggregations"]["value_ranges"]["buckets"]:
        value_range = bucket["key"]
        matches = bucket["doc_count"]
        avg_goals = bucket["avg_goals"]["value"] or 0
        upsets = bucket["upsets"]["doc_count"]
        
        print(f"{value_range:<20} {matches:>10} {avg_goals:>12.2f} {upsets:>10}")


def generate_report():
    """Génère le rapport complet."""
    print("\n" + "=" * 60)
    print("⚽ RAPPORT D'ANALYSE FOOTBALL - DONNÉES CROISÉES")
    print("=" * 60)
    print(f"📅 Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Sources: Football API + Transfermarkt + OpenWeather")
    
    # Vérifier la connexion
    try:
        response = requests.get(f"{ES_URL}/{INDEX}/_count")
        count = response.json().get("count", 0)
        print(f"📈 Total documents: {count}")
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return
    
    # Exécuter toutes les analyses
    analyze_competitions()
    analyze_upsets()
    analyze_weather_impact()
    analyze_teams()
    analyze_goals_distribution()
    analyze_value_performance()
    
    print("\n" + "=" * 60)
    print("✅ RAPPORT TERMINÉ")
    print("=" * 60)


if __name__ == "__main__":
    generate_report()
