import requests
import json
import uuid

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}

def get_data_view_id(title_pattern):
    response = requests.get(f"{KIBANA_URL}/api/data_views", headers=HEADERS)
    if response.status_code == 200:
        for dv in response.json().get("data_view", []):
            if dv.get("title") == title_pattern:
                return dv.get("id")
    override_id = title_pattern.replace("*", "all").replace("_", "-")
    data_view = {"data_view": {"title": title_pattern, "name": f"Created for Dashboard ({title_pattern})", "id": override_id}}
    res = requests.post(f"{KIBANA_URL}/api/data_views/data_view", headers=HEADERS, json=data_view)
    if res.status_code in [200, 201]:
        return res.json().get("data_view", {}).get("id")
    return None

def create_saved_object(obj_type, obj_id, attributes, references):
    payload = {
        "attributes": attributes,
        "references": references
    }
    res = requests.post(f"{KIBANA_URL}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true", headers=HEADERS, json=payload)
    if res.status_code == 200:
        print(f"✅ {obj_type} '{attributes.get('title')}' créé !")
        return True
    else:
        print(f"❌ Erreur création {obj_type} '{attributes.get('title')}': {res.text}")
        return False

def main():
    dv_id = get_data_view_id("football_*")
    if not dv_id:
        print("Data view introuvable.")
        return

    # ----- WEATHER DASHBOARD -----
    vis_weather_pie_id = "vis-weather-pie-v2"
    vis_weather_pie_attrs = {
        "title": "Matches par Météo",
        "visState": json.dumps({
            "title": "Matches par Météo",
            "type": "pie",
            "params": {"type":"pie","addTooltip":True,"addLegend":True,"legendPosition":"right","isDonut":True},
            "aggs": [
                {"id":"1","enabled":True,"type":"count","schema":"metric","params":{}},
                {"id":"2","enabled":True,"type":"terms","schema":"segment","params":{"field":"weather_condition","size":10,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "Répartition des matchs par condition météorologique",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_weather_pie_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_weather_pie_id, vis_weather_pie_attrs, vis_weather_pie_refs)

    # Use a Data Table instead of Histogram to avoid the undefined error in Kibana 8
    vis_weather_goals_id = "vis-weather-goals-v2"
    vis_weather_goals_attrs = {
        "title": "Moyenne de Buts par Météo",
        "visState": json.dumps({
            "title": "Moyenne de Buts par Météo",
            "type": "table",
            "params": {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False, "sort": {"columnIndex": None, "direction": None}, "showTotal": False, "totalFunc": "sum"},
            "aggs": [
                {"id":"1","enabled":True,"type":"avg","schema":"metric","params":{"field":"total_goals"}},
                {"id":"2","enabled":True,"type":"terms","schema":"bucket","params":{"field":"weather_condition","size":10,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "Table: Moyenne Buts",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_weather_goals_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_weather_goals_id, vis_weather_goals_attrs, vis_weather_goals_refs)

    dash_weather_id = "dash-weather-impact-v2"
    dash_weather_attrs = {
        "title": "Weather Impact Analysis V2",
        "hits": 0,
        "description": "Analyse de la météo sur les matchs",
        "panelsJSON": json.dumps([
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": "1"}, "panelIndex": "1", "panelRefName": "panel_0"},
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 24, "y": 0, "w": 24, "h": 15, "i": "2"}, "panelIndex": "2", "panelRefName": "panel_1"}
        ]),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        }
    }
    dash_weather_refs = [
        {"name": "panel_0", "type": "visualization", "id": vis_weather_pie_id},
        {"name": "panel_1", "type": "visualization", "id": vis_weather_goals_id}
    ]
    create_saved_object("dashboard", dash_weather_id, dash_weather_attrs, dash_weather_refs)


    # ----- MARKET VALUE DASHBOARD -----
    vis_market_upset_id = "vis-market-upset-v2"
    vis_market_upset_attrs = {
        "title": "Upsets vs Favoris",
        "visState": json.dumps({
            "title": "Upsets vs Favoris",
            "type": "pie",
            "params": {"type":"pie","addTooltip":True,"addLegend":True,"legendPosition":"right","isDonut":False},
            "aggs": [
                {"id":"1","enabled":True,"type":"count","schema":"metric","params":{}},
                {"id":"2","enabled":True,"type":"terms","schema":"segment","params":{"field":"is_upset","size":10,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "Part des matchs remportés par l'équipe la moins chère (Upset)",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_market_upset_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_market_upset_id, vis_market_upset_attrs, vis_market_upset_refs)

    dash_market_id = "dash-market-value-v2"
    dash_market_attrs = {
        "title": "Transfer Market Analysis V2",
        "hits": 0,
        "description": "Analyse de la valeur marchande",
        "panelsJSON": json.dumps([
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": "1"}, "panelIndex": "1", "panelRefName": "panel_0"}
        ]),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        }
    }
    dash_market_refs = [
        {"name": "panel_0", "type": "visualization", "id": vis_market_upset_id}
    ]
    create_saved_object("dashboard", dash_market_id, dash_market_attrs, dash_market_refs)

    print("\nDashboards créés avec succès !")
    print(f"Weather Dashboard: {KIBANA_URL}/app/dashboards#/view/{dash_weather_id}")
    print(f"Market Dashboard:  {KIBANA_URL}/app/dashboards#/view/{dash_market_id}")

if __name__ == "__main__":
    main()
