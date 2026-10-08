"""W2h in the helper: the notebook keeps the interactions whose act ended on a screen only the
User's hands can use (never deleted), her menu keeps those acts listed and marked, and the
notebook's show output carries them. Invented strings only."""
import json

from domus_helper.acts import OPENS_SCREEN, options
from domus_helper.notebook import Notebook
from domus_helper.windows import withheld_of

MENU = {"menu_rev": 1, "room": "4", "objects": [
    {"object_id": "11", "definition_id": None, "class": "object_vase", "distance_m": 1.5, "same_room": True,
     "acts": [{"guid64": "4242", "name": "vase_Arrange", "text_key": None},
              {"guid64": "4243", "name": "vase_Sniff", "text_key": None}]}]}


def test_a_withheld_interaction_is_counted_once_per_act_and_never_deleted(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_withheld("vase_Arrange", "msg_17", 1000)
    book.observe_withheld("vase_Arrange", "msg_17", 2000)
    book.observe_withheld("", "msg_17", 3000)
    book.observe_withheld("vase_Arrange", "", 3000)
    book.rebuild_procedures([], 4000)
    book.close()
    again = Notebook(tmp_path / "notebook.db")
    rows = [dict(row) for row in again._con.execute("SELECT * FROM withheld")]
    assert rows == [{"tuning": "vase_Arrange", "screen": "msg_17", "n": 2, "first_ms": 1000, "last_ms": 2000}]
    assert again.withheld_names() == {"vase_Arrange"}


def test_show_lists_the_withheld_interactions(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_withheld("vase_Arrange", "msg_17", 1000)
    shown = book.show()
    assert shown["withheld"] == [{"tuning": "vase_Arrange", "screen": "msg_17", "n": 1,
                                  "first_ms": 1000, "last_ms": 1000}]
    assert json.loads(json.dumps(shown))["withheld"][0]["tuning"] == "vase_Arrange"


def test_her_menu_keeps_such_an_act_listed_and_marks_it():
    result = options(MENU, withheld={"vase_Arrange"})
    acts = result[0]["acts"]
    assert [act["guid64"] for act in acts] == ["4242", "4243"]
    assert acts[0]["opens"] == OPENS_SCREEN == "a screen only the User's hands can use"
    assert "opens" not in acts[1]
    assert "opens" not in options(MENU)[0]["acts"][0]


def test_the_screen_an_act_ended_on_is_read_from_its_code_and_tuning_name():
    row = {"event_kind": "act_event", "e2": {"act_id": "a" * 32, "phase": "FINISHED",
                                             "code": "SCREEN_WITHHELD:msg_17", "tuning_name": "vase_Arrange"}}
    assert withheld_of(row) == ("vase_Arrange", "msg_17")
    assert withheld_of({"event_kind": "speed_event", "e2": {"code": "SCREEN_WITHHELD:msg_17"}}) is None


def test_the_bridge_records_the_act_from_the_telemetry_and_marks_it_on_her_menu(paths, tmp_path, monkeypatch):
    from test_bridge_thalamus import WALL, _append, _bridge, _data, _lineage
    _data(paths, tmp_path, monkeypatch)
    act = {"event_kind": "act_event", "written_sequence": 2, "wall_timestamp_ms": WALL + 500,
           "monotonic_ns": 1, "telemetry_session_id": "sess-1", "probe_version": "2.5.1",
           "e2": {"act_id": "a" * 32, "phase": "FINISHED", "code": "SCREEN_WITHHELD:msg_17",
                  "tuning_name": "vase_Arrange"}}
    _append(paths, [_lineage(1, WALL), act])
    mono = {"ms": WALL + 500}
    bridge = _bridge(paths, mono)
    bridge.tick(WALL + 500)
    assert bridge.notebook.withheld_names() == {"vase_Arrange"}
    bridge._menu = {"session": "sess-1", "payload": MENU}
    listed = bridge._options({"telemetry_session_id": "sess-1", "presence": []})
    assert listed[0]["acts"][0].get("opens") == OPENS_SCREEN
    assert "opens" not in listed[0]["acts"][1]
