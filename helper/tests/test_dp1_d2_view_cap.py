"""D2 (Domus perception 1): the view cap keeps what a felt need requires.

Forty invented objects (two toilets in two rooms, the rest bookshelves) with the bladder worst keep both toilets
through the helper's object and byte caps, including the halving _fit_options does for a view too large for the wire.
Both option objects say "serves": ["bladder"], and the cut still counts what was left out.

Names, ids and rooms are invented; no game text or real id appears here."""
import json
from types import SimpleNamespace

from domus_helper import bridge as bridge_module
from domus_helper.acts import felt_needs, options
from domus_helper.bridge import Bridge
from domus_helper.bridge import OPTIONS_LIMIT


def obj(object_id, distance, acts, room="1", klass=None, serves=None):
    item = {"object_id": object_id, "class": klass or "object_thing_%s" % object_id, "room": room,
            "distance_m": distance, "same_room": room == "1",
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts]}
    if serves is not None:
        item["serves"] = serves
    return item


def toilet(object_id, distance, guid, room, klass):
    item = obj(object_id, distance, [(guid, "toilet_Use")], room=room, klass=klass)
    item["acts"][0]["serves"] = ["bladder"]
    return item


def menu(*objects, room="1"):
    return {"room": room, "objects": list(objects)}


def forty():
    shelves = [obj(str(100 + index), 1.0 + index, [("6100", "thing_Read")], room="6")
               for index in range(38)]
    return shelves + [toilet("200", 39.0, "6101", "4", "object_toilet_blue"),
                      toilet("201", 40.0, "6102", "5", "object_toilet_green")]


def test_felt_needs_are_worst_first_and_unread_values_are_skipped():
    row = {"motives": [{"id": "hunger", "value": 72, "band": "ok"},
                       {"id": "bladder", "value": 8, "band": "distress"},
                       {"id": None, "value": 1, "band": "distress"},
                       {"id": "fun", "value": None, "band": "ok"},
                       {"id": "hygiene", "value": 30, "band": "low"}]}
    assert felt_needs(row) == ("bladder", "hygiene", "hunger")
    assert felt_needs({}) == ()
    assert felt_needs(None) == ()


def test_forty_objects_and_bladder_distress_keep_both_toilets_through_the_object_cap():
    cut = {}
    result = options(menu(*forty()), room="4", objects_limit=20, cut=cut, needs=("bladder", "hunger"))
    ids = [entry["object_id"] for entry in result]
    assert ids[:2] == ["200", "201"]
    by_id = {entry["object_id"]: entry for entry in result}
    assert by_id["200"]["serves"] == ["bladder"]
    assert by_id["201"]["serves"] == ["bladder"]
    assert cut["objects"] == 20
    assert cut["rooms"] == ["6"]


def test_forty_objects_and_bladder_distress_keep_both_toilets_through_the_byte_cap():
    cut = {}
    result = options(menu(*forty()), room="4", limit=800, cut=cut, needs=("bladder", "hunger"))
    ids = [entry["object_id"] for entry in result]
    assert "200" in ids and "201" in ids
    by_id = {entry["object_id"]: entry for entry in result}
    assert by_id["200"]["serves"] == ["bladder"]
    assert by_id["201"]["serves"] == ["bladder"]
    assert cut["objects"] == 40 - len(result) > 0
    assert cut["rooms"] == ["6"]


def test_serves_is_bounded_to_eight_ids_of_at_most_thirty_two_characters():
    item = obj("7", 1.0, [("7001", "thing_Read")])
    item["acts"][0]["serves"] = ["n%d" % index for index in range(6)] + ["x" * 33, "n7", "n8", "n9"]
    item["serves"] = ["x" * 33, "bladder"]
    [entry] = options(menu(item), room="1")
    assert entry["serves"] == ["n0", "n1", "n2", "n3", "n4", "n5", "n7", "n8"]


def test_fit_options_halving_the_budget_keeps_both_toilets_and_names_the_cut(monkeypatch):
    row = {"motives": [{"id": "hunger", "value": 72, "band": "ok"},
                       {"id": "bladder", "value": 8, "band": "distress"}]}
    lot = menu(*forty())

    def options_for(row, cut=None, limit=OPTIONS_LIMIT):
        return options(lot, room="4", cut=cut, limit=limit, needs=felt_needs(row))

    def build(_decision, ctx):
        return {"options": list(ctx.get("options") or []), "options_cut": dict(ctx.get("options_cut") or {})}

    fake = SimpleNamespace(_options=options_for)
    ctx = {"row": row, "options": options_for(row)}
    first = build(None, ctx)
    monkeypatch.setattr(bridge_module, "build", build)
    # A view just over the wire limit: _fit_options halves the options budget until it fits, cutting objects.
    monkeypatch.setattr(bridge_module, "OBSERVATION_BYTES",
                        len(json.dumps(first, separators=(",", ":")).encode("utf-8")) - 1)
    ctx, obs = Bridge._fit_options(fake, ctx, first, None)
    ids = [entry["object_id"] for entry in obs["options"]]
    assert ids[:2] == ["200", "201"]
    assert obs["options_cut"]["objects"] > 0
