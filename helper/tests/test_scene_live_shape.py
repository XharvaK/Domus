"""S2 live check 2026-10-05: lamps at 0.3 m crowded a meal at 2.2 m out of near,
"Not_Burning" read as burning, and the portion label was used as the dish name."""
from domus_helper import scene

BODY = {"room": "3", "position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}}

LAMP_STATES = {"EmotionEnvironment_ToggleState": "EmotionEnvironment_Disabled",
               "Fire_Object_Burn_material_change": "FireState_Burn_Material_Change_Not_Burning",
               "Klepto_Stolen_Object": "Klepto_Not_Stolen_Object",
               "LightFlickeringState": "lightFlickeringState_Values_Off",
               "Lighting_States": "Lighting_On",
               "MaterialisticAdmired": "Materialistic_Admired",
               "Broken": "Brokenness_Unbroken"}


def _obj(object_id, cls, x, states=None, stats=None, craft=None):
    return {"kind": "object", "object_id": object_id, "class": cls, "room": "3",
            "position": {"x": x, "y": 0.0, "z": 0.0, "level": 0},
            "states": states, "stats": stats or {}, "craft": craft}


MEAL = _obj("900", "object_Food_PlateFork_Multi", 2.2,
            states={"Freshness": "Freshness_Fresh", "Servings": "Servings_LargeUntouched"},
            stats={"statistic_Object_Consumable_Servings": 8.0},
            craft={"recipe": "recipe_Food_Homestyle_MacNCheese-Large", "name_key": "1",
                   "multi_name_key": "2", "crafter_id": "5", "crafter": "E1 Proband"})
TEXT = {"1": "Mac and Cheese", "2": "Party Size (8)"}


def _many_offers(object_id, count=12):
    return [{"kind": "preflight", "object_id": object_id, "name": "lights_option_%02d" % i,
             "ok": True} for i in range(count)]


def test_a_meal_is_never_crowded_out_by_nearer_lamps():
    lamps = [_obj(str(100 + i), "object_light_ceiling", 0.1 * i, states=dict(LAMP_STATES))
             for i in range(18)]
    rows = [row for lamp in lamps for row in _many_offers(lamp["object_id"])]
    result = scene.layers({"body": BODY}, lamps + [MEAL], resolve=TEXT.get,
                          preflight_rows=rows)
    assert result["near_omitted"] == 0
    meal = [fact for fact in result["near"] if fact["id"] == "900"][0]
    assert meal["name"] == "Mac and Cheese" and meal["portion"] == "Party Size (8)"
    assert meal["servings_left"] == 8.0 and meal["made_by"] == "E1 Proband"
    assert meal["states"]["Freshness"] == "Freshness_Fresh"  # detail went to the meal first
    assert result["near_detail_omitted"] > 0


def test_negated_values_are_not_notable():
    assert scene.notable(LAMP_STATES) == []
    assert scene.notable({"a": "Freshness_Spoiled", "b": "BrokenState_Broken",
                          "c": "DirtyState_Dirty", "d": "Dirty_Clean"}) == [
        "BrokenState_Broken", "DirtyState_Dirty", "Freshness_Spoiled"]


def test_far_shows_food_not_unburnt_furniture():
    far_meal = dict(MEAL, object_id="901", position={"x": 20.0, "y": 0, "z": 0, "level": 0},
                    room="5")
    lamp = dict(_obj("101", "object_light_ceiling", 21.0, states=dict(LAMP_STATES)), room="5")
    result = scene.layers({"body": BODY}, [far_meal, lamp], resolve=TEXT.get)
    assert [line["id"] for line in result["far"]] == ["901"]
