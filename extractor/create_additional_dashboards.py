import requests
import json
import os

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}

def get_data_view_id(title_pattern):
    """Récupère l'ID du data view correspondant au pattern (ex: football_*)"""
    print(f"Recherche du Data View pour '{title_pattern}'...")
    response = requests.get(f"{KIBANA_URL}/api/data_views", headers=HEADERS)
    if response.status_code == 200:
        data_views = response.json().get("data_view", [])
        for dv in data_views:
            if dv.get("title") == title_pattern:
                return dv.get("id")
    
    # Si non trouvé, on en crée un avec un ID connu
    print(f"Data view non trouvé, création de '{title_pattern}'...")
    override_id = title_pattern.replace("*", "all").replace("_", "-")
    data_view = {
        "data_view": {
            "title": title_pattern,
            "name": f"Created for Dashboard ({title_pattern})",
            "id": override_id
        }
    }
    res = requests.post(f"{KIBANA_URL}/api/data_views/data_view", headers=HEADERS, json=data_view)
    if res.status_code in [200, 201]:
        return res.json().get("data_view", {}).get("id")
    return None

def create_dashboard(dashboard_id, title, description, panels, data_view_id):
    """Crée un dashboard en utilisant les API Saved Objects"""
    
    # Mettre à jour les références avec le bon data_view_id
    for panel in panels:
        if "embeddableConfig" in panel and "references" in panel["embeddableConfig"]:
            for ref in panel["embeddableConfig"]["references"]:
                if ref["type"] == "index-pattern":
                    ref["id"] = data_view_id

    # On doit utiliser l'API d'import car c'est la façon la plus fiable pour les dashboards avec Lens
    # L'API _import attend du NDJSON
    
    # Construction de l'objet pour NDJSON
    dashboard_obj = {
        "attributes": {
            "title": title,
            "hits": 0,
            "description": description,
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
            "version": 1,
            "timeRestore": False,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        },
        "id": dashboard_id,
        "type": "dashboard",
        "references": [],
        "managed": False
    }
    
    # Pour Lens, si les références sous embeddableConfig pointent vers un index-pattern, 
    # l'objet de plus haut niveau au-dessus (le dashboard) n'a pas nécessairement besoin
    # d'inclure ces références dans la racine `references: []` lors d'un import NDJSON s'il
    # s'agit d'un import classique sans résolution stricte. Cependant, pour être sûr,
    # ajoutons le data view dans le NDJSON ou utilisons un hack.
    # En fait, Kibana tolère les ID si on utilise le format exporté.
    
    ndjson_str = json.dumps(dashboard_obj) + "\n"
    
    print(f"Importation du dashboard '{title}'...")
    response = requests.post(
        f"{KIBANA_URL}/api/saved_objects/_import?overwrite=true",
        headers={"kbn-xsrf": "true"},
        files={"file": (f"{dashboard_id}.ndjson", ndjson_str, "application/ndjson")}
    )
    
    if response.status_code == 200:
        print(f"✅ Dashboard '{title}' importé avec succès: {KIBANA_URL}/app/dashboards#/view/{dashboard_id}")
    else:
        print(f"❌ Erreur lors de l'import {response.status_code}: {response.text}")


def main():
    dv_combined = get_data_view_id("football_*")
    
    if not dv_combined:
        print("Impossible de trouver ou créer le Data View combiné.")
        return

    # ----- 1. WEATHER DASHBOARD -----
    weather_panels = [
        # Panel 1: Répartition des conditions météo (Pie)
        {
            "version": "8.11.0",
            "type": "lens",
            "gridData": {"x": 0, "y": 0, "w": 24, "h": 12, "i": "w1"},
            "panelIndex": "w1",
            "embeddableConfig": {
                "attributes": {
                    "title": "Matchs par condition météo",
                    "visualizationType": "lnsPie",
                    "state": {
                        "datasourceStates": {
                            "formBased": {
                                "layers": {
                                    "layer1": {
                                        "columns": {
                                            "col1": {
                                                "label": "Météo",
                                                "dataType": "string",
                                                "operationType": "terms",
                                                "sourceField": "weather_description.keyword",
                                                "params": {"size": 10}
                                            },
                                            "col2": {
                                                "label": "Nb Matchs",
                                                "dataType": "number",
                                                "operationType": "count"
                                            }
                                        },
                                        "columnOrder": ["col1", "col2"]
                                    }
                                }
                            }
                        },
                        "visualization": {
                            "shape": "pie",
                            "layers": [{"layerId": "layer1", "primaryGroups": ["col1"], "metrics": ["col2"]}]
                        }
                    },
                    "references": [{"type": "index-pattern", "id": "PLACEHOLDER", "name": "indexpattern-datasource-layer-layer1"}]
                }
            }
        },
        # Panel 2: Upsets lors de pluie (Pie)
        {
            "version": "8.11.0",
            "type": "lens",
            "gridData": {"x": 24, "y": 0, "w": 24, "h": 12, "i": "w2"},
            "panelIndex": "w2",
            "embeddableConfig": {
                "attributes": {
                    "title": "Upsets (Surprises) par condition météo",
                    "visualizationType": "lnsPie",
                    "state": {
                        "datasourceStates": {
                            "formBased": {
                                "layers": {
                                    "layer1": {
                                        "columns": {
                                            "col1": {
                                                "label": "Météo",
                                                "dataType": "string",
                                                "operationType": "terms",
                                                "sourceField": "weather_description.keyword",
                                                "params": {"size": 10}
                                            },
                                            "col2": {
                                                "label": "Upsets",
                                                "dataType": "number",
                                                "operationType": "count"
                                            }
                                        },
                                        "columnOrder": ["col1", "col2"]
                                    }
                                }
                            }
                        },
                        "visualization": {
                            "shape": "donut",
                            "layers": [{"layerId": "layer1", "primaryGroups": ["col1"], "metrics": ["col2"]}]
                        },
                        "query": {
                            "query": "is_upset: true",
                            "language": "kuery"
                        }
                    },
                    "references": [{"type": "index-pattern", "id": "PLACEHOLDER", "name": "indexpattern-datasource-layer-layer1"}]
                }
            }
        }
    ]
    
    create_dashboard(
        "weather-impact-dashboard", 
        "Weather Impact Analysis", 
        "Dashboard analysant l'impact de la météo sur les matchs de football", 
        weather_panels, 
        dv_combined
    )

    # ----- 2. MARKET VALUE DASHBOARD -----
    market_panels = [
        # Panel 1: Ratio de valeur selon l'issue du match (Pie)
        {
            "version": "8.11.0",
            "type": "lens",
            "gridData": {"x": 0, "y": 0, "w": 24, "h": 12, "i": "m1"},
            "panelIndex": "m1",
            "embeddableConfig": {
                "attributes": {
                    "title": "Vainqueur du match",
                    "visualizationType": "lnsPie",
                    "state": {
                        "datasourceStates": {
                            "formBased": {
                                "layers": {
                                    "layer1": {
                                        "columns": {
                                            "col1": {
                                                "label": "Vainqueur",
                                                "dataType": "string",
                                                "operationType": "terms",
                                                "sourceField": "actual_winner.keyword",
                                                "params": {"size": 3}
                                            },
                                            "col2": {
                                                "label": "Nb Matchs",
                                                "dataType": "number",
                                                "operationType": "count"
                                            }
                                        },
                                        "columnOrder": ["col1", "col2"]
                                    }
                                }
                            }
                        },
                        "visualization": {
                            "shape": "pie",
                            "layers": [{"layerId": "layer1", "primaryGroups": ["col1"], "metrics": ["col2"]}]
                        }
                    },
                    "references": [{"type": "index-pattern", "id": "PLACEHOLDER", "name": "indexpattern-datasource-layer-layer1"}]
                }
            }
        },
        # Panel 2: Total Valeur Combinée par Compétition (Pie)
        {
            "version": "8.11.0",
            "type": "lens",
            "gridData": {"x": 24, "y": 0, "w": 24, "h": 12, "i": "m2"},
            "panelIndex": "m2",
            "embeddableConfig": {
                "attributes": {
                    "title": "Compétitions par matchs à forte valeur (>1Md)",
                    "visualizationType": "lnsPie",
                    "state": {
                        "datasourceStates": {
                            "formBased": {
                                "layers": {
                                    "layer1": {
                                        "columns": {
                                            "col1": {
                                                "label": "Compétition",
                                                "dataType": "string",
                                                "operationType": "terms",
                                                "sourceField": "competition_code.keyword",
                                                "params": {"size": 5}
                                            },
                                            "col2": {
                                                "label": "Nb Matchs",
                                                "dataType": "number",
                                                "operationType": "count"
                                            }
                                        },
                                        "columnOrder": ["col1", "col2"]
                                    }
                                }
                            }
                        },
                        "visualization": {
                            "shape": "donut",
                            "layers": [{"layerId": "layer1", "primaryGroups": ["col1"], "metrics": ["col2"]}]
                        },
                        "query": {
                            "query": "combined_market_value >= 1000000000",
                            "language": "kuery"
                        }
                    },
                    "references": [{"type": "index-pattern", "id": "PLACEHOLDER", "name": "indexpattern-datasource-layer-layer1"}]
                }
            }
        }
    ]
    
    create_dashboard(
        "market-value-dashboard", 
        "Transfer Market Analysis", 
        "Dashboard analysant la valeur marchande des équipes", 
        market_panels, 
        dv_combined
    )

if __name__ == "__main__":
    main()
