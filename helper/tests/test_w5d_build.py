"""2.32.0 (PR10, PR11): build mode is its own portrait state (not "paused"), and a fire on the lot is a fact."""
from domus_helper.thalamus import observation


def _row(game):
    return {"zone": {"room": "hall"}, "presence": [{"id": "1", "is_body": True, "name": "Ada", "room": "hall",
                                                  "level": 0}], "game": game}


def test_build_mode_is_a_state_and_the_clock_held_for_it_is_not_a_pause():
    portrait = observation._portrait(_row({"paused": True, "build_mode": True, "fire": False}))
    assert portrait["building"] is True
    assert portrait["paused"] is False
    assert "fire_on_lot" not in portrait


def test_a_user_pause_outside_build_mode_is_still_a_pause():
    portrait = observation._portrait(_row({"paused": True, "build_mode": False}))
    assert portrait["paused"] is True
    assert "building" not in portrait


def test_a_fire_on_the_lot_is_a_fact_and_unreadable_game_flags_say_nothing():
    assert observation._portrait(_row({"paused": False, "fire": True}))["fire_on_lot"] is True
    quiet = observation._portrait(_row({"paused": False, "build_mode": None, "fire": None}))
    assert "fire_on_lot" not in quiet and "building" not in quiet
