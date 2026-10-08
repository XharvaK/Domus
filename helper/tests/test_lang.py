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


def test_sentence_drops_unresolved_placeholders():
    book = lang.SocialPhrases({
        "mixer_participants": {"pre": ["{actor.0} greets {participants}."]},
        "mixer_pronoun": {"pre": ["{actor.0.he/she} waves."]},
        "mixer_index": {"pre": ["{0.String} tells {1.SimFirstName}."]},
    })
    assert book.sentence("mixer_participants", ["Ada"]) is None
    assert book.sentence("mixer_pronoun", ["Ada"]) is None
    assert book.sentence("mixer_index", ["Ada", "Bea"]) is None


def test_load_missing_or_broken_is_empty(tmp_path):
    assert lang.SocialPhrases.load(tmp_path / "missing.json").entries == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert lang.SocialPhrases.load(broken).entries == {}
    assert lang.SocialPhrases.load(broken).sentence("mixer_wave", ["Ada"]) is None


def _row():
    return {
        "presence": [{"id": "1", "level": 0, "is_body": True, "name": "Ada"},
                     {"id": "2", "level": 0, "is_body": False, "name": "Bea", "distance_m": 1.0}],
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
    assert portrait["running"] == ["invented running"]
    assert portrait["queued"] == ["invented queued", "invented solo"]
    assert portrait["doing_said"] == [
        {"interaction": "invented_running", "sentence": "PLAIN invented_running Ada Bea",
         "state": "running"},
        {"interaction": "invented_queued", "sentence": "PLAIN invented_queued Ada Bea",
         "state": "queued"},
        {"interaction": "invented_solo", "sentence": "PLAIN invented_solo Ada", "state": "queued"},
    ]
    assert book.calls[0] == ("invented_running", ["Ada", "Bea"])

    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: None))
    quiet = observation._portrait(_row())
    assert quiet["running"] == ["invented running"]
    assert quiet["queued"] == ["invented queued", "invented solo"]
    assert quiet["addressed_by"] == [{"by": "2", "interaction": "invented_address"}]
    assert "doing_said" not in quiet
    assert not _has_sentence(quiet)

    class _Down:
        def sentence(self, tuning, actors):
            raise RuntimeError("down")

    monkeypatch.setattr(lang, "phrases", lambda: _Down())
    assert observation._portrait(_row())["running"] == ["invented running"]

    note = {"pad": ""}
    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: None))
    bare = observation._bytes(observation._portrait(_row(), notebook=note))
    note["pad"] = "p" * (8100 - bare)
    fitted = observation._portrait(_row(), notebook=note)
    assert "notebook" in fitted and observation._bytes(fitted) <= observation._PORTRAIT_LIMIT

    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: "S" * 200))
    shed = observation._portrait(_row(), notebook=note)
    assert shed["notebook"]["pad"] == note["pad"]
    assert shed["running"] == ["invented running"]
    assert shed["queued"] == ["invented queued", "invented solo"]
    assert all(isinstance(item, str) for item in shed["running"] + shed["queued"])
    assert "doing_said" not in shed
    assert "sentence" not in shed["addressed_by"][0]
    assert not _has_sentence(shed)


def test_over_budget_sheds_doing_said_then_addressed_before_notebook(monkeypatch):
    monkeypatch.setattr(lang, "phrases", lambda: _Book(lambda tuning, actors: "S" * 60))
    note = {"pad": ""}
    full = observation._portrait(_row(), notebook=note)
    assert full["running"] == ["invented running"]
    assert full["queued"] == ["invented queued", "invented solo"]
    assert all(isinstance(item, str) for item in full["running"] + full["queued"])
    full_bytes = observation._bytes(full)
    without_last = json.loads(json.dumps(full))
    without_last["doing_said"].pop()
    without_said = json.loads(json.dumps(full))
    del without_said["doing_said"]
    assert full_bytes <= observation._PORTRAIT_LIMIT
    assert observation._bytes(without_last) < full_bytes

    note["pad"] = "p" * (observation._PORTRAIT_LIMIT - full_bytes + 1)
    one = observation._portrait(_row(), notebook=note)
    assert [item["interaction"] for item in one["doing_said"]] == [
        "invented_running", "invented_queued"]
    assert one["doing_said"][0]["state"] == "running"
    assert one["doing_said"][1]["state"] == "queued"
    assert "sentence" in one["addressed_by"][0]
    assert one["notebook"]["pad"] == note["pad"]
    assert one["running"] == ["invented running"]
    assert one["queued"] == ["invented queued", "invented solo"]
    assert observation._bytes(one) <= observation._PORTRAIT_LIMIT

    note_b = {"pad": "p" * (observation._PORTRAIT_LIMIT - observation._bytes(without_said) + 1)}
    second = observation._portrait(_row(), notebook=note_b)
    assert "doing_said" not in second
    assert "sentence" not in second["addressed_by"][0]
    assert second["notebook"]["pad"] == note_b["pad"]
    assert second["running"] == ["invented running"]
    assert second["queued"] == ["invented queued", "invented solo"]
    assert all(isinstance(item, str) for item in second["running"] + second["queued"])
    assert observation._bytes(second) <= observation._PORTRAIT_LIMIT


def test_the_bundled_phrases_ship_with_their_license():
    bundled = lang._BUNDLED
    data = json.loads(bundled.read_text(encoding="utf-8"))
    assert data["source"]["license"] == "MIT" and len(data["entries"]) > 1000
    assert "MIT" in (bundled.parent / "SENTIENT_SIMS_LICENSE").read_text(encoding="utf-8")


def test_a_data_dir_import_takes_precedence_over_the_bundled_copy(tmp_path, monkeypatch):
    class _Paths:
        data_dir = tmp_path
    monkeypatch.setattr(lang.Paths, "from_env", staticmethod(lambda: _Paths))
    assert lang._social_path() == lang._BUNDLED
    local = tmp_path / "lang" / "social.json"
    local.parent.mkdir()
    local.write_text('{"v": 1, "entries": {}}', encoding="utf-8")
    assert lang._social_path() == local
