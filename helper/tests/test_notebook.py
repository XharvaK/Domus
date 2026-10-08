"""The world notebook: facts that close instead of disappearing, and procedures."""
import json
from pathlib import Path

import domus_helper.notebook as notebook
from domus_helper.notebook import Notebook
from domus_helper.thalamus import observation


def _menu(room, object_id="501", same_room=True, acts=None):
    obj = {"object_id": object_id, "definition_id": "1", "class": "object_fridge_X",
           "same_room": same_room, "acts": acts or []}
    return {"menu_rev": 1, "room": room, "objects": [obj]}


def _records(name, deltas, origins=None):
    origins = origins or ["counter"] * len(deltas)
    return [{
        "interaction": {"name": name},
        "needs": {"delta": delta},
        "origin": origin,
        "company": False,
        "act_id": "a%s" % index,
    } for index, (delta, origin) in enumerate(zip(deltas, origins), start=1)]


def test_object_room_closes_and_opens(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_menu("slot1", _menu("7"), 1000)
    rows = book._con.execute("SELECT * FROM facts").fetchall()
    assert len(rows) == 1 and rows[0]["value"] == "7" and rows[0]["label"] == "fridge"
    assert rows[0]["valid_until_ms"] is None
    book.observe_menu("slot1", _menu("7"), 2000)
    rows = book._con.execute("SELECT * FROM facts").fetchall()
    assert len(rows) == 1 and rows[0]["seen_ms"] == 2000
    book.observe_menu("slot1", _menu("9"), 3000)
    rows = book._con.execute(
        "SELECT value, valid_until_ms FROM facts ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["value"] == "7" and rows[0]["valid_until_ms"] == 3000
    assert rows[1]["value"] == "9" and rows[1]["valid_until_ms"] is None
    book.observe_menu("slot1", _menu("9", same_room=False), 4000)
    book.observe_menu("slot1", {"menu_rev": 1, "room": None, "objects": [
        {"object_id": "9", "class": "object_fridge_X", "same_room": True, "acts": []}]}, 4000)
    assert book._con.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 2
    book.close()


def test_lives_here_only_at_her_home(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    row = {"place": {"her_home": True, "owner_household_id": 42}, "presence": [
        {"id": 11, "household_id": 42, "name": "Ann"},
        {"id": 12, "household_id": 99, "name": "Bea"}]}
    book.observe_presence("slot1", row, 1000)
    facts = book._con.execute("SELECT subject, value, label FROM facts").fetchall()
    assert [(item["subject"], item["value"], item["label"]) for item in facts] == [("11", "42", "Ann")]
    book.observe_presence("slot1", {"place": {"her_home": False, "owner_household_id": 42},
                                    "presence": [{"id": 13, "household_id": 42, "name": "Cy"}]}, 2000)
    assert book._con.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 1
    book.close()


def test_facts_are_never_deleted(tmp_path):
    source = Path(notebook.__file__).read_text(encoding="utf-8")
    assert "DELETE FROM facts" not in source
    book = Notebook(tmp_path / "notebook.db")
    book.observe_menu("slot1", _menu("7"), 1000)
    book.observe_menu("slot1", _menu("9"), 3000)
    closed = book._con.execute(
        "SELECT value FROM facts WHERE valid_until_ms IS NOT NULL").fetchone()
    assert closed["value"] == "7"
    book.close()


def test_procedures_need_agreement_and_rebuild_drops_what_no_longer_holds(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    held = _records("fridge_Grab_Snack", [
        {"hunger": 20, "fun": 3}, {"hunger": 25, "fun": -2}, {"hunger": 30, "fun": 1}])
    count = book.rebuild_procedures(held + _records("book_Read", [{"hunger": 40}]), 5000)
    assert count == 1
    row = book._con.execute("SELECT interaction, n, needs FROM procedures").fetchone()
    assert row["interaction"] == "fridge_Grab_Snack" and row["n"] == 3
    assert json.loads(row["needs"]) == {"hunger": 25}
    tiny = _records("sip", [{"hunger": 2}, {"hunger": 3}])
    assert book.rebuild_procedures(tiny, 6000) == 0
    assert book._con.execute("SELECT COUNT(*) FROM procedures").fetchone()[0] == 0
    book.close()


def test_a_procedure_keeps_the_time_she_first_had_it(tmp_path):
    # HE13: an upsert keeps first_ms; a notebook from before the column gets it from its last update.
    book = Notebook(tmp_path / "notebook.db")
    held = _records("fridge_Grab_Snack", [{"hunger": 20}, {"hunger": 25}, {"hunger": 30}])
    book.rebuild_procedures(held, 5000)
    book.rebuild_procedures(held, 9000)
    row = book._con.execute("SELECT n, first_ms, updated_ms FROM procedures").fetchone()
    assert (row["n"], row["first_ms"], row["updated_ms"]) == (3, 5000, 9000)
    book.close()
    old = tmp_path / "old.db"
    import sqlite3
    raw = sqlite3.connect(str(old))
    raw.execute("CREATE TABLE procedures (interaction TEXT PRIMARY KEY, n INTEGER NOT NULL, needs TEXT NOT NULL,"
                " conditions TEXT NOT NULL, act_ids TEXT NOT NULL, updated_ms INTEGER NOT NULL)")
    raw.execute("INSERT INTO procedures VALUES ('sip', 2, '{}', '{}', '[]', 4000)")
    raw.commit()
    raw.close()
    migrated = Notebook(old)
    assert migrated.show()["procedures"][0]["first_ms"] == 4000
    migrated.close()


def test_a_development_trial_never_teaches_a_procedure(tmp_path):
    # HE13: origin "experiment" is development tooling, not something she learned.
    book = Notebook(tmp_path / "notebook.db")
    trials = _records("fridge_Grab_Snack", [{"hunger": 20}, {"hunger": 25}, {"hunger": 30}],
                      origins=["experiment"] * 3)
    assert book.rebuild_procedures(trials, 5000) == 0
    mixed = _records("fridge_Grab_Snack", [{"hunger": 20}, {"hunger": 25}, {"hunger": 30}],
                     origins=["experiment", "counter", "counter"])
    assert book.rebuild_procedures(mixed, 6000) == 1
    assert book._con.execute("SELECT n FROM procedures").fetchone()["n"] == 2
    book.close()


def test_slice_offers_moves_and_trims(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_menu("slot1", _menu("7"), 1_000)
    book.observe_menu("slot1", _menu("9"), 2_000)
    book.rebuild_procedures(_records("fridge_Grab_Snack", [
        {"hunger": 20}, {"hunger": 25}, {"hunger": 30}]), 2_000)
    offered = _menu("9", acts=[{"name": "fridge_Grab_Snack"}])
    sliced = book.slice("slot1", offered, 2_000)
    assert sliced["procedures"][0]["interaction"] == "fridge_Grab_Snack"
    assert sliced["moved"][0]["was_in"] == "7" and sliced["moved"][0]["now_in"] == "9"
    quiet = book.slice("slot1", _menu("9", acts=[{"name": "other"}]), 2_000)
    assert "procedures" not in quiet
    assert book.slice("slot1", offered, 2_000 + 25 * 3_600_000).get("moved") is None
    long = []
    for index in range(40):
        name = "act_%02d_%s" % (index, "n" * 180)
        long.extend(_records(name, [{"hunger": 10}, {"hunger": 12}]))
    book.rebuild_procedures(long, 3_000)
    menu = {"room": "9", "objects": [{"object_id": "501", "same_room": True, "acts": [
        {"name": "act_%02d_%s" % (index, "n" * 180)} for index in range(40)]}]}
    wide = book.slice("slot1", menu, 3_000)
    assert len(json.dumps(wide, separators=(",", ":")).encode()) <= 1024
    assert len(wide["procedures"]) < 6
    book.close()


def test_portrait_sheds_notebook_before_moodlets():
    note = {"procedures": [{"interaction": "fridge_Grab_Snack", "n": 3, "needs": {"hunger": 25}}]}
    small = observation._portrait({"motives": []}, None, notebook=note)
    assert small["notebook"] == note
    row = {"sim_signals": [
        {"kind": "MOODLET", "tuning_id": str(index), "tuning_name": "m" * 1500,
         "visible": True, "magnitude": "w:1"}
        for index in range(200)]}
    with_note = observation._portrait(row, None, notebook=note)
    without = observation._portrait(row, None)
    assert "notebook" not in with_note
    assert with_note["moodlets"]
    assert len(with_note["moodlets"]) >= len(without["moodlets"])


def test_cli_show_and_rebuild(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert notebook.main(["show"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["facts_open"] == 0 and shown["procedures"] == []
    folder = tmp_path / "outcomes"
    folder.mkdir()
    records = _records("fridge_Grab_Snack", [{"hunger": 20}, {"hunger": 25}, {"hunger": 30}])
    (folder / "day.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    assert notebook.main(["rebuild"]) == 0
    assert json.loads(capsys.readouterr().out) == {"procedures": 1}
