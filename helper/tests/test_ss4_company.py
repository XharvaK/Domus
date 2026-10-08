"""SS4-v2: she names a Sim she can see. Everyone else on the lot is someone she hears.

Seen: indoors (her body in a real room), the same room and the same level; outdoors (her room None or "0"),
within 4 m on the same level. Addressing her does not make a Sim seen. Heard Sims carry a keyed handle."""
from domus_helper import lang
from domus_helper.scene import seen_here
from domus_helper.thalamus import observation


def _body():
    return {"id": "1", "is_body": True, "name": "Ada", "room": "hall", "level": 0}


def _sim(sim_id, name, room, distance, on_lot=True, level=0, **extra):
    item = {"id": sim_id, "is_body": False, "name": name, "room": room, "level": level,
            "distance_m": distance, "on_lot": on_lot,
            "doing": "invented_wave",
            "situations": [{"situation": "situation_Visit", "role": "Guest"}],
            "relationship": {"known": True, "tracks": [{"track": "LTR_Friendship_Main", "value": 10}],
                             "labels": []}}
    item.update(extra)
    return item


def _portrait(people, social=None, running=None):
    row = {"zone": {"room": "hall"}, "presence": [_body(), *people]}
    if social is not None:
        row["social"] = social
    if running is not None:
        row["interactions"] = {"observed": running}
    return observation._portrait(row)


class _Book:
    def sentence(self, tuning, actors):
        return "%s:%s" % (tuning, " ".join(actors))


def test_the_seen_rule_is_the_same_room_and_level_indoors_and_four_metres_outdoors():
    body = _body()
    assert seen_here(_sim("2", "A", "hall", 1.0), body) is True
    assert seen_here(_sim("3", "B", "yard", 1.0), body) is False          # another room, through a wall
    assert seen_here(_sim("4", "C", "hall", 1.0, level=1), body) is False  # same room, other level
    assert seen_here(_sim("5", "D", None, 1.0), body) is False            # no room: not in her room
    outdoors = {"room": "0", "level": 0}
    assert seen_here(_sim("6", "E", "0", 4.0), outdoors) is True
    assert seen_here(_sim("7", "F", "0", 4.1), outdoors) is False
    assert seen_here(_sim("8", "G", "3", 2.0), outdoors) is True          # outdoors: distance alone decides
    assert seen_here(_sim("9", "H", "0", 2.0, level=None), outdoors) is False  # level unknown: heard
    assert seen_here(_sim("10", "I", "0", True), outdoors) is False       # a bool distance is not a distance


def test_same_room_is_a_full_entry_and_a_far_room_is_only_heard():
    portrait = _portrait([
        _sim("2", "Testa Zubrin", "hall", 12.0),
        _sim("3", "Quin Lorne", "yard", 12.0),
    ])
    testa, quin = portrait["company"]
    assert testa["id"] == "2" and testa["name"] == "Testa Zubrin"
    assert testa["doing"] == "invented_wave"
    assert testa["relationship"]["met"] is True
    assert testa["situations"] == [{"situation": "situation_Visit", "role": "Guest"}]
    assert set(quin) == {"heard", "handle", "room", "distance_m", "on_lot"}
    assert quin["heard"] is True and quin["room"] == "yard" and quin["distance_m"] == 12.0
    assert "id" not in quin and "name" not in quin and "doing" not in quin
    assert "relationship" not in quin and "situations" not in quin


def test_a_sim_through_the_wall_within_four_metres_is_heard_and_addressing_does_not_make_her_seen():
    portrait = _portrait([
        _sim("2", "Testa Zubrin", "yard", 4.0),
        _sim("3", "Quin Lorne", "hall", 4.0, level=1),
        _sim("4", "Nia Pell", "yard", 30.0),
        _sim("5", "Bo Linn", "street", 30.0, on_lot=False),
    ], social=[{"actor_id": "4", "affordance_text": "invented_wave"}])
    assert [item.get("name") for item in portrait["company"] if "name" in item] == []
    heard = [item for item in portrait["company"] if item.get("heard")]
    assert [(item["room"], item["distance_m"]) for item in heard] == [("yard", 4.0), ("hall", 4.0),
                                                                     ("yard", 30.0)]
    assert all(item.get("name") != "Bo Linn" and item.get("id") != "5" for item in portrait["company"])
    assert all(item.get("name") != "Nia Pell" for item in portrait["company"])


def test_outdoors_her_seen_rule_is_four_metres_on_the_same_level():
    row = {"zone": {"room": "0"}, "presence": [
        {"id": "1", "is_body": True, "name": "Ada", "room": "0", "level": 0},
        _sim("2", "Testa Zubrin", "0", 4.0),
        _sim("3", "Quin Lorne", "0", 4.1),
    ]}
    portrait = observation._portrait(row)
    assert [item["name"] for item in portrait["company"] if "name" in item] == ["Testa Zubrin"]
    assert [item["distance_m"] for item in portrait["company"] if item.get("heard")] == [4.1]


def test_an_unknown_lot_flag_is_still_heard_and_keeps_on_lot_only_when_known():
    portrait = _portrait([
        {"id": "2", "is_body": False, "name": "Testa Zubrin", "room": "yard", "level": 0,
         "distance_m": 9.0},
    ])
    company = portrait["company"]
    assert len(company) == 1 and company[0]["heard"] is True
    assert company[0]["room"] == "yard" and company[0]["distance_m"] == 9.0
    assert "on_lot" not in company[0] and "id" not in company[0]


def test_seen_keep_row_order_then_heard_are_nearest_first_and_the_cap_is_seven():
    people = [
        _sim("2", "Cara Lind", "hall", 20.0),
        _sim("3", "Quin Lorne", "hall", 1.0),
        _sim("4", "Far One", "yard", 11.0),
        _sim("5", "Far Two", "yard", 8.0),
        _sim("6", "Far Three", "yard", 9.0),
    ]
    company = _portrait(people)["company"]
    assert [item.get("name") for item in company[:2]] == ["Cara Lind", "Quin Lorne"]
    assert [item["distance_m"] for item in company[2:]] == [8.0, 9.0, 11.0]
    crowded = [_sim(str(index), "Seen %d" % index, "hall", 30.0) for index in range(2, 10)]
    crowded += [_sim("40", "Near Heard", "yard", 0.5)]
    capped = _portrait(crowded)["company"]
    assert len(capped) == 7
    assert all("name" in item for item in capped)
    assert all(not item.get("heard") for item in capped)


def test_a_heard_sims_running_social_says_someone(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    row = {"zone": {"room": "hall"}, "presence": [
        _body(),
        _sim("9", "Testa Zubrin", "yard", 12.0),
    ], "interactions": {"observed": [{
        "affordance_text": "invented_wave", "membership": "RUNNING", "target_id": "9"}]}}
    portrait = observation._portrait(row)
    assert portrait["doing_said"] == [{
        "interaction": "invented_wave", "sentence": "invented_wave:Ada someone", "state": "running"}]
    assert "Testa" not in portrait["doing_said"][0]["sentence"]
    addressed = observation._portrait({
        "zone": {"room": "hall"},
        "presence": [_body(), _sim("4", "Nia Pell", "yard", 30.0)],
        "social": [{"actor_id": "4", "affordance_text": "invented_wave"}],
    })
    assert addressed["addressed_by"][0]["sentence"] == "invented_wave:someone Ada"


def test_a_handle_is_stable_per_sim_never_the_id_and_distinct_between_strangers():
    memory = observation.SeenMemory(b"install-key-for-tests")
    row = {"presence": [_body(), _sim("9", "Testa Zubrin", "yard", 12.0),
                        _sim("10", "Quin Lorne", "yard", 12.0)]}
    memory.observe(row)
    handles = [item["handle"] for item in observation._portrait(row, seen=memory)["company"]]
    assert len(set(handles)) == 2 and all(handle != "9" and handle != "10" for handle in handles)
    memory.observe(row)
    again = [item["handle"] for item in observation._portrait(row, seen=memory)["company"]]
    assert handles == again
    assert observation.SeenMemory(b"another-install").handle("9") != memory.handle("9")
    assert "'id': '9'" not in str(observation._portrait(row, seen=memory)["company"])


def test_a_stranger_who_leaves_and_one_who_arrives_are_different_handles():
    memory = observation.SeenMemory(b"install-key-for-tests")
    before = {"presence": [_body(), _sim("9", "Testa Zubrin", "yard", 12.0)]}
    memory.observe(before)
    left = observation._portrait(before, seen=memory)["company"][0]["handle"]
    after = {"presence": [_body(), _sim("11", "Bo Linn", "yard", 12.0)]}
    memory.observe(after)
    arrived = observation._portrait(after, seen=memory)["company"][0]["handle"]
    assert left != arrived


def test_one_sample_of_flicker_does_not_flip_a_seen_state_and_two_samples_do():
    memory = observation.SeenMemory(b"install-key-for-tests")
    room_hall = {"presence": [_body(), _sim("2", "Testa Zubrin", "hall", 1.0)]}
    room_yard = {"presence": [_body(), _sim("2", "Testa Zubrin", "yard", 1.0)]}
    assert memory.observe(room_hall) == {"2"}
    assert memory.observe(room_yard) == {"2"}      # one sample apart: still seen
    assert memory.observe(room_hall) == {"2"}
    assert memory.observe(room_yard) == {"2"}
    assert memory.observe(room_yard) == set()      # a second sample in a row: heard
    assert memory.observe(room_yard) == set()


def test_the_act_menu_and_outcomes_name_only_seen_sims():
    from domus_helper import acts
    from domus_helper import outcomes
    row = {"presence": [_body(), _sim("2", "Testa Zubrin", "hall", 1.0),
                        _sim("3", "Quin Lorne", "yard", 1.0)]}
    assert acts.people_names(row, {"2"}) == {"1": "Ada", "2": "Testa Zubrin"}
    assert acts.people_names(row) == {"1": "Ada", "2": "Testa Zubrin", "3": "Quin Lorne"}
    assert outcomes.company_names(row) == ["Testa Zubrin"]


def test_shedding_drops_heard_before_a_sim_she_can_see():
    heard = [_sim(str(10 + index), "Far %d" % index, "yard", 10.0 + index) for index in range(4)]
    seen = _sim("2", "Testa Zubrin", "hall", 1.0)
    seen["relationship"] = {"known": True, "tracks": [], "labels": [{"label": ""}]}
    slim = _portrait([seen, *heard])
    room = observation._PORTRAIT_LIMIT - observation._bytes(slim)
    assert room > 0
    seen["relationship"]["labels"][0]["label"] = "L" * (room + 1)
    portrait = _portrait([seen, *heard])
    assert observation._bytes(portrait) <= observation._PORTRAIT_LIMIT
    assert [item.get("name") for item in portrait["company"] if "name" in item] == ["Testa Zubrin"]
    heard_left = [item["distance_m"] for item in portrait["company"] if item.get("heard")]
    assert heard_left == [10.0, 11.0, 12.0]


def test_household_here_names_only_the_members_she_sees():
    row = {"zone": {"room": "hall"}, "place": {"owner_household_id": "h1", "her_home": False},
           "presence": [_body(),
                        _sim("2", "Testa Zubrin", "hall", 12.0, household_id="h1"),
                        _sim("3", "Quin Lorne", "attic", 12.0, household_id="h1"),
                        _sim("4", "Mor Vell", "attic", 12.0, household_id="h2")]}
    place = observation._portrait(row)["place"]
    assert place["household_here"] == ["Testa Zubrin"]
    assert place["household_heard"] == 1
    assert "Quin Lorne" not in str(observation._portrait(row))
