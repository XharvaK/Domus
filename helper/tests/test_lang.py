"""Invented phrase fixtures only. The Sentient Sims dictionary is not in this repo."""
import json

from domus_helper import lang
from domus_helper.thalamus import observation

_SOURCE = {"repo": "example/phrases", "path": "descriptions/invented.ts",
           "commit": "abc123", "license": "MIT", "fetched": "2026-10-07"}

_SNIPPET = """
export const interactionDescriptions = {
    'mixer_wave': {
        pre_actions: ['{actor.0} waves at {actor.1}.'],
    },
    "mixer_quoted": {
        pre_actions: ['{actor.0} nods.'],
    },
    'mixer_two': {
        pre_actions: [
            '{actor.0} speaks first.',
            '{actor.0} speaks second.',
        ],
    },
    'mixer_escape': {
        pre_actions: ['{actor.0} says \\'hello\\'.'],
    },
    'Mixer_Case': {
        pre_actions: ['  {actor.0}   meets
{actor.1}  '],
    },
    mixer_plain: {
        pre_actions: ['{actor.0} waits.'],
    },
    'mixer_dull': {
        ignored: true,
    },
    'mixer_neither': {
        note: 1,
    },
};
"""


def test_import_descriptions_parses_invented_entries(tmp_path):
    ts_path = tmp_path / "invented.ts"
    out_path = tmp_path / "lang" / "social.json"
    ts_path.write_text(_SNIPPET, encoding="utf-8")
    counts = lang.import_descriptions(ts_path, out_path, _SOURCE)
    assert counts == {"pre": 6, "ignored": 1}
    assert json.loads(out_path.read_text(encoding="utf-8")) == {
        "v": 1,
        "source": _SOURCE,
        "entries": {
            "mixer_wave": {"pre": ["{actor.0} waves at {actor.1}."]},
            "mixer_quoted": {"pre": ["{actor.0} nods."]},
            "mixer_two": {"pre": ["{actor.0} speaks first.", "{actor.0} speaks second."]},
            "mixer_escape": {"pre": ["{actor.0} says 'hello'."]},
            "mixer_case": {"pre": ["  {actor.0}   meets\n{actor.1}  "]},
            "mixer_plain": {"pre": ["{actor.0} waits."]},
            "mixer_dull": {"ignored": True},
        },
    }


def test_sentence_fills_actors_and_stops_at_200_chars(tmp_path):
    out_path = tmp_path / "social.json"
    ts_path = tmp_path / "invented.ts"
    ts_path.write_text(_SNIPPET + """
    'mixer_long': {
        pre_actions: ['%s'],
    },
""" % ("{actor.0} " + ("n" * 250)), encoding="utf-8")
    lang.import_descriptions(ts_path, out_path, _SOURCE)
    book = lang.SocialPhrases.load(out_path)
    assert book.sentence("mixer_wave", ["Ada", "Bea"]) == "Ada waves at Bea."
    assert book.sentence("MIXER_WAVE", ["Ada"]) == "Ada waves at someone."
    assert book.sentence("mixer_case", ["Ada", "Bea"]) == "Ada meets Bea"
    assert book.sentence("mixer_two", ["Ada", "Bea"]) == "Ada speaks first."
    assert book.sentence("mixer_escape", ["Ada"]) == "Ada says 'hello'."
    assert book.sentence("mixer_dull", ["Ada", "Bea"]) is None
    assert book.sentence("mixer_missing", ["Ada"]) is None
    assert book.sentence("mixer_plain", []) == "someone waits."
    filled = book.sentence("mixer_long", ["Ada"])
    assert len(filled) == 200 and filled.startswith("Ada ")


def test_load_missing_or_broken_is_empty(tmp_path):
    assert lang.SocialPhrases.load(tmp_path / "missing.json").entries == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert lang.SocialPhrases.load(broken).entries == {}
    assert lang.SocialPhrases.load(broken).sentence("mixer_wave", ["Ada"]) is None


def _row():
    return {
        "presence": [{"id": "1", "is_body": True, "name": "Ada"},
                     {"id": "2", "is_body": False, "name": "Bea"}],
        "social": [{"actor_id": "2", "affordance_text": "invented_address"}],
        "interactions": {"observed": [
            {"affordance_text": "invented_running", "membership": "RUNNING", "target_id": "2"},
            {"affordance_text": "invented_queued", "membership": "QUEUED", "target_id": "2"},
            {"affordance_text": "invented_solo", "membership": "QUEUED"},
        ]},
    }


class _Book:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def sentence(self, tuning, actors):
        self.calls.append((tuning, list(actors)))
        return self.reply(tuning, actors)


def _has_sentence(value):
    if isinstance(value, dict):
        return "sentence" in value or any(_has_sentence(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_sentence(item) for item in value)
    return False


def test_portrait_adds_sentence_and_sheds_it_first(monkeypatch):
    book = _Book(lambda tuning, actors: "PLAIN %s %s" % (tuning, " ".join(actors)))
    monkeypatch.setattr(lang, "phrases", lambda: book)
    portrait = observation._portrait(_row())
    assert portrait["addressed_by"] == [{
        "by": "2", "interaction": "invented_address", "sentence": "PLAIN invented_address Bea Ada"}]
    assert portrait["running"] == [{
        "interaction": "invented_running", "sentence": "PLAIN invented_running Ada Bea"}]
    assert portrait["queued"][0]["sentence"] == "PLAIN invented_queued Ada Bea"
    assert portrait["queued"][1]["sentence"] == "PLAIN invented_solo Ada"
    assert book.calls[0] == ("invented_running", ["Ada", "Bea"])

    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: None))
    quiet = observation._portrait(_row())
    assert quiet["running"] == ["invented_running"]
    assert quiet["queued"] == ["invented_queued", "invented_solo"]
    assert quiet["addressed_by"] == [{"by": "2", "interaction": "invented_address"}]
    assert not _has_sentence(quiet)

    class _Down:
        def sentence(self, tuning, actors):
            raise RuntimeError("down")

    monkeypatch.setattr(lang, "phrases", lambda: _Down())
    assert observation._portrait(_row())["running"] == ["invented_running"]

    note = {"pad": ""}
    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: None))
    bare = observation._bytes(observation._portrait(_row(), notebook=note))
    note["pad"] = "p" * (8100 - bare)
    fitted = observation._portrait(_row(), notebook=note)
    assert "notebook" in fitted and observation._bytes(fitted) <= observation._PORTRAIT_LIMIT

    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: "S" * 200))
    shed = observation._portrait(_row(), notebook=note)
    assert shed["notebook"]["pad"] == note["pad"]
    assert shed["running"] == ["invented_running"]
    assert shed["queued"] == ["invented_queued", "invented_solo"]
    assert "sentence" not in shed["addressed_by"][0]
    assert not _has_sentence(shed)
