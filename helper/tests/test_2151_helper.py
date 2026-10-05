"""2.15.1 in the helper, from the 2026-10-05 trip: cooking on a host's stove is aimed at
the stove, yet the host reacted (reaction_Inappropriate, then a send-away) and their
friendship fell 12 points. The record names who reacted, the change with that Sim
counts as the act's consequence, and a bystander's drift still does not."""
from domus_helper import consequences, outcomes
from domus_helper.thalamus import observation
from test_215_helper import _v8
from test_outcomes import PIE

COOK = "stove_MakeFood_FryingPan_Staging_Basic"
SCOLD = "reaction_Inappropriate"
SEND_AWAY = "nonTouching_Reaction_InappropriateBehavior_SendAway"


def _doing(name):
    return "<class 'sims4.tuning.instances.%s'>" % name


def _cooking(index, minute, running, travis, summer, travis_doing="sim-stand"):
    row = _v8(index, minute, running, summer=summer, travis=travis)
    for entry in row["interactions"]["observed"]:
        if entry["interaction_id"] != "1":
            entry["target_id"] = "9861"  # the stove
    for item in row["presence"]:
        item["doing"] = _doing("sim-stand")
    row["presence"][2]["doing"] = _doing(travis_doing)
    return row


def _session():
    act = [(40, 13388, COOK, PIE)]
    return [_cooking(0, 600, [], 5.5, -2.7),
            _cooking(1, 602, act, 5.5, -2.7),
            _cooking(2, 604, act, 5.5, -2.7, travis_doing=SCOLD),
            _cooking(3, 606, act, -0.6, -2.6, travis_doing=SCOLD),
            _cooking(4, 608, [], -0.6, -2.6, travis_doing=SEND_AWAY)]


def _cook(records):
    return [record for record in records if record["interaction"]["name"] == COOK][0]


def test_the_record_names_who_reacted_and_how():
    cook = _cook(outcomes.acts(_session(), "s"))
    assert cook["reactions"] == [
        {"by": "Travis Scott", "reaction": SCOLD, "id": "3"},
        {"by": "Travis Scott", "reaction": SEND_AWAY, "id": "3"}]


def test_the_reactor_is_told_apart_from_a_bystander():
    cook = _cook(outcomes.acts(_session(), "s"))
    by = {change["with"]: change for change in cook["relationships"]}
    assert by["Travis Scott"]["role"] == "reactor"
    assert by["Travis Scott"]["tracks"] == {"LTR_Friendship_Main": -6.1}
    assert by["Summer Holiday"]["role"] == "bystander"


def test_consequences_carry_the_reaction_and_its_cost():
    effects = [line["effect"]
               for line in consequences.observed(outcomes.acts(_session(), "s"), COOK)]
    assert {"type": "REACTION", "reaction": SCOLD, "times": 1} in effects
    relationship = [e for e in effects if e["type"] == "RELATIONSHIP"]
    assert relationship == [{"type": "RELATIONSHIP", "role": "reactor",
                             "track": "LTR_Friendship_Main", "change_median": -6.1,
                             "seen_in": 1}]


def test_her_own_reaction_is_not_someone_reacting_to_her():
    rows = _session()
    rows[2]["presence"][0]["doing"] = _doing("reaction_SmellBad")
    cook = _cook(outcomes.acts(rows, "s"))
    assert [item["by"] for item in cook["reactions"]] == ["Travis Scott", "Travis Scott"]


def test_a_quiet_act_has_no_reactions():
    rows = _session()
    for row in rows:
        row["presence"][2]["doing"] = _doing("sim-stand")
    assert _cook(outcomes.acts(rows, "s"))["reactions"] == []


def test_a_reaction_queued_on_her_is_an_act_that_followed():
    rows = _session()
    rows[4]["interactions"]["observed"].append({
        "interaction_id": "43", "affordance_id": "129635",
        "affordance_text": _doing(SEND_AWAY), "source_raw": "InteractionSource.SCRIPT",
        "membership": "QUEUED", "target_id": "1"})
    records = outcomes.acts(rows, "s")
    sent = [r for r in records if r["interaction"]["name"] == SEND_AWAY][0]
    assert sent["origin"] == "game_reaction"
    assert [item["name"] for item in _cook(records)["followed_by"]] == [SEND_AWAY]


def test_portrait_says_more_are_nearby_and_the_lot_is_whole():
    row = _cooking(0, 600, [], 5.5, -2.7)
    row["missingness"] = {"presence_nearby": {"status": "MISSING",
                                              "detail": "3 off the lot not listed"}}
    portrait = observation._portrait(row, None)
    assert portrait["more_nearby"] is True
    assert "company_complete" not in portrait
