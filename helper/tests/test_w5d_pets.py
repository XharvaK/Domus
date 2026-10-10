"""2.32.0 (PR13): a pet or an occult form is flagged in the company list she sees, with its species and its
occult kinds when the game gave them. A heard Sim is not described at all (no species, no occult kind)."""
from domus_helper.thalamus import observation
from domus_helper.vendor import schema


def _body():
    return {"id": "1", "is_body": True, "name": "Ada", "room": "hall", "level": 0}


def _sim(**extra):
    item = {"id": "2", "is_body": False, "name": "Biscuit", "room": "hall", "level": 0,
            "distance_m": 1.0, "on_lot": True, "is_pet": True, "species": "DOG", "occult_kinds": []}
    item.update(extra)
    return item


def _company(item):
    row = {"zone": {"room": "hall"}, "presence": [_body(), item]}
    return observation._portrait(row)["company"]


def test_a_pet_she_sees_is_named_as_a_pet_with_its_species():
    entry = _company(_sim())[0]
    assert entry["name"] == "Biscuit" and entry["pet"] is True and entry["species"] == "DOG"
    assert "occult" not in entry


def test_an_ordinary_sim_carries_no_pet_or_occult_keys():
    entry = _company(_sim(is_pet=False, species="HUMAN", occult_kinds=None))[0]
    assert "pet" not in entry and "species" not in entry and "occult" not in entry


def test_an_occult_form_she_sees_names_its_kinds():
    entry = _company(_sim(is_pet=False, species="HUMAN", occult_kinds=["VAMPIRE"]))[0]
    assert entry["occult"] == ["VAMPIRE"]


def test_a_heard_pet_is_only_a_sound():
    row = {"zone": {"room": "hall"}, "presence": [_body(), _sim(room="yard", distance_m=12.0)]}
    entry = observation._portrait(row)["company"][0]
    assert entry["heard"] is True
    assert "pet" not in entry and "species" not in entry and "name" not in entry


def test_the_vendored_schema_accepts_the_presence_fields_at_fifteen_and_rejects_bad_ones():
    item = {"id": "2", "active_household": False, "level": 0, "is_body": False, "household_id": None,
            "name": "Biscuit", "position": None, "room": "hall", "posture": None, "doing": None,
            "doing_target": None, "distance_m": 1.0, "relationship": None, "situations": None,
            "on_lot": True, "is_pet": True, "species": "DOG", "occult_kinds": ["WEREWOLF"]}
    schema._validate_presence([item], 15)
    for bad in ({"is_pet": "yes"}, {"occult_kinds": "WEREWOLF"}, {"species": "x" * 200}):
        try:
            schema._validate_presence([dict(item, **bad)], 15)
        except schema.SchemaError:
            continue
        raise AssertionError("accepted %r" % bad)
