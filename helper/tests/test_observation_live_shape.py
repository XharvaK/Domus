"""Live 2.13.1 (2026-10-05): the portrait showed the probe's raw class repr as an action."""
from domus_helper.thalamus import observation

REPR = "<class 'sims4.tuning.instances.sim-stand'>"


def test_actions_read_as_tuning_names():
    row = {
        "interactions": {"observed": [{"affordance_text": REPR, "membership": "RUNNING"}]},
        "presence": [{"id": "1", "level": 0, "is_body": True, "doing": REPR},
                     {"id": "2", "level": 0, "name": "Bella", "room": "3", "distance_m": 2.0,
                      "doing": "<class 'sims4.tuning.instances.social_Chat'>"}],
        "social": [{"actor_id": "2", "affordance_text": "<class 'sims4.tuning.instances.social_Chat'>"}],
        "game": {"calendar": "02:31:21.960 day:2 week:0"},
    }
    portrait = observation._portrait(row)
    assert portrait["running"] == []  # HE2: standing is not an act; her posture says it
    assert portrait["company"][0]["doing"] == "social_Chat"
    assert portrait["addressed_by"] == [{"by": "2", "interaction": "social_Chat"}]
    assert portrait["time"]["weekday"] == "Tuesday" and portrait["time"]["hour"] == 2


def test_plain_text_passes_through():
    assert observation._affordance_name("generic_food_Grab") == "generic_food_Grab"
    assert observation._affordance_name(None) is None
