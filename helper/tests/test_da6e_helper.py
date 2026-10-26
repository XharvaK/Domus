"""DA6E helper: what the live 2.11.0 session showed on the helper side."""
import json

from domus_helper import crawl, food, relief_survey
from test_crawl import Clock, FakeTools, _affordance, _drive, _import, _tuned, _verdict
from test_food import _food_file

SNACK = 13397


def _pf(guid, name, ok=True, object_id="9"):
    return {"kind": "preflight", "object_id": object_id, "guid64": guid, "name": name,
            "ok": ok, "reason": None if ok else "no"}


def _presence(motives, running=()):
    observed = [{"interaction_id": iid, "source_raw": source, "membership": "RUNNING"}
                for iid, source in running]
    return {"event_kind": "presence_snapshot", "written_sequence": 1,
            "motives": [{"id": key, "value": value} for key, value in motives.items()],
            "interactions": {"observed": observed}}


def _cleanup(experiment_id, detail):
    return {"event_kind": "experiment_event",
            "e2": {"phase": "TRIAL_CLEANUP", "experiment_id": experiment_id, "detail": detail}}


def test_scan_all_errors_prints_reasons_not_none_rows():
    """D10: 706 error rows printed as 706 lines of None."""
    rows = [{"kind": "food_header", "sims_build": "1.1"}]
    rows += [{"kind": "food_affordance", "object_id": "1",
              "error": "AttributeError: favorite_recipe"}] * 3
    rows += [{"kind": "food_menu", "object_id": "1", "error": "AttributeError: x"}]
    assert food.summarize(rows) == []
    assert food.errors_of(rows) == [("AttributeError: favorite_recipe", 3),
                                    ("AttributeError: x", 1)]


def test_eat_falls_back_to_preflight_food_routes(tmp_path, monkeypatch):
    """D10: an unusable scan left --eat with no route; the snack still passed preflight."""
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "domus-data"))
    sims = tmp_path / "sims"
    tools = FakeTools(tmp_path)
    tools.paths = type(tools.paths)(sims, tmp_path / "game")
    atlas_dir = sims / "AshleyE1Telemetry" / "atlas"
    _food_file(atlas_dir, [
        {"kind": "food_header", "sims_build": "1.1"},
        {"kind": "food_affordance", "object_id": "9", "error": "AttributeError"},
        {"kind": "food_footer", "count": 0, "errors": 1},
    ])
    (atlas_dir / "preflight_1.1_2.jsonl").write_text("".join(json.dumps(row) + "\n" for row in [
        {"kind": "preflight_header"}, _pf(13388, "fridge_CookAutonomously"),
        _pf(SNACK, "fridge_GrabSnackAutonomously"), {"kind": "preflight_footer"},
    ]), encoding="utf-8")
    tools.replies = ["TRIAL_PUSHED exp-1 interaction 1"]
    tools.rows = [{"event_kind": "experiment_event",
                   "e2": {"phase": "VERDICT", "experiment_id": "exp-1", "code": "PASS",
                          "detail": "route=auto_craft hunger=31->80->79",
                          "tuning_name": "fridge_GrabSnackAutonomously", "ambiguous": []}}]
    tools.paths.atlas_db.parent.mkdir(parents=True, exist_ok=True)
    clock = Clock()
    assert food.eat(tools, telemetry_rows=lambda: tools.rows, sleep=clock.sleep,
                    monotonic=lambda: clock.t + 0.001) == 0
    assert tools.sent[-1] == ("trial", {"object_id": "9", "guid64": str(SNACK)})


def test_wait_left_running_records_needs_at_finish():
    """D13: a relief left running is measured when she is idle again."""
    clock = Clock()
    rows = [_cleanup("e1", "relief_left_running"),
            _presence({"energy": 30}, running=[("5", "InteractionSource.SCRIPT")])]

    def read():
        if clock.t > 20:
            rows[-1] = _presence({"energy": 95},
                                 running=[("6", "InteractionSource.POSTURE_GRAPH")])
        return rows

    found = crawl.wait_left_running(read, "e1", clock.sleep, clock.monotonic, timeout=600)
    assert found["detail"] == "relief_left_running"
    assert found["needs_finish"] == [{"id": "energy", "value": 95}]
    assert crawl.wait_left_running(lambda: [_cleanup("e2", "CANCELLED")], "e2",
                                   clock.sleep, clock.monotonic) is None


def test_wait_left_running_is_bounded_with_a_frozen_clock():
    stuck = [_cleanup("e1", "food_left_running"),
             _presence({"hunger": 30}, running=[("5", "InteractionSource.SCRIPT")])]
    found = crawl.wait_left_running(lambda: stuck, "e1", lambda _s: None, lambda: 0.0,
                                    timeout=30)
    assert found["timeout"] is True


def test_relief_survey_picks_the_plain_cure_and_never_cleaning():
    rows = [_pf(1, "toilet_Clean"), _pf(2, "toilet-use-sitting"),
            _pf(3, "shower_TakeShower_Steamy"), _pf(4, "shower_TakeShower"),
            _pf(5, "shower_Clean"), _pf(6, "sofa_Nap"), _pf(7, "bed_sleep"),
            _pf(8, "bed_sleep", ok=False), _pf(SNACK, "fridge_GrabSnackAutonomously")]
    assert relief_survey.cure_for("bladder", rows)["guid64"] == 2
    assert relief_survey.cure_for("hygiene", rows)["guid64"] == 4
    assert relief_survey.cure_for("energy", rows)["guid64"] == 7
    assert relief_survey.cure_for("hunger", rows)["guid64"] == SNACK
    assert relief_survey.cure_for("bladder", [_pf(1, "toilet_Clean")]) is None
    assert relief_survey.low_need({"bladder": 30, "hunger": 20, "fun": 5}) == "hunger"
    assert relief_survey.low_need({"bladder": 60, "fun": 5}) is None


def _survey_drive(tmp_path, survey):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_PUSHED exp1 interaction 5"]
    tools.rows = [_presence({"bladder": 30}), _verdict("exp1")]
    clock = Clock()
    preflight = [_pf(1, "sit", object_id="1"), _pf(2, "toilet-use-sitting", object_id="7")]
    _drive(tools, db, [_tuned(1, [1])], clock, max_trials=1, preflight_rows=preflight,
           survey=survey)
    return tools


def test_relief_survey_is_opt_in(tmp_path):
    """Owner 2026-10-04: telemetry, not her policy. Off unless asked for."""
    off = _survey_drive(tmp_path / "off", False)
    assert [args for name, args in off.sent if name == "trial"][0]["guid64"] == "1"
    on = _survey_drive(tmp_path / "on", True)
    assert [args for name, args in on.sent if name == "trial"][0] == {
        "object_id": "7", "guid64": "2"}


def test_crawl_asks_for_a_fresh_preflight(tmp_path):
    """D9: the crawl used only an older file; none existed, so nothing was filtered."""
    tools = FakeTools(tmp_path)
    folder = tools.paths.atlas_dir
    folder.mkdir(parents=True, exist_ok=True)
    clock = Clock()

    def sleep(seconds):
        clock.sleep(seconds)
        (folder / "preflight_1.1_9.jsonl").write_text(
            json.dumps(_pf(1, "sit")) + "\n" + json.dumps({"kind": "preflight_footer"}) + "\n",
            encoding="utf-8")

    rows = crawl.fresh_preflight(tools, timeout=30, sleep=sleep, monotonic=clock.monotonic)
    assert ("preflight", {}) in tools.sent
    assert rows[-1]["kind"] == "preflight_footer"
