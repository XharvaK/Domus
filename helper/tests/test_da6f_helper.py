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


class _Clock:
    def __init__(self):
        self.t = 0.0

    def sleep(self, seconds):
        self.t += seconds

    def monotonic(self):
        return self.t


def test_preflight_wait_follows_a_growing_partial_past_ten_minutes(tmp_path):
    """D22: 6025 rows at 10 rows/s met a fixed 600 s wait."""
    import json
    from domus_helper import crawl
    clock = _Clock()
    partial = tmp_path / "preflight_1.1_5.jsonl.partial"
    partial.write_text("{}\n", encoding="utf-8")

    def sleep(seconds):
        clock.sleep(seconds)
        if clock.t < 700:
            with partial.open("a", encoding="utf-8") as handle:
                handle.write("{}\n")
        else:
            (tmp_path / "preflight_1.1_5.jsonl").write_text(
                json.dumps({"kind": "preflight_footer"}) + "\n", encoding="utf-8")

    rows = crawl.wait_preflight(tmp_path, 0, 1800, sleep, clock.monotonic)
    assert rows[-1]["kind"] == "preflight_footer"
    assert clock.t >= 700


def test_preflight_wait_gives_up_on_a_stalled_partial(tmp_path):
    import pytest
    from domus_helper import crawl
    clock = _Clock()
    (tmp_path / "preflight_1.1_5.jsonl.partial").write_text("{}\n", encoding="utf-8")
    with pytest.raises(TimeoutError, match="stalled"):
        crawl.wait_preflight(tmp_path, 0, 1800, clock.sleep, clock.monotonic)
    assert 120 <= clock.t < 130
