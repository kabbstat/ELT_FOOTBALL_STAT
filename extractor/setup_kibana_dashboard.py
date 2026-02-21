
import requests
import json

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}

def create_data_view():
    """Crée le Data View pour tous les indices football."""
    print(" Création du Data View...")
    
    # Data View pour les matchs
    data_view_matches = {
        "data_view": {
            "title": "football_matches",
            "name": "Football Matches",
            "timeFieldName": "match_date"
        }
    }
    
    response = requests.post(
        f"{KIBANA_URL}/api/data_views/data_view",
        headers=HEADERS,
        json=data_view_matches
    )
    
    if response.status_code in [200, 201]:
        matches_id = response.json().get("data_view", {}).get("id")
        print(f"  Data View 'Football Matches' créé: {matches_id}")
    else:
        print(f" Data View matches: {response.status_code}")
        matches_id = None
    
    # Data View pour les valeurs d'équipes
    data_view_values = {
        "data_view": {
            "title": "football_team_values",
            "name": "Team Values"
        }
    }
    
    response = requests.post(
        f"{KIBANA_URL}/api/data_views/data_view",
        headers=HEADERS,
        json=data_view_values
    )
    
    if response.status_code in [200, 201]:
        values_id = response.json().get("data_view", {}).get("id")
        print(f" Data View 'Team Values' créé: {values_id}")
    else:
        values_id = None
    
    # Data View pour la météo
    data_view_weather = {
        "data_view": {
            "title": "football_weather",
            "name": "Weather Data"
        }
    }
    
    response = requests.post(
        f"{KIBANA_URL}/api/data_views/data_view",
        headers=HEADERS,
        json=data_view_weather
    )
    
    if response.status_code in [200, 201]:
        weather_id = response.json().get("data_view", {}).get("id")
        print(f"Data View 'Weather Data' créé: {weather_id}")
    else:
        weather_id = None
    
    # Data View combiné
    data_view_all = {
        "data_view": {
            "title": "football_*",
            "name": "All Football Data",
            "timeFieldName": "match_date"
        }
    }
    
    response = requests.post(
        f"{KIBANA_URL}/api/data_views/data_view",
        headers=HEADERS,
        json=data_view_all
    )
    
    if response.status_code in [200, 201]:
        all_id = response.json().get("data_view", {}).get("id")
        print(f" Data View 'All Football Data' créé: {all_id}")
    else:
        all_id = None
    
    return matches_id, values_id, weather_id, all_id


def import_dashboard():
    """Importe un dashboard complet avec visualisations."""
    print("\nImport du dashboard...")
    
    # Dashboard complet avec visualisations intégrées
    dashboard_ndjson = """{"attributes":{"title":"Football Analytics Dashboard","hits":0,"description":"Dashboard complet pour l'analyse des données football, météo et valeurs marchandes","panelsJSON":"[{\\"version\\":\\"8.11.0\\",\\"type\\":\\"lens\\",\\"gridData\\":{\\"x\\":0,\\"y\\":0,\\"w\\":24,\\"h\\":8,\\"i\\":\\"1\\"},\\"panelIndex\\":\\"1\\",\\"embeddableConfig\\":{\\"attributes\\":{\\"title\\":\\"Matchs par compétition\\",\\"visualizationType\\":\\"lnsPie\\",\\"state\\":{\\"datasourceStates\\":{\\"formBased\\":{\\"layers\\":{\\"layer1\\":{\\"columns\\":{\\"col1\\":{\\"label\\":\\"Competition\\",\\"dataType\\":\\"string\\",\\"operationType\\":\\"terms\\",\\"sourceField\\":\\"competition.keyword\\",\\"params\\":{\\"size\\":10}},\\"col2\\":{\\"label\\":\\"Count\\",\\"dataType\\":\\"number\\",\\"operationType\\":\\"count\\"}},\\"columnOrder\\":[\\"col1\\",\\"col2\\"]}}}},\\"visualization\\":{\\"shape\\":\\"pie\\",\\"layers\\":[{\\"layerId\\":\\"layer1\\",\\"primaryGroups\\":[\\"col1\\"],\\"metrics\\":[\\"col2\\"]}]}},\\"references\\":[{\\"type\\":\\"index-pattern\\",\\"id\\":\\"football_matches\\",\\"name\\":\\"indexpattern-datasource-layer-layer1\\"}]}}},{\\"version\\":\\"8.11.0\\",\\"type\\":\\"lens\\",\\"gridData\\":{\\"x\\":24,\\"y\\":0,\\"w\\":24,\\"h\\":8,\\"i\\":\\"2\\"},\\"panelIndex\\":\\"2\\",\\"embeddableConfig\\":{\\"attributes\\":{\\"title\\":\\"Résultats des matchs\\",\\"visualizationType\\":\\"lnsPie\\",\\"state\\":{\\"datasourceStates\\":{\\"formBased\\":{\\"layers\\":{\\"layer1\\":{\\"columns\\":{\\"col1\\":{\\"label\\":\\"Result\\",\\"dataType\\":\\"string\\",\\"operationType\\":\\"terms\\",\\"sourceField\\":\\"result.keyword\\",\\"params\\":{\\"size\\":5}},\\"col2\\":{\\"label\\":\\"Count\\",\\"dataType\\":\\"number\\",\\"operationType\\":\\"count\\"}},\\"columnOrder\\":[\\"col1\\",\\"col2\\"]}}}},\\"visualization\\":{\\"shape\\":\\"donut\\",\\"layers\\":[{\\"layerId\\":\\"layer1\\",\\"primaryGroups\\":[\\"col1\\"],\\"metrics\\":[\\"col2\\"]}]}},\\"references\\":[{\\"type\\":\\"index-pattern\\",\\"id\\":\\"football_matches\\",\\"name\\":\\"indexpattern-datasource-layer-layer1\\"}]}}}]","optionsJSON":"{\\"useMargins\\":true,\\"syncColors\\":false,\\"hidePanelTitles\\":false}","version":1,"timeRestore":false,"kibanaSavedObjectMeta":{"searchSourceJSON":"{\\"query\\":{\\"query\\":\\"\\",\\"language\\":\\"kuery\\"},\\"filter\\":[]}"}},"id":"football-dashboard-main","type":"dashboard","references":[],"managed":false}"""
    
    response = requests.post(
        f"{KIBANA_URL}/api/saved_objects/_import?overwrite=true",
        headers={"kbn-xsrf": "true"},
        files={"file": ("dashboard.ndjson", dashboard_ndjson, "application/ndjson")}
    )
    
    if response.status_code == 200:
        print(" Dashboard importé")
        return True
    else:
        print(f" Import dashboard: {response.status_code} - {response.text}")
        return False


def create_simple_visualizations():
    """Crée des visualisations simples via l'API."""
    print("\n Création des visualisations...")
    
    # Vérifier les données dans Elasticsearch
    es_response = requests.get("http://localhost:9200/football_matches/_count")
    if es_response.status_code == 200:
        count = es_response.json().get("count", 0)
        print(f" {count} matchs disponibles dans Elasticsearch")
    
    es_response = requests.get("http://localhost:9200/football_team_values/_count")
    if es_response.status_code == 200:
        count = es_response.json().get("count", 0)
        print(f"  {count} équipes disponibles dans Elasticsearch")
    
    es_response = requests.get("http://localhost:9200/football_weather/_count")
    if es_response.status_code == 200:
        count = es_response.json().get("count", 0)
        print(f"  {count} villes météo disponibles dans Elasticsearch")
    
    return True


def print_instructions():
    """Affiche les instructions pour utiliser Kibana."""
    print("\n" + "=" * 60)
    print(" CONFIGURATION KIBANA TERMINÉE")
    print("=" * 60)
    print("""
 Accès: http://localhost:5601

 Pour créer des visualisations:
   1. Menu ☰ → Analytics → Discover
   2. Sélectionne "Football Matches" ou "All Football Data"
   3. Tu verras toutes les données

 Pour créer un graphique:
   1. Menu ☰ → Analytics → Visualize Library
   2. Clique "Create visualization"
   3. Sélectionne "Lens" (le plus simple)
   4. Glisse-dépose les champs pour créer ton graphique

 Champs intéressants pour les graphiques:
   - competition.keyword → Pie chart des compétitions
   - home_team.keyword → Top équipes à domicile
   - away_team.keyword → Top équipes à l'extérieur
   - home_score, away_score → Moyennes de buts
   - match_date → Évolution dans le temps
   - market_value → Valeurs marchandes
   - temperature → Température par ville

 Pour voir directement les données:
   1. Menu ☰ → Analytics → Discover
   2. Change la période en haut à droite → "Last 5 years"
   3. Les données de 2023-2024 apparaîtront
""")


def main():
    print("=" * 60)
    print(" CONFIGURATION AUTOMATIQUE KIBANA")
    print("=" * 60)
    
    # 1. Créer les Data Views
    create_data_view()
    
    # 2. Vérifier les données
    create_simple_visualizations()
    
    # 3. Instructions
    print_instructions()


if __name__ == "__main__":
    main()
