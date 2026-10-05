"""2.15.0 in the helper, from the 2026-10-05 live session: socials are acts with their
own origin, bystanders are told apart from the Sim an act was aimed at, an act carries
what it did to her (skills, money) and what she learned, and the portrait shows it."""
from domus_helper import consequences, outcomes
from domus_helper.thalamus import observation
from test_outcomes import AUTO, PIE, _row

CHAT = "sim_Chat"
PROPERTY = "mixer_social_ChatAboutPropertyVaules_targeted_friendly_alwaysOn_neighbor"
FLIRT = "mixer_social_Flirt_targeted_romance_alwaysOn"
TEXT = {"31": "Cheerful", "41": "Close", "51": "Charisma", "61": "Loner"}


def _v8(index, minute, running, summer=10.0, travis=-12.6, funds=18000, charisma=2,
        learned=(), queued=()):
    row = _row(index, minute, running)
    row["schema_version"] = 8
    for entry in row["interactions"]["observed"]:
        if entry["interaction_id"] != "1":
            entry["target_id"] = "2"
    for iid, name, source in queued:
        row["interactions"]["observed"].append({
            "interaction_id": str(iid), "affordance_id": "9",
            "affordance_text": "<class 'sims4.tuning.instances.%s'>" % name,
            "source_raw": source, "membership": "QUEUED", "target_id": "2"})

    def rel(value, traits=()):
        return {"known": True, "tracks": [{"track": "LTR_Friendship_Main", "value": value}],
                "labels": [],
                "knows": {"traits": [{"trait": t, "text_key": "31"} for t in traits],
                          "careers": None, "relationship_status": False,
                          "romantic_preference": False, "net_worth": None},
                "sentiments": []}
    row["presence"] = [
        {"id": "1", "is_body": True, "name": "E1 Proband", "relationship": None, "on_lot": True},
        {"id": "2", "is_body": False, "name": "Summer Holiday", "on_lot": True,
         "relationship": rel(summer, learned)},
        {"id": "3", "is_body": False, "name": "Travis Scott", "on_lot": True,
         "relationship": rel(travis)}]
    row["objects"] = {"baseline": False, "created": [], "destroyed": [], "changed": [],
                      "truncated": False}
    row["self"] = {"traits": [{"trait": "trait_Cheerful", "text_key": "31", "personality": True}],
                   "skills": [{"skill": "statistic_Skill_AdultMajor_Charisma",
                               "text_key": "51", "level": charisma}],
                   "funds": funds}
    return row


def _session():
    return [_v8(0, 600, []),
            _v8(1, 602, [(30, 13998, CHAT, AUTO)]),
            _v8(2, 604, [(30, 13998, CHAT, AUTO)], queued=[(31, PROPERTY, PIE)]),
            _v8(3, 606, [(30, 13998, CHAT, AUTO)], summer=17.0, travis=-12.5,
                learned=["trait_Cheerful"], queued=[(32, FLIRT, AUTO)]),
            _v8(4, 610, [(30, 13998, CHAT, AUTO)], summer=21.0, travis=-12.5, charisma=3,
                learned=["trait_Cheerful"], funds=17950),
            _v8(5, 612, [], summer=21.0, travis=-12.4, charisma=3,
                learned=["trait_Cheerful"], funds=17950)]


def _by_name(records):
    return {record["interaction"]["name"]: record for record in records}


def test_socials_are_acts_with_their_own_origin_inside_the_chat():
    records = _by_name(outcomes.acts(_session(), "s"))
    chat, mine, hers = records[CHAT], records[PROPERTY], records[FLIRT]
    assert chat["origin"] == "body"
    assert mine["origin"] == "owner" and mine["social"] is True
    assert hers["origin"] == "body"
    assert mine["part_of"] == chat["act_id"] and hers["part_of"] == chat["act_id"]
    assert [(s["name"], s["origin"]) for s in chat["socials"]] == [
        (PROPERTY, "owner"), (FLIRT, "body")]
    # Its own socials are not counted as acts that followed it.
    assert all(item["name"] not in (PROPERTY, FLIRT) for item in chat["followed_by"])


def test_the_target_is_told_apart_from_a_bystander():
    chat = _by_name(outcomes.acts(_session(), "s"))[CHAT]
    by = {change["with"]: change for change in chat["relationships"]}
    assert by["Summer Holiday"]["role"] == "target"
    assert by["Summer Holiday"]["tracks"] == {"LTR_Friendship_Main": 11.0}
    assert by["Summer Holiday"]["learned_traits"] == ["trait_Cheerful"]
    assert by["Travis Scott"]["role"] == "bystander"


def test_the_act_carries_what_it_did_to_her():
    chat = _by_name(outcomes.acts(_session(), "s"))[CHAT]
    assert chat["self"] == {"funds": -50,
                            "skills": {"statistic_Skill_AdultMajor_Charisma": 1}}
    assert chat["unknown"] == []


def test_consequences_count_only_the_target():
    records = outcomes.acts(_session(), "s")
    effects = [line["effect"] for line in consequences.observed(records, CHAT)]
    relationship = [e for e in effects if e["type"] == "RELATIONSHIP"]
    assert relationship == [{"type": "RELATIONSHIP", "role": "target", "track": "LTR_Friendship_Main",
                             "change_median": 11.0, "seen_in": 1}]
    assert {"type": "SKILL", "skill": "statistic_Skill_AdultMajor_Charisma", "levels": 1,
            "seen_in": 1} in effects
    assert {"type": "FUNDS", "change_median": -50, "seen_in": 1} in effects


def test_portrait_shows_what_she_knows_feels_and_is():
    row = _v8(3, 606, [], learned=["trait_Cheerful"])
    row["presence"][1]["relationship"]["sentiments"] = [{"sentiment": "Sentiment_Close",
                                                         "text_key": "41"}]
    row["missingness"] = {"presence": {"status": "MISSING", "detail": "skipped 1 Sims"}}
    portrait = observation._portrait(row, TEXT.get)
    summer = portrait["company"][0]
    assert summer["on_lot"] is True
    assert summer["relationship"]["knows"]["traits"] == ["Cheerful"]
    assert summer["relationship"]["feels"] == ["Close"]
    assert portrait["self"] == {"traits": ["Cheerful"],
                                "skills": [{"skill": "Charisma", "level": 2}],
                                "funds": 18000}
    assert portrait["company_complete"] is False


def test_a_full_skill_list_does_not_invent_new_skills():
    rows = _session()
    full = [{"skill": "s%02d" % i, "text_key": None, "level": 1} for i in range(12)]
    rows[0]["self"]["skills"] = full  # the sample before the chat began
    rows[5]["self"]["skills"] = full[1:] + [{"skill": "s99", "text_key": None, "level": 1}]
    chat = _by_name(outcomes.acts(rows, "s"))[CHAT]
    assert "skills_new" not in (chat["self"] or {})
