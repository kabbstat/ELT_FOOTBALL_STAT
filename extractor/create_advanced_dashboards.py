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

    # ----- 1. WEATHER VS WIN (Stacked Bar Chart) -----
    vis_weather_win_id = "vis-weather-vs-win"
    vis_weather_win_attrs = {
        "title": "Weather vs Match Outcome",
        "visState": json.dumps({
            "title": "Weather vs Match Outcome",
            "type": "histogram",
            "params": {
                "type":"histogram",
                "grid":{"categoryLines":False},
                "categoryAxes":[{"id":"CategoryAxis-1","type":"category","position":"bottom","show":True}],
                "valueAxes":[{"id":"ValueAxis-1","name":"LeftAxis-1","type":"value","position":"left","show":True}],
                "seriesParams":[{"show":"true","type":"histogram","mode":"stacked","data":{"label":"Count","id":"1"}}]
            },
            "aggs": [
                {"id":"1","enabled":True,"type":"count","schema":"metric","params":{}},
                {"id":"2","enabled":True,"type":"terms","schema":"segment","params":{"field":"weather_condition","size":10,"order":"desc","orderBy":"1"}},
                {"id":"3","enabled":True,"type":"terms","schema":"group","params":{"field":"actual_winner","size":3,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "Weather condition vs Actual Winner (Home/Away/Draw)",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_weather_win_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_weather_win_id, vis_weather_win_attrs, vis_weather_win_refs)

    # ----- 2. MOST VALUED TEAM VS WIN (Pie Chart: Upsets) -----
    # By definition, if is_upset=false, the most valued team either won or drew against a closely valued team.
    # It shows the overall win rate of the favorite.
    vis_value_pie_id = "vis-value-vs-win-pie"
    vis_value_pie_attrs = {
        "title": "Most Valued Teams Win Rate (Favorites vs Upsets)",
        "visState": json.dumps({
            "title": "Most Valued Teams Win Rate",
            "type": "pie",
            "params": {"type":"pie","addTooltip":True,"addLegend":True,"legendPosition":"right","isDonut":False},
            "aggs": [
                {"id":"1","enabled":True,"type":"count","schema":"metric","params":{}},
                {"id":"2","enabled":True,"type":"terms","schema":"segment","params":{"field":"is_upset","size":2,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "False = Most valued team won/drew, True = Upset (underdog won)",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_value_pie_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_value_pie_id, vis_value_pie_attrs, vis_value_pie_refs)

    # ----- 3. WIN BY MARKET VALUE DIFFERENCE (Histogram) -----
    vis_value_diff_id = "vis-value-diff-vs-win"
    vis_value_diff_attrs = {
        "title": "Match Outcome by Market Value Ratio",
        "visState": json.dumps({
            "title": "Match Outcome by Market Value Ratio",
            "type": "histogram",
            "params": {
                "type":"histogram",
                "grid":{"categoryLines":False},
                "categoryAxes":[{"id":"CategoryAxis-1","type":"category","position":"bottom","show":True}],
                "valueAxes":[{"id":"ValueAxis-1","name":"LeftAxis-1","type":"value","position":"left","show":True}],
                "seriesParams":[{"show":"true","type":"histogram","mode":"stacked","data":{"label":"Count","id":"1"}}]
            },
            "aggs": [
                {"id":"1","enabled":True,"type":"count","schema":"metric","params":{}},
                {"id":"2","enabled":True,"type":"histogram","schema":"segment","params":{"field":"market_value_ratio","interval":1,"min_doc_count":1}},
                {"id":"3","enabled":True,"type":"terms","schema":"group","params":{"field":"actual_winner","size":3,"order":"desc","orderBy":"1"}}
            ]
        }),
        "uiStateJSON": "{}",
        "description": "Ratio of valuations between teams vs Match Outcome",
        "version": 1,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
                "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
            })
        }
    }
    vis_value_diff_refs = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": dv_id}]
    create_saved_object("visualization", vis_value_diff_id, vis_value_diff_attrs, vis_value_diff_refs)

    # ----- DASHBOARD -----
    dash_advanced_id = "dash-advanced-football"
    dash_advanced_attrs = {
        "title": "Advanced Analytics: Weather & Market Value vs Wins",
        "hits": 0,
        "description": "Dashboard complexe d'analyse",
        "panelsJSON": json.dumps([
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": "1"}, "panelIndex": "1", "panelRefName": "panel_0"},
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 24, "y": 0, "w": 12, "h": 15, "i": "2"}, "panelIndex": "2", "panelRefName": "panel_1"},
            {"version": "8.11.0", "type": "visualization", "gridData": {"x": 36, "y": 0, "w": 12, "h": 15, "i": "3"}, "panelIndex": "3", "panelRefName": "panel_2"}
        ]),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        }
    }
    dash_advanced_refs = [
        {"name": "panel_0", "type": "visualization", "id": vis_weather_win_id},
        {"name": "panel_1", "type": "visualization", "id": vis_value_pie_id},
        {"name": "panel_2", "type": "visualization", "id": vis_value_diff_id}
    ]
    create_saved_object("dashboard", dash_advanced_id, dash_advanced_attrs, dash_advanced_refs)

    print("\nDashboards créés avec succès !")
    print(f"Advanced Dashboard: {KIBANA_URL}/app/dashboards#/view/{dash_advanced_id}")

if __name__ == "__main__":
    main()
