"""Social talk in plain words. A Sim she can see is said doing a thing to whoever it is aimed at; her own
name is "you" when the talk is to her; a social percept reaches Ashley as names and sentences, never as ids."""
import json
from types import SimpleNamespace

from domus_helper import lang
from domus_helper.contract import validate_observation as check
from domus_helper.thalamus import observation
from domus_helper.thalamus.types import Percept


class _Book:
    """Invented sentences only: "<tuning>:<actors>". Tunings in `quiet` have no sentence."""

    def __init__(self, quiet=()):
        self.quiet = set(quiet)
        self.calls = []

    def sentence(self, tuning, actors):
        self.calls.append((tuning, list(actors)))
        if tuning in self.quiet:
            return None
        return "%s:%s" % (tuning, " ".join(actors))


def _body():
    return {"id": "1", "is_body": True, "name": "Ada", "room": "hall", "level": 0}


def _person(sim_id, name, room, distance=1.0, doing=None, target=None):
    item = {"id": sim_id, "is_body": False, "name": name, "room": room, "level": 0,
            "distance_m": distance, "on_lot": True}
    if doing is not None:
        item["doing"] = doing
    if target is not None:
        item["doing_target"] = target
    return item


def _portrait(presence, social=None, running=None):
    row = {"zone": {"room": "hall"}, "presence": [_body(), *presence]}
    if social is not None:
        row["social"] = social
    if running is not None:
        row["interactions"] = {"observed": running}
    return observation._portrait(row)


def test_a_seen_sim_doing_something_is_said_to_whoever_it_is_aimed_at(monkeypatch):
    book = _Book()
    monkeypatch.setattr(lang, "phrases", lambda: book)
    portrait = _portrait([
        _person("2", "Bob", "hall", doing="invented_joke", target="1"),
        _person("3", "Mia", "hall"),
        _person("4", "Cy", "hall", doing="invented_tell", target="3"),
        _person("5", "Dee", "yard", distance=12.0),
        _person("6", "Eve", "hall", doing="invented_wave", target="5"),
        _person("7", "Fay", "hall", doing="invented_sit", target="chair-9"),
        _person("8", "Gus", "hall", doing="invented_wave"),
        _person("9", "Hal", "hall", doing="invented_quiet", target="1"),
    ])
    by_name = {item["name"]: item for item in portrait["company"] if "name" in item}
    assert by_name["Bob"]["said"] == "invented_joke:Bob you"
    assert by_name["Cy"]["said"] == "invented_tell:Cy Mia"
    assert by_name["Eve"]["said"] == "invented_wave:Eve someone"
    assert by_name["Fay"]["said"] == "invented_sit:Fay"
    assert by_name["Gus"]["said"] == "invented_wave:Gus"
    assert ("invented_joke", ["Bob", "you"]) in book.calls
    assert ("invented_tell", ["Cy", "Mia"]) in book.calls
    assert ("invented_wave", ["Eve", "someone"]) in book.calls
    assert ("invented_sit", ["Fay"]) in book.calls
    assert "said" not in by_name["Mia"]
    assert "Dee" not in str([item.get("said") for item in portrait["company"]])


def test_company_said_is_omitted_when_the_dictionary_has_no_sentence(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book(quiet=("invented_quiet",)))
    portrait = _portrait([_person("2", "Bob", "hall", doing="invented_quiet", target="1"),
                          _person("3", "Mia", "hall", doing="invented_wave")])
    by_name = {item["name"]: item for item in portrait["company"]}
    assert by_name["Bob"]["doing"] == "invented_quiet"
    assert "said" not in by_name["Bob"]
    assert by_name["Mia"]["said"] == "invented_wave:Mia"


def test_an_addressed_sentence_says_you_for_her_and_her_own_act_keeps_her_name(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    portrait = _portrait(
        [_person("2", "Bob", "hall")],
        social=[{"actor_id": "2", "affordance_text": "invented_ask"}],
        running=[{"affordance_text": "invented_wave", "membership": "RUNNING", "target_id": "2"}])
    assert portrait["addressed_by"] == [{
        "by": "2", "interaction": "invented_ask", "sentence": "invented_ask:Bob you"}]
    assert portrait["doing_said"] == [{
        "interaction": "invented_wave", "sentence": "invented_wave:Ada Bob", "state": "running"}]


def test_company_said_is_shed_after_her_own_sentences_and_before_the_ones_to_her(monkeypatch):
    portrait = {
        "doing_said": [{"interaction": "a", "sentence": "A", "state": "running"}],
        "company": [{"id": "2", "name": "Bob", "said": "B1"}, {"id": "3", "name": "Mia", "said": "B2"}],
        "addressed_by": [{"by": "4", "interaction": "x", "sentence": "C1"}],
    }
    assert observation._shed_sentence(portrait) is True
    assert "doing_said" not in portrait
    assert observation._shed_sentence(portrait) is True
    assert "said" not in portrait["company"][1] and portrait["company"][0]["said"] == "B1"
    assert observation._shed_sentence(portrait) is True
    assert "said" not in portrait["company"][0]
    assert portrait["addressed_by"][0]["sentence"] == "C1"
    assert observation._shed_sentence(portrait) is True
    assert "sentence" not in portrait["addressed_by"][0]
    assert observation._shed_sentence(portrait) is False


def _talk_row(presence):
    return {
        "written_sequence": 3, "wall_timestamp_ms": 5_000, "telemetry_session_id": "sess-1",
        "body": {"sim_id": "1", "posture": {"posture_name": "stand"}},
        "game": {"clock_speed": "NORMAL", "paused": False},
        "zone": {"zone_id": 7, "lot_id": 9, "room": "hall"},
        "motives": [{"id": "hunger", "value": 40, "band": "ok"}],
        "presence": [_body(), *presence],
    }


def _build(percepts, row):
    obs = observation.build(SimpleNamespace(percepts=tuple((p, 0.5) for p in percepts)), {
        "helper_session": "a" * 32, "obs_seq": 0, "slot_id": 3, "guid": "abc",
        "lineage_class": "load", "row": row,
    })
    check(obs, 5_000)
    return obs


def test_a_social_percept_is_said_in_words_and_carries_no_raw_ids(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    talk = Percept("social", "4471", "9123", "addressed", urgency="always_through",
                   facts=(("ticks", "5"), ("affordance_text", "invented_ask")))
    obs = _build([talk], _talk_row([_person("4471", "Bob", "hall")]))
    assert obs["percepts"][0]["kind"] == "social"
    assert obs["percepts"][0]["facts"] == {
        "by": "Bob", "interaction": "invented_ask", "sentence": "invented_ask:Bob you",
        "bucket": "addressed"}
    text = json.dumps(obs["percepts"])
    assert "4471" not in text and "9123" not in text


def test_a_social_percept_from_someone_she_cannot_see_is_by_someone(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book())
    talk = Percept("social", "4471", "9123", "addressed",
                   facts=(("affordance_text", "invented_ask"),))
    obs = _build([talk], _talk_row([_person("4471", "Bob", "yard", distance=12.0)]))
    assert obs["percepts"][0]["facts"] == {
        "by": "someone", "interaction": "invented_ask",
        "sentence": "invented_ask:someone you", "bucket": "addressed"}


def test_a_social_percept_without_a_sentence_or_a_name_keeps_only_what_is_known(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book(quiet=("invented_ask",)))
    quiet = Percept("social", "4471", "9123", "addressed", facts=(("affordance_text", "invented_ask"),))
    obs = _build([quiet], _talk_row([_person("4471", "Bob", "hall")]))
    assert obs["percepts"][0]["facts"] == {"by": "Bob", "interaction": "invented_ask", "bucket": "addressed"}
    bare = Percept("social", "4471", "9123", "addressed", facts=(("ticks", "5"),))
    obs = _build([bare], _talk_row([]))
    assert obs["percepts"][0]["facts"] == {"by": "someone", "bucket": "addressed"}
    assert "4471" not in json.dumps(obs["percepts"])

