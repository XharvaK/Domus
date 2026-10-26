"""S3: declared (atlas ads, labelled advertised) and observed (outcome records with n,
conditions and provenance), never mixed."""
import json
import sqlite3

from domus_helper import consequences, outcomes
from test_outcomes import AUTO, EAT, GRAB, INTENT, PIE, _meal, _row

ADS = [{"stat": 16656, "name": "motive_Hunger",
        "ops": [{"op": "StatisticChangeOp", "amount": 3.5, "advertise": True},
                {"op": "StatisticChangeOp", "amount": 3.5, "advertise": True}]},
       {"stat": 1, "name": "commodity_Hidden", "ops": [{"amount": 9.0, "advertise": False}]}]


def _atlas():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE affordances (build TEXT, guid64 INTEGER, name TEXT, "
                       "autonomy_ads_json TEXT)")
    connection.execute("INSERT INTO affordances VALUES ('1.128', 13435, ?, ?)",
                       (GRAB, json.dumps(ADS)))
    return connection


def test_declared_is_advertised_not_a_rate():
    lines = consequences.declared(_atlas(), name=GRAB)
    assert [(l["kind"], l["effect"]) for l in lines] == [
        ("DECLARED", {"type": "NEED", "stat": "motive_Hunger", "advertised": [3.5]})]
    assert lines[0]["provenance"] == {"atlas_build": "1.128"}


def test_grab_is_followed_by_eating_and_does_not_claim_the_meal():
    records = outcomes.acts(_meal(), "abcdef12")
    lines = consequences.observed(records, GRAB)
    effects = [l["effect"] for l in lines]
    assert {"type": "FOLLOWED_BY", "interaction": EAT, "by": "owner",
            "within_game_minutes": 15, "times": 1} in effects
    assert not [e for e in effects if e["type"] == "NEED"]  # the meal is eating's
    assert all(l["n"] == 1 and l["provenance"]["act_ids"] for l in lines)


def test_a_cook_that_ends_at_serving_says_nothing_followed():
    cook = "stove_MakeFood_Pot_Staging_Basic"
    rows = [_row(0, 600, []), _row(1, 605, [(20, 5, cook, AUTO)]),
            _row(2, 610, [(20, 5, cook, AUTO)]), _row(3, 612, [(21, 1, "sim-stand", AUTO)]),
            _row(4, 640, [])]
    records = outcomes.acts(rows, "s")
    assert [r["interaction"]["name"] for r in records] == [cook]  # standing is not an act
    effects = [l["effect"] for l in consequences.observed(records, cook)]
    assert {"type": "NOTHING_FOLLOWED", "within_game_minutes": 15, "times": 1} in effects


def test_groups_by_origin_and_never_mixes_sources():
    records = (outcomes.acts(_meal(PIE), "aaaa") + outcomes.acts(_meal(experiment=True), "bbbb"))
    result = consequences.for_interaction(GRAB, records, _atlas())
    origins = sorted({l["conditions"]["origin"] for l in result["observed"]})
    assert origins == ["experiment", "owner"]
    assert all(l["kind"] == "DECLARED" for l in result["declared"])
    assert all(l["kind"] == "OBSERVED" for l in result["observed"])
    assert {"type": "UNKNOWN", "what": ["objects", "relationships", "self"]} in [
        l["effect"] for l in result["observed"]]


def test_eating_owns_its_hunger_change():
    records = outcomes.acts(_meal(), "abcdef12")
    effects = [l["effect"] for l in consequences.observed(records, EAT)]
    assert {"type": "NEED", "stat": "hunger", "change_median": 40, "seen_in": 1} in effects
    assert INTENT  # continuation source exercised via _meal
