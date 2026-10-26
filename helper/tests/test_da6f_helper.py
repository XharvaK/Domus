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


def _distress_drive(tmp_path, motives, survey, preflight, capsys=None):
    from domus_helper import crawl
    from test_crawl import Clock, FakeTools, _affordance, _drive, _import, _tuned, _verdict
    from test_da6e_helper import _presence
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "shower_UpgradeFasterHygiene")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_PUSHED exp1 interaction 5"]
    tools.rows = [_presence(motives), _verdict("exp1")]
    code = _drive(tools, db, [_tuned(1, [1])], Clock(), max_trials=1,
                  preflight_rows=preflight, survey=survey)
    lines = capsys.readouterr().out.strip().splitlines() if capsys else []
    return tools, (lines[-1] if code == 2 and lines else None)


def _pf(guid, name, object_id="1"):
    return {"kind": "preflight", "object_id": object_id, "guid64": guid, "name": name,
            "ok": True, "reason": None}


def test_no_trial_is_pushed_into_a_visible_distress(tmp_path, capsys):
    """D23: two mirror trials went into bladder 15; the stop said 'feed/rest her'."""
    tools, stop = _distress_drive(tmp_path, {"bladder": 15, "hunger": 60}, False,
                                  [_pf(1, "shower_UpgradeFasterHygiene")], capsys)
    assert stop == "the lab Sim needs care: bladder 15 (distress); no trial pushed"
    assert not [name for name, _args in tools.sent if name == "trial"]


def test_survey_stops_when_no_approved_cure(tmp_path, capsys):
    """D24: no cure fell back to the plan and pushed a shower upgrade."""
    tools, stop = _distress_drive(tmp_path, {"bladder": 15}, True,
                                  [_pf(1, "shower_UpgradeFasterHygiene")], capsys)
    assert stop.startswith("relief survey: bladder is low and no preflight-approved cure")
    assert not [name for name, _args in tools.sent if name == "trial"]


def test_survey_pushes_the_cure_in_distress(tmp_path):
    tools, _stop = _distress_drive(tmp_path, {"bladder": 15}, True,
                                   [_pf(1, "shower_UpgradeFasterHygiene"),
                                    _pf(14427, "toilet-use-sitting", object_id="7")])
    assert [args for name, args in tools.sent if name == "trial"][0] == {
        "object_id": "7", "guid64": "14427"}


def test_distress_text_names_body_needs_only():
    from domus_helper import crawl
    from test_da6e_helper import _presence
    assert crawl.distress_text([_presence({"bladder": 15, "fun": 3, "energy": 20})]) == (
        "bladder 15, energy 20")
    assert crawl.distress_text([_presence({"bladder": 21})]) is None
