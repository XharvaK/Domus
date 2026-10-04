"""DA6F helper: the second live session (2.11.1)."""
from domus_helper import food


def _menu(guid, name, price, enabled=True, object_id="97"):
    return {"kind": "food_menu", "object_id": object_id, "guid64": guid,
            "recipe_name": name, "price": price, "is_enable": enabled}


def test_report_labels_routes_first_and_one_line_per_menu():
    """D21: 701 unlabelled rows led with None; the 30-recipe menu was not shown."""
    rows = [
        {"kind": "food_affordance", "object_id": "97", "guid64": 10163,
         "name": "stove_CookGourmet", "food_route": None, "excluded": "picker"},
        {"kind": "food_affordance", "object_id": "97", "guid64": 13397,
         "name": "fridge_GrabSnackAutonomously", "food_route": "auto_craft", "excluded": None},
        _menu(13387, "recipe_MacAndCheese", 3), _menu(13387, "recipe_Salad", 32, enabled=False),
        {"kind": "food_menu", "object_id": "98", "guid64": 1, "error": "AttributeError: x"},
    ]
    lines = food.report(rows)
    assert lines[0].startswith("route=auto_craft guid=13397 fridge_GrabSnackAutonomously")
    assert lines[1].startswith("route=None guid=10163 stove_CookGourmet")
    assert lines[2] == ("menu obj=97 via=13387 recipes=2 enabled=1 price=3-32 "
                        "e.g. recipe_MacAndCheese, recipe_Salad")
    assert lines[3] == "error x1 AttributeError: x"
    assert lines[-1] == "rows 2 routes 1 menus 1 errors 1"
