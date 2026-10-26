"""2.32.0 (PR5, PR12): her life block reaches her portrait, and a BODY_GONE lineage record carries its reason as a fact
of the lineage percept (and its lineage class is not admissible, so her acts are not admitted meanwhile)."""
from domus_helper.thalamus import observation
from domus_helper.thalamus.percepts import Extractor
from domus_helper.vendor import schema


def _life(**changes):
    life = {"age": "ADULT", "pregnant": False, "sick": False, "dead": False, "ghost": False, "npc": False}
    life.update(changes)
    return life


def _self(life):
    return {"traits": None, "skills": None, "funds": None, "careers": None, "wants": None, "life": life}


def test_the_life_block_is_in_her_portrait_self():
    row = {"presence": [{"id": "1", "is_body": True, "name": "Ada", "room": "hall", "level": 0}],
           "self": _self(_life(pregnant=True, sick=None))}
    life = observation._portrait(row)["self"]["life"]
    assert life == {"age": "ADULT", "pregnant": True, "sick": None, "dead": False, "ghost": False, "npc": False}


def test_an_unreadable_life_block_is_still_a_block_of_nulls_not_absent():
    row = {"presence": [], "self": _self({"age": None, "pregnant": None, "sick": None,
                                           "dead": None, "ghost": None, "npc": None})}
    assert observation._portrait(row)["self"]["life"]["age"] is None


def test_a_body_gone_record_carries_its_reason_on_the_lineage_percept():
    extractor = Extractor()
    percept = extractor._lineage({"e2": {"record": "BODY_GONE", "slot_id": "2", "guid": "g",
                                         "lineage_class": "BODY_GONE", "reason": "DEAD"}})
    assert percept.kind == "lineage"
    assert percept.bucket == "BODY_GONE"  # the lineage class rides in the bucket (as before)
    assert dict(percept.facts) == {"reason": "DEAD"}
    assert extractor.lineage_class == "BODY_GONE"


def test_a_lineage_record_without_a_reason_has_no_reason_fact():
    extractor = Extractor()
    percept = extractor._lineage({"e2": {"record": "CLASSIFIED", "slot_id": "2", "guid": "g",
                                         "lineage_class": "CONTINUES_LAST_SAVE"}})
    assert percept.facts == ()


def test_the_vendored_schema_is_fifteen_and_names_the_body_gone_record():
    assert schema.OBSERVATION_SCHEMA_VERSION == 21
    assert "BODY_GONE" in schema.LINEAGE_RECORDS
    assert "reason" in schema.E2_PAYLOAD_KEYS["lineage_event"]
