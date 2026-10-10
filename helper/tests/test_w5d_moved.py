"""2.32.0 (HE5): a moved object closes its old room fact and opens the new one, and object-room facts come from
the 16 nearest objects of the sample (never from a menu's four objects)."""
from domus_helper.notebook import Notebook


def _row(near=(), moved=()):
    return {"objects": {"near_rooms": [{"object_id": oid, "class": "object_fridge_X", "room": room}
                                       for oid, room in near],
                        "moved": [{"object_id": oid, "class": "object_fridge_X", "from_room": a, "to_room": b}
                                  for oid, a, b in moved]}}


def test_a_moved_object_closes_the_old_room_and_opens_the_new_one(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_near_rooms("w", _row(near=[("12", "4")]), 1_000)
    book.observe_near_rooms("w", _row(near=[("12", "5")], moved=[("12", "4", "5")]), 2_000)
    rows = book._con.execute("SELECT value, valid_until_ms FROM facts WHERE subject = '12'"
                             " ORDER BY id").fetchall()
    assert [(r["value"], r["valid_until_ms"]) for r in rows] == [("4", 2_000), ("5", None)]
    book.close()


def test_an_object_that_did_not_move_keeps_its_fact(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_near_rooms("w", _row(near=[("13", "4")]), 1_000)
    book.observe_near_rooms("w", _row(near=[("13", "4")]), 2_000)
    assert book._con.execute("SELECT COUNT(*) FROM facts WHERE subject = '13'").fetchone()[0] == 1
    book.close()


def test_a_menu_sets_no_room_fact(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_menu("w", {"room": "4", "objects": [{"object_id": "14", "class": "object_fridge_X",
                                                       "same_room": True, "acts": []}]}, 1_000)
    assert book._con.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
    book.close()
