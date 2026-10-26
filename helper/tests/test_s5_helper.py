"""S5 in the helper: what schema 7 rows add to her portrait, outcome records and scene."""
from domus_helper import outcomes, scene
from domus_helper.thalamus import observation
from test_outcomes import AUTO, EAT, INTENT, PIE, GRAB, _row

TEXT = {"11": "Friends", "21": "Nauseous", "22": "From Eating Spoiled Food"}


def _v7(row, friendship=10.0, labels=(), objects=None):
    row = dict(row, schema_version=7)
    row["presence"] = [
        {"id": "1", "level": 0, "is_body": True, "name": "E1 Proband", "relationship": None},
        {"id": "2", "level": 0, "is_body": False, "name": "Bella Goth", "room": "3", "distance_m": 2.0,
         "doing": "<class 'sims4.tuning.instances.social_Chat'>",
         "relationship": {"known": True,
                          "tracks": [{"track": "LTR_Friendship_Main", "value": friendship}],
                          "labels": [{"label": l, "text_key": "11"} for l in labels]}}]
    row["objects"] = objects if objects is not None else {
        "baseline": False, "created": [], "destroyed": [], "changed": [], "truncated": False}
    return row


def test_portrait_shows_reason_time_left_and_relationship_in_game_words():
    row = _v7(_row(0, 600, []), friendship=35.2, labels=["RelBit_Friends"])
    row["sim_signals"] = [{"kind": "MOODLET", "tuning_id": "5", "tuning_name": "Buff_Nauseous",
                           "text_key": "21", "magnitude": "w:2", "mood_type": "Mood_Uncomfortable",
                           "visible": True, "reason_key": "22", "minutes_left": 90.0}]
    portrait = observation._portrait(row, TEXT.get)
    assert portrait["moodlets"][0]["text"] == "Nauseous"
    assert portrait["moodlets"][0]["reason"] == "From Eating Spoiled Food"
    assert portrait["moodlets"][0]["minutes_left"] == 90.0
    bella = portrait["company"][0]
    assert bella["relationship"] == {"met": True, "tracks": {"LTR_Friendship_Main": 35.2},
                                     "labels": ["Friends"]}
    assert bella["doing"] == "social_Chat"


def test_an_act_carries_its_relationship_change_and_object_events():
    chat = "social_Chat"
    spoiled = {"baseline": False, "created": [], "destroyed": [], "truncated": False,
               "changed": [{"object_id": "9", "class": "object_Food", "state": "Freshness",
                            "from": "Freshness_Fresh", "to": "Freshness_Spoiled"}]}
    rows = [_v7(_row(0, 600, []), friendship=10.0),
            _v7(_row(1, 602, [(30, 7, chat, PIE)]), friendship=10.0),
            _v7(_row(2, 610, [(30, 7, chat, PIE)]), friendship=14.0, objects=spoiled),
            _v7(_row(3, 615, []), friendship=16.5, labels=["RelBit_Friends"])]
    record = outcomes.acts(rows, "s")[0]
    # The fixture's chat has no target, so Bella reads as a bystander here.
    assert record["relationships"] == [{"with": "Bella Goth", "role": "bystander",
                                        "tracks": {"LTR_Friendship_Main": 6.5},
                                        "labels_gained": ["RelBit_Friends"], "labels_lost": []}]
    assert record["objects"]["changed"][0]["to"] == "Freshness_Spoiled"
    assert record["unknown"] == ["self"]


def test_a_new_baseline_inside_an_act_makes_objects_unknown():
    rows = [_v7(_row(0, 600, [])),
            _v7(_row(1, 602, [(30, 7, "social_Chat", PIE)])),
            _v7(_row(2, 610, [(30, 7, "social_Chat", PIE)]),
                objects={"baseline": True, "created": [], "destroyed": [], "changed": [],
                         "truncated": False}),
            _v7(_row(3, 615, []))]
    record = outcomes.acts(rows, "s")[0]
    assert record["objects"] is None and record["unknown"] == ["objects", "self"]


def test_schema_6_rows_stay_unknown():
    record = outcomes.acts([_row(0, 600, []), _row(1, 602, [(1, 1, EAT, INTENT)]),
                            _row(2, 610, [])], "s")[0]
    assert record["unknown"] == ["objects", "relationships", "self"]
    assert AUTO and GRAB


def test_scene_shows_who_holds_it_and_how_fast_it_spoils():
    body = {"room": "3", "position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}}
    plate = {"kind": "object", "object_id": "1", "class": "object_Food_PlateFork_Multi",
             "room": "3", "position": {"x": 1.0, "y": 0.0, "z": 0.0, "level": 0},
             "states": {"Freshness": "Freshness_Fresh"}, "stats": {}, "craft": None,
             "in_use": True, "used_by": ["100"], "rates": {"commodity_freshness": -0.1}}
    fact = scene.layers({"body": body}, [plate])["near"][0]
    assert fact["in_use_by"] == ["100"] and fact["freshness_per_minute"] == -0.1
