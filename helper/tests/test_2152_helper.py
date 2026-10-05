"""2.15.2 in the helper: the game's pop-ups become question records (what was asked,
the choices, the answer, who answered, what changed for her), and the portrait shows
whose home this is, the situations people are in, and any open question."""
import json

from domus_helper import consequences, outcomes
from domus_helper.paths import Paths
from domus_helper.thalamus import observation
from test_215_helper import _v8

FITNESS = "trait_SimPreference_Likes_Activities_Fitness"
TEXT = {"51": "A title", "52": "A question about a like",
        "61": "Yes", "62": "No"}


def _open(auto=False):
    return {"dialog_id": "555", "kind": "UiDialogOkCancel", "owner_id": "1",
            "title_key": "51", "text_key": "52",
            "responses": [{"response": "ok", "text_key": "61"},
                          {"response": "cancel", "text_key": "62"}],
            "auto_respond": auto}


def _v9(index, minute, dialogs=None, traits=()):
    row = _v8(index, minute, [])
    row["schema_version"] = 9
    row["place"] = {"owner_household_id": "hh9", "her_home": False, "venue": "Residential"}
    row["dialogs"] = dialogs or {"open": [], "closed": [], "truncated": False}
    for trait in traits:
        row["self"]["traits"].append({"trait": trait, "text_key": None, "personality": False})
    return row


def _asked_and_answered(answer="ok", auto=False, gained=True):
    closed = {"dialog_id": "555", "kind": "UiDialogOkCancel", "title_key": "51",
              "text_key": "52", "response": answer}
    after = [FITNESS] if gained else []
    return [_v9(0, 600),
            _v9(1, 601, {"open": [_open(auto)], "closed": [], "truncated": False}),
            _v9(2, 602, {"open": [_open(auto)], "closed": [], "truncated": False}),
            _v9(3, 603, {"open": [], "closed": [closed], "truncated": False}),
            _v9(4, 604, traits=after)]


def test_a_question_its_answer_and_what_changed():
    [record] = outcomes.questions(_asked_and_answered(), "s")
    assert record["kind"] == "question"
    assert record["dialog"] == {"kind": "UiDialogOkCancel", "title_key": "51",
                                "text_key": "52", "owner_id": "1"}
    assert [choice["response"] for choice in record["choices"]] == ["ok", "cancel"]
    assert record["answer"] == "ok" and record["answered_by"] == "owner"
    assert record["changed"]["self"]["traits_gained"] == [FITNESS]


def test_a_dialog_the_game_would_answer_itself():
    [record] = outcomes.questions(_asked_and_answered(auto=True), "s")
    assert record["answered_by"] == "owner_or_game"


def test_a_dismissed_dialog_has_no_answerer():
    [record] = outcomes.questions(_asked_and_answered(answer="closed", gained=False), "s")
    assert record["answered_by"] == "none"


def test_a_question_still_open_at_the_end():
    rows = _asked_and_answered()[:3]
    [record] = outcomes.questions(rows, "s")
    assert record["closed"] is None and record["answer"] is None
    assert record["answered_by"] is None and "changed" not in record


def test_question_records_do_not_reach_consequences(tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    folder = tmp_path / "outcomes"
    folder.mkdir()
    lines = [{"kind": "outcome", "interaction": {"name": "x"}},
             {"kind": "question", "question_id": "q"}]
    (folder / "s.jsonl").write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert [r["kind"] for r in consequences.load_records(Paths.from_env())] == ["outcome"]


def test_portrait_place_situations_and_the_open_question():
    row = _v9(1, 601, {"open": [_open()], "closed": [], "truncated": False})
    row["presence"][2]["household_id"] = "hh9"
    row["presence"][0]["household_id"] = "hh9"  # her own entry is never listed
    row["presence"][2]["situations"] = [{"situation": "situation_Visit", "role": "Host"}]
    row["presence"][0]["situations"] = [{"situation": "situation_Visit", "role": "Visitor"}]
    portrait = observation._portrait(row, TEXT.get)
    assert portrait["place"] == {"her_home": False, "venue": "Residential",
                                 "household_here": ["Travis Scott"]}
    assert portrait["situations"] == [{"situation": "situation_Visit", "role": "Visitor"}]
    travis = [c for c in portrait["company"] if c["name"] == "Travis Scott"][0]
    assert travis["situations"] == [{"situation": "situation_Visit", "role": "Host"}]
    assert portrait["asked"] == [{
        "dialog_id": "555", "title": "A title",
        "text": "A question about a like",
        "choices": [{"choice": "ok", "text": "Yes"}, {"choice": "cancel", "text": "No"}],
        "answers_itself": False}]
