"""D6 (H1, schema 18): her inner life reaches Thought as words. The portrait carries her aspiration, bills, what she
carries, the weather and the season; each game notice is a notice percept; a change to her self is a self percept
that names the one thing that changed. Synthetic rows, the game's words stood in by invented keys."""
import json

from domus_helper.thalamus import observation, parameters
from domus_helper.thalamus.percepts import Extractor
from domus_helper.thalamus.types import Percept

TEXT = {
    "91": "Cooking expert", "92": "Cook a meal", "93": "Serve a guest",
    "101": "Bills are due", "102": "The mail brought your bills.",
    "111": "Cooking", "112": "Dishwasher", "113": "Read a book", "114": "Piano",
}


def _resolve(key):
    return TEXT.get(key)


def _portrait_row(**fields):
    row = {"motives": []}
    row.update(fields)
    return row


def _row(seq, *, self_=None, notices=None, weather=None, kind="presence_snapshot"):
    row = {
        "event_kind": kind,
        "written_sequence": seq,
        "wall_timestamp_ms": 1_000_000 + seq * 1000,
        "monotonic_ns": (1_000_000 + seq * 1000) * 1_000_000,
        "telemetry_session_id": "sess",
        "game": {"ticks": 100 * seq, "clock_speed": "NORMAL", "paused": False},
        "body": {"sim_id": "ASH", "posture": {"posture_name": "stand", "target_id": "chair"}},
        "interactions": {"observed": []},
        "motives": [],
        "zone": {"zone_id": 1, "lot_id": 9, "room": None, "position": None},
    }
    if self_ is not None:
        row["self"] = self_
    if notices is not None:
        row["notices"] = notices
    if weather is not None:
        row["weather"] = weather
    return row


def _self(**fields):
    base = {"traits": [], "skills": [], "funds": None, "careers": None, "wants": None,
            "life": {"age": None, "pregnant": None, "sick": None, "dead": None, "ghost": None, "npc": None}}
    base.update(fields)
    return base


def _texts(percepts, kind):
    return [dict(p.facts)["text"] for p in percepts if p.kind == kind]


# ----------------------------------------------------------------- H1: the portrait carries the words

def test_the_portrait_carries_her_aspiration_in_words():
    row = _portrait_row(self={
        "traits": None, "skills": None, "funds": None, "life": None,
        "aspiration": {"name_key": "91", "objectives": [
            {"text_key": "92", "done": True}, {"text_key": "93", "done": False},
            {"text_key": None, "done": False}]}})
    portrait = observation._portrait(row, _resolve)
    assert portrait["self"]["aspiration"] == {"name": "Cooking expert", "objectives": [
        {"text": "Cook a meal", "done": True}, {"text": "Serve a guest", "done": False},
        {"text": None, "done": False}]}


def test_the_portrait_carries_bills_and_the_inventory_in_words():
    row = _portrait_row(self=_self(
        bills={"owed": 320, "delivered": True, "late": False},
        inventory=[{"name": "Pot_Invented", "count": 2}]))
    portrait = observation._portrait(row, _resolve)
    assert portrait["self"]["bills"] == {"owed": 320, "delivered": True, "late": False}
    assert portrait["self"]["inventory"] == [{"item": "Pot_Invented", "count": 2}]


def test_an_absent_sense_is_absent_from_the_portrait_not_empty():
    portrait = observation._portrait(_portrait_row(self=_self()), _resolve)
    for key in ("aspiration", "bills", "inventory"):
        assert key not in portrait["self"]
    assert "weather" not in portrait and "season" not in portrait


def test_the_portrait_carries_the_weather_and_the_season_at_the_top():
    portrait = observation._portrait(_portrait_row(weather={"types": ["Rain", "Cloudy"], "season": "Summer"}), _resolve)
    assert portrait["weather"] == ["Rain", "Cloudy"]
    assert portrait["season"] == "Summer"


def test_weather_with_no_types_or_season_keeps_only_what_is_known():
    portrait = observation._portrait(_portrait_row(weather={"types": None, "season": None}), _resolve)
    assert "weather" not in portrait
    assert portrait["season"] is None


def test_new_fields_shed_first_and_the_marker_names_them(monkeypatch):
    """Over the limit, the inner-life fields go before anything the existing shedding cuts (moodlets, company)."""
    base_row = _portrait_row(self=_self(), weather={"types": ["Rain"], "season": "Summer"})
    base = observation._portrait(base_row, _resolve)
    full_row = _portrait_row(
        self=_self(aspiration={"name_key": "91", "objectives": [{"text_key": "92", "done": True}]},
                   bills={"owed": 320, "delivered": True, "late": False},
                   inventory=[{"name": "Pot_%03d" % n, "count": n} for n in range(20)]),
        weather={"types": ["Rain"], "season": "Summer"})
    limit = observation._bytes(base) + 200  # room for the marker that names what was shed
    monkeypatch.setattr(observation, "_PORTRAIT_LIMIT", limit)
    portrait = observation._portrait(full_row, _resolve)
    assert observation._bytes(portrait) <= limit
    shed = {item["part"] for item in portrait["shed"]}
    assert shed <= {"inventory", "aspiration", "bills", "weather", "season"}
    assert "inventory" in shed
    assert "moodlets" not in shed and "company" not in shed


def test_a_portrait_that_fits_keeps_the_inner_life_and_has_no_marker():
    portrait = observation._portrait(_portrait_row(self=_self(bills={"owed": 0, "delivered": False, "late": False})), _resolve)
    assert "shed" not in portrait


# ----------------------------------------------------------------- P2 and H1: notices are percepts

def test_a_notice_is_a_notice_percept_with_its_words_once():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1))
    percepts = ext.step(_row(2, notices=[{"title_key": "101", "text_key": "102"}]))
    notices = [p for p in percepts if p.kind == "notice"]
    assert len(notices) == 1
    assert dict(notices[0].facts) == {"text": "The mail brought your bills.", "title": "Bills are due"}
    assert [p for p in ext.step(_row(3, notices=[])) if p.kind == "notice"] == []


def test_a_notice_without_a_title_has_only_its_text():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1))
    notice = [p for p in ext.step(_row(2, notices=[{"title_key": None, "text_key": "102"}]))
              if p.kind == "notice"][0]
    assert notice.facts == (("text", "The mail brought your bills."),)


def test_a_notice_whose_text_cannot_be_resolved_still_says_one_came():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1))
    notice = [p for p in ext.step(_row(2, notices=[{"title_key": None, "text_key": "999"}]))
              if p.kind == "notice"][0]
    assert dict(notice.facts)["text"] == "The game showed a notice."


def test_notice_and_self_kinds_are_in_the_vocabulary():
    assert "notice" in parameters.KINDS and "self" in parameters.KINDS
    Percept("notice", "", "1:2", "")  # accepted by the vocabulary
    Percept("self", "ASH", "skill:111", "")


# ----------------------------------------------------------------- H1: a change to her self is a percept

def test_a_skill_level_change_names_the_skill_and_both_levels():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1, self_=_self(skills=[{"skill": "Skill_Cooking", "text_key": "111", "level": 3}])))
    texts = _texts(ext.step(_row(2, self_=_self(skills=[{"skill": "Skill_Cooking", "text_key": "111", "level": 4}]))), "self")
    assert texts == ["Skill: Cooking 4 (was 3)."]


def test_a_new_want_is_named_once_and_an_unchanged_self_says_nothing():
    ext = Extractor(resolve=_resolve)
    wants = [{"want": "FakeWant_Book", "text_key": "113", "tip_key": None, "fear": False, "locked": False,
              "done": None, "of": None, "until": None}]
    ext.step(_row(1, self_=_self(wants=[])))
    assert _texts(ext.step(_row(2, self_=_self(wants=wants))), "self") == ["New want: Read a book."]
    assert _texts(ext.step(_row(3, self_=_self(wants=wants))), "self") == []


def test_a_new_fear_is_named_as_a_fear():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1, self_=_self(wants=[])))
    fear = [{"want": "FakeFear_Piano", "text_key": "114", "tip_key": None, "fear": True, "locked": False,
             "done": None, "of": None, "until": None}]
    assert _texts(ext.step(_row(2, self_=_self(wants=fear))), "self") == ["New fear: Piano."]


def test_a_job_change_and_money_change_are_one_percept_each():
    ext = Extractor(resolve=_resolve)
    before = _self(funds=1200, careers=[{"career": "career_Dishes", "text_key": None, "title_key": "112",
                                         "level": 3, "at_work": False}])
    after = _self(funds=1500, careers=[{"career": "career_Dishes", "text_key": None, "title_key": "112",
                                        "level": 4, "at_work": False}])
    ext.step(_row(1, self_=before))
    texts = _texts(ext.step(_row(2, self_=after)), "self")
    assert sorted(texts) == sorted(["Job: Dishwasher, level 4 (was 3).", "Money: §1,500 (was §1,200)."])


def test_a_first_sample_sets_the_baseline_and_names_nothing():
    ext = Extractor(resolve=_resolve)
    assert _texts(ext.step(_row(1, self_=_self(funds=1200))), "self") == []


def test_a_self_change_survives_a_restart_without_a_false_baseline():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1, self_=_self(funds=1200)))
    restored = Extractor.from_dict(json.loads(json.dumps(ext.to_dict())), resolve=_resolve)
    assert _texts(restored.step(_row(2, self_=_self(funds=1200))), "self") == []
    assert _texts(restored.step(_row(3, self_=_self(funds=1300))), "self") == ["Money: §1,300 (was §1,200)."]


def test_a_new_session_starts_its_own_self_baseline():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1, self_=_self(funds=1200)))
    other = _row(2, self_=_self(funds=9000), kind="session_open")
    other["telemetry_session_id"] = "other"
    ext.step(other)
    assert _texts(ext.step(_row(3, self_=_self(funds=9000))), "self") == []


def test_the_self_percept_keys_differ_per_thing():
    ext = Extractor(resolve=_resolve)
    ext.step(_row(1, self_=_self(funds=1, skills=[{"skill": "S", "text_key": "111", "level": 1}])))
    percepts = ext.step(_row(2, self_=_self(funds=2, skills=[{"skill": "S", "text_key": "111", "level": 2}])))
    keys = [p.key for p in percepts if p.kind == "self"]
    assert len(keys) == len(set(keys)) == 2
