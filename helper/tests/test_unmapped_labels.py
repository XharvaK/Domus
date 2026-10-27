"""L2: unmapped interaction labels.

When the game gives an act no label (no ``text_key`` resolved) and the helper
shows words guessed from the tuning name, the option must say ``unmapped: True``.
Acts in the game's own label, and spots the helper names, are not marked.

The label is for the view only.  Building the options and running one act
through the courier must leave no copy of it in the spool (its kv or rows), the
catalogue DB, the notebook DB or any file under the data folder, and no act
event or detail sent to Mint may carry it.

Design note (2.41.7): "unmapped" = no game label was resolved and the words are a guess from the
tuning name. RED: ``options()`` does not mark it yet, so the first test fails.  The second test passes today (the act path stores the object id, guid
and tuning name, never the label); it stays as L2's no-persist guard.
"""
import json
import sqlite3

from domus_helper import catalog, notebook
from domus_helper.acts import ActCourier, options
from domus_helper.spool import Spool

LABEL = "Zorblax the Kettle"
TUNING = "kettle_BoilWater"
TEXTS = {"9001": LABEL, "9002": "Test Kettle"}
MENU = {"menu_rev": 7, "room": "4", "objects": [
    {"object_id": "11", "definition_id": "511", "class": "object_kettle", "distance_m": 1.0,
     "same_room": True,
     "acts": [{"guid64": "4242", "name": TUNING, "text_key": "9001"},
              {"guid64": "4243", "name": "kettle_Polish", "text_key": None}]},
]}
SPOT_MENU = dict(MENU, menu_rev=8, objects=MENU["objects"] + [
    {"object_id": "91", "class": "spot", "room": "4", "level": 0, "spot": "front_door",
     "acts": [{"guid64": "6000", "name": "spot_GoHere", "text_key": "9999"}]},
])
ACT = {"act_id": "a" * 32, "object_id": "11", "guid64": "4242", "expires_at_ms": 99_000}


def _listed(menu=MENU, texts=None, catalogue=None):
    return options(menu, (texts or TEXTS).get, catalogue, room="4")


def _act(result, guid):
    for entry in result:
        for act in entry["acts"]:
            if act["guid64"] == guid:
                return act
    raise AssertionError("act %s is not listed" % guid)


def test_an_act_with_no_game_label_is_marked_unmapped_and_a_labelled_one_is_not():
    """Design (2.41.7, conservative): Domus has no curated act table; every act's words are the game's own
    label from the string index. So "unmapped" means the game gave no label and the helper shows a guess
    built from the tuning name (humanize). Labelled acts carry no unmapped key."""
    result = _listed(SPOT_MENU)
    labelled = _act(result, "4242")
    guessed = _act(result, "4243")
    spot = _act(result, "6000")
    assert labelled["text"] == LABEL
    assert "unmapped" not in labelled, "an act in the game's own label is mapped"
    assert guessed.get("unmapped") is True, "an act whose words are guessed from its tuning name is unmapped"
    assert "unmapped" not in spot, "a spot's name the helper already has is mapped"


class _Client:
    """The acts round trip Mint's side, as test_acts.py's fake."""

    def __init__(self, acts=()):
        self.acts = list(acts)
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        return {"status": "ok", "applied": len(body["events"]), "acts": list(self.acts)}


def _row(phase, **extra):
    e2 = {"act_id": "a" * 32, "phase": phase, "code": None, "object_id": "11", "guid64": "4242",
          "interaction_id": None, "tuning_name": TUNING, "finishing_type": None, "detail": None}
    e2.update(extra)
    return {"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 5000, "e2": e2}


def _stores(paths):
    """Every store the helper keeps today, each with one row, so a leak has somewhere to land."""
    data = paths.data_dir
    data.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(catalog.index_path(paths)))
    try:
        connection.executescript(catalog.SCHEMA)
        connection.execute("INSERT INTO catalog VALUES (?, ?, ?, ?, ?)", (511, 9002, 9003, 0, "fixture"))
        connection.execute("INSERT OR REPLACE INTO meta VALUES ('fingerprint', 'fixture')")
        connection.commit()
    finally:
        connection.close()
    book = notebook.Notebook(data / notebook.DB_NAME)
    try:
        # A tuning name, as the notebook really stores it: never the live label.
        book.observe_withheld(TUNING, "Create a Sim", 5000)
    finally:
        book.close()
    return data


def _files(root):
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def test_the_live_label_is_never_stored_by_the_act_path(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "data"))
    data = _stores(paths)

    chosen = _act(_listed(catalogue=catalog.Catalog(paths)), "4242")
    assert chosen["text"] == LABEL  # this is the live label she is shown

    spool = Spool(data / "spool.db")
    client = _Client([dict(ACT)])
    published = []
    courier = ActCourier(spool, lambda command, args: published.append((command, args)))
    try:
        assert courier.tick(client, "h", 1000, True) == [ACT["act_id"]]
        courier.on_row(_row("PUSHED", interaction_id="777"))
        courier.on_row(_row("FINISHED", interaction_id="777", finishing_type="FinishingType.NATURAL"))
        courier.tick(client, "h", 2000, True)
    finally:
        spool.close()

    assert published == [("act", {"act_id": ACT["act_id"], "object_id": "11", "guid64": "4242"})]
    sent = json.dumps(client.bodies)
    assert TUNING in sent, "the act path must have run and recorded the tuning name"
    assert LABEL not in sent, "the live label reached an act event/detail sent to Mint"

    spool = Spool(data / "spool.db")
    try:
        for key in ("acts_known", "acts_events", "acts_quarantined", "acts_asked"):
            assert LABEL not in (spool.get_kv(key) or ""), "the live label reached spool kv %s" % key
    finally:
        spool.close()

    files = _files(tmp_path)
    names = {path.name for path in files}
    assert {"spool.db", "catalog.db", notebook.DB_NAME} <= names, "the store fixtures must exist"
    for path in files:
        assert LABEL.encode("utf-8") not in path.read_bytes(), "the live label reached %s" % path
