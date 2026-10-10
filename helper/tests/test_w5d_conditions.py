"""2.32.0 (HE7): the notable conditions of the near objects reach her as an env object_state percept on change, a
portrait line (no object ids), and an object_condition notebook fact that closes once the object is no longer named.
An older notebook (without the kind) gets its facts table rebuilt with its rows kept."""
import sqlite3

from domus_helper.notebook import CONDITION_STALE_MS, Notebook
from domus_helper.thalamus import observation
from domus_helper.thalamus.percepts import Extractor, _conditions_of


def _objects(*entries):
    return {"baseline": False, "created": [], "destroyed": [], "changed": [], "truncated": False,
            "near_conditions": [{"object_id": object_id, "class": klass,
                                 "states": [{"state": state, "value": value} for state, value in states]}
                                for object_id, klass, states in entries]}


def test_a_condition_that_comes_and_clears_is_one_percept_each_time():
    extractor = Extractor()
    came = extractor._condition_percepts({}, _conditions_of(_objects(("7", "object_fridge_Stove",
                                                                     [("Freshness", "Freshness_Spoiled")]))), 500)
    assert [(p.kind, p.subject, p.object) for p in came] == [("env", "object_state", "7")]
    assert dict(came[0].facts)["states"] == "Freshness=Freshness_Spoiled"
    before = _conditions_of(_objects(("7", "object_fridge_Stove", [("Freshness", "Freshness_Spoiled")])))
    assert extractor._condition_percepts(before, before, 600) == []
    cleared = extractor._condition_percepts(before, _conditions_of(_objects()), 700)
    assert len(cleared) == 1 and dict(cleared[0].facts)["states"] == ""


def test_the_portrait_names_the_notable_states_in_words_and_never_an_object_id():
    row = {"zone": {"room": "hall"}, "presence": [{"id": "1", "is_body": True, "name": "Ada", "room": "hall",
                                                  "level": 0}],
           "objects": _objects(("7", "object_fridge_Stove", [("Freshness", "Freshness_Spoiled")]))}
    lines = observation._portrait(row)["near_conditions"]
    assert lines == [{"object": "object fridge Stove", "states": ["Freshness Spoiled"]}]
    assert "7" not in str(lines)


def test_a_sample_without_the_block_says_nothing_about_conditions():
    row = {"zone": {"room": "hall"}, "presence": []}
    assert "near_conditions" not in observation._portrait(row)


def test_the_notebook_keeps_a_condition_fact_while_named_and_closes_it_once_stale(tmp_path):
    notebook = Notebook(tmp_path / "notebook.db")
    row = {"objects": _objects(("7", "object_fridge_Stove", [("Freshness", "Freshness_Spoiled")]))}
    notebook.observe_conditions("w", row, 1_000)
    facts = notebook._con.execute("SELECT kind, subject, value, valid_until_ms FROM facts").fetchall()
    assert [tuple(item) for item in facts] == [("object_condition", "7", "Freshness=Freshness_Spoiled", None)]
    notebook.observe_conditions("w", row, 1_000 + CONDITION_STALE_MS + 1)
    closed = notebook._con.execute("SELECT valid_until_ms FROM facts WHERE kind = 'object_condition'").fetchone()
    assert closed["valid_until_ms"] is not None
    notebook.close()


def test_an_older_notebook_gets_the_kind_and_keeps_its_facts(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(str(path))
    con.executescript("""
CREATE TABLE facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, world TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('object_room', 'lives_here')),
  subject TEXT NOT NULL, value TEXT NOT NULL, label TEXT, valid_from_ms INTEGER NOT NULL,
  valid_until_ms INTEGER, seen_ms INTEGER NOT NULL);
CREATE UNIQUE INDEX facts_open ON facts (world, kind, subject) WHERE valid_until_ms IS NULL;
INSERT INTO facts (world, kind, subject, value, label, valid_from_ms, valid_until_ms, seen_ms)
  VALUES ('w', 'object_room', '4', '2', 'stove', 1, NULL, 1);
""")
    con.commit()
    con.close()
    notebook = Notebook(path)
    kept = notebook._con.execute("SELECT id, kind, subject, value FROM facts").fetchall()
    assert [tuple(item) for item in kept] == [(1, "object_room", "4", "2")]
    notebook.observe_conditions("w", {"objects": _objects(("9", "object_bin", [("Cleanliness", "Cleanliness_Dirty")]))},
                                5)
    assert notebook._con.execute("SELECT COUNT(*) FROM facts WHERE kind = 'object_condition'").fetchone()[0] == 1
    notebook.close()
