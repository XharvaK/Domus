"""H3 (D2): a look is owed when the acts sync answer says `look: true`, once; its percept kind is `look`."""
from domus_helper.acts import ActCourier
from domus_helper.contract import validate_observation as check
from domus_helper.spool import Spool
from domus_helper.thalamus import observation
from domus_helper.thalamus.types import Percept


class _Answer:
    def __init__(self, answer):
        self.answer = answer

    def sync_acts(self, body):
        return dict(self.answer)


def test_the_sync_answer_hands_a_look_over_once(tmp_path):
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None)
    assert courier.take_look() is False
    courier.tick(_Answer({"status": "ok", "applied": 0, "acts": [], "look": True}), "h", 1_000, True)
    assert courier.take_look() is True
    assert courier.take_look() is False
    courier.tick(_Answer({"status": "ok", "applied": 0, "acts": [], "look": True}), "h", 2_000, True)
    courier.tick(_Answer({"status": "ok", "applied": 0, "acts": [], "look": "yes"}), "h", 3_000, True)
    assert courier.take_look() is True
    courier.tick(_Answer({"status": "ok", "applied": 0, "acts": []}), "h", 4_000, True)
    assert courier.take_look() is False


def test_a_look_percept_builds_a_valid_view_with_its_bucket_asked(tmp_path):
    look = Percept("look", "self", "", "asked")
    assert look.key == "look:self::asked"
    row = {
        "written_sequence": 3, "wall_timestamp_ms": 5_000, "telemetry_session_id": "sess-1",
        "body": {"sim_id": "ASH", "posture": {"posture_name": "stand"}},
        "game": {"clock_speed": "NORMAL", "paused": False}, "zone": {"zone_id": 7, "lot_id": 9},
        "motives": [{"id": "hunger", "value": 40, "band": "ok"}],
    }
    decision_percepts = ((look, 0.0),)
    from types import SimpleNamespace
    obs = observation.build(SimpleNamespace(percepts=decision_percepts), {
        "helper_session": "a" * 32, "obs_seq": 0, "slot_id": 3, "guid": "abc",
        "lineage_class": "load", "row": row,
    })
    normalized = check(obs, 5_000)
    assert [item["kind"] for item in normalized["percepts"]] == ["look"]
    assert normalized["percepts"][0]["facts"]["bucket"] == "asked"
    assert normalized["percepts"][0]["salience"] == 0.0
