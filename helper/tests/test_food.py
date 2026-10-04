"""Food command: route preference, preflight skip, ledger, crawl guid skip."""
import json

from domus_helper import atlas, crawl, food
from test_crawl import FakeTools, _affordance, _import, _tuned


def _food_file(folder, rows):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "food_1.1_1.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _offer(route, guid, name, object_id="9"):
    return {
        "kind": "food_affordance", "object_id": object_id, "guid64": guid, "name": name,
        "food_route": route, "excluded": None,
    }


def test_choose_prefers_autopick_then_snack_then_cook():
    rows = [
        _offer("auto_craft", 13388, "fridge_CookAutonomously"),
        _offer("auto_craft", 13397, "fridge_GrabSnackAutonomously"),
        _offer("auto_pick", 60, "fridge_GrabLeftover"),
    ]
    assert food.choose(rows, None)["guid64"] == 60
    refused = [{"kind": "preflight", "object_id": "9", "guid64": 60, "ok": False, "reason": "no"}]
    assert food.choose(rows, refused)["guid64"] == 13397
    refused.append({"kind": "preflight", "object_id": "9", "guid64": 13397, "ok": False})
    assert food.choose(rows, refused)["guid64"] == 13388


def test_eat_records_ledger_and_hunger(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "domus-data"))
    sims = tmp_path / "sims"
    tools = FakeTools(tmp_path)
    tools.paths = type(tools.paths)(sims, tmp_path / "game")
    atlas_dir = sims / "AshleyE1Telemetry" / "atlas"
    _food_file(atlas_dir, [
        {"kind": "food_header", "sims_build": "1.1"},
        _offer("auto_pick", 60, "fridge_GrabLeftover", "9"),
        {"kind": "food_footer", "count": 1, "errors": 0},
    ])
    tools.replies = ["TRIAL_PUSHED exp-1 interaction 1"]
    tools.rows = [{
        "event_kind": "experiment_event",
        "e2": {"phase": "VERDICT", "experiment_id": "exp-1", "code": "PASS",
               "detail": "route=auto_pick hunger=10->40 foreign_roots=0",
               "tuning_name": "fridge_GrabLeftover", "ambiguous": []},
    }]
    db = tools.paths.atlas_db
    db.parent.mkdir(parents=True, exist_ok=True)
    assert food.eat(tools, telemetry_rows=lambda: tools.rows, sleep=lambda _s: None,
                    monotonic=_Clock().monotonic) == 0
    assert tools.sent[-1] == ("trial", {"object_id": "9", "guid64": "60"})
    recorded = atlas.trials_for(db, "1.1")
    assert recorded[0]["outcome"] == "PASS"
    line = capsys.readouterr().out.strip()
    assert line == "eat route=auto_pick verdict=PASS hunger=10->40"


class _Clock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        self.t += 1
        return self.t


def test_crawl_skips_food_guids(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [
        _affordance(13397, "fridge_GrabSnackAutonomously"),
        _affordance(13388, "fridge_CookAutonomously"),
        _affordance(4, "sit"),
    ])
    planned = crawl.plan("1.1", [_tuned(5, [13397, 13388, 4])], db, limit=10)
    assert [item["guid64"] for item in planned] == [4]
