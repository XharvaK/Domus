"""S2: layers from a situation scan; deterministic, budgeted, omissions counted."""
import json

from domus_helper import scene

BODY = {"room": "3", "position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}}


def _obj(object_id, cls, x, room, states=None, stats=None, craft=None):
    return {"kind": "object", "object_id": object_id, "class": cls, "room": room,
            "position": {"x": x, "y": 0.0, "z": 0.0, "level": 0},
            "states": states, "stats": stats or {}, "craft": craft}


PLATTER = _obj("1", "object_Food_PlateFork_Multi", 2.0, "3",
               states={"Freshness": "Freshness_Fresh"}, stats={"statistic_Servings": 7.0},
               craft={"recipe": "recipe_Food_EggsAndToast", "name_key": "10",
                      "multi_name_key": "11", "crafter_id": "100", "crafter": "E1 Proband"})
TRAY = _obj("2", "object_IngredientTray_Carb", 3.0, "3",
            states={"Freshness": "Freshness_Spoiled"})
SINK = _obj("3", "object_sinkPedC", 9.0, "5", states={"Dirtiness": "Dirtiness_Clean"})
FRIDGE = _obj("4", "object_fridgeLOW", 12.0, "5")
FLOWERS = [_obj(str(100 + i), "object_GardeningFlower_Chrysanthemum", 30.0 + i, None)
           for i in range(5)]


def test_layers_near_far_available():
    texts = {"11": "Eggs and Toast"}
    rows = [{"kind": "preflight", "object_id": "1", "name": "generic_food_Grab", "ok": True},
            {"kind": "preflight", "object_id": "1", "name": "Food_CallToMeal", "ok": False,
             "reason": "No valid sims to call."},
            {"kind": "preflight", "object_id": "1", "name": "cheat_set_as_head", "ok": False,
             "reason": "deny_name"}]
    result = scene.layers({"body": BODY}, [SINK, TRAY, PLATTER, FRIDGE] + FLOWERS,
                          resolve=texts.get, preflight_rows=rows)
    assert [fact["id"] for fact in result["near"]] == ["1", "2"]
    platter = result["near"][0]
    assert platter["name"] == "Eggs and Toast" and platter["name_source"] == "GAME_TEXT"
    assert platter["servings_left"] == 7.0 and platter["made_by"] == "E1 Proband"
    assert platter["offers"] == {"allowed": ["generic_food_Grab"], "refused": [
        {"name": "Food_CallToMeal", "game_reason": "No valid sims to call."}]}
    assert result["near"][1]["states"] == {"Freshness": "Freshness_Spoiled"}
    # far keeps only objects with a game state worth a line, servings or a recipe
    assert result["far"] == []
    assert result["available"]["GardeningFlower"] == 5
    assert result["available"]["sinkPedC"] == 1


def test_far_lines_and_name_fallback():
    spoiled = _obj("9", "object_Food_GrilledCheese_Single", 15.0, "6",
                   states={"Freshness": "Freshness_Spoiled"},
                   craft={"recipe": "recipe_Food_GrilledCheese", "name_key": "77"})
    result = scene.layers({"body": BODY}, [spoiled])
    assert result["far"] == [{"id": "9", "name": "recipe_Food_GrilledCheese", "room": "6",
                              "distance_m": 15.0, "states": ["Freshness_Spoiled"]}]


def test_budgets_count_omissions_and_order_is_stable():
    crowd = [_obj(str(i), "object_counter", 1.0 + i * 0.01, "3",
                  states={"state_%d" % k: "value_%d" % k for k in range(10)})
             for i in range(40)]
    first = scene.layers({"body": BODY}, crowd)
    second = scene.layers({"body": BODY}, list(reversed(crowd)))
    assert first == second
    assert len(json.dumps(first["near"], separators=(",", ":"))) <= scene.BUDGET["near"]
    assert first["near_omitted"] == 40 - len(first["near"]) > 0
