"""8f: her options in each observation, and the courier that carries her acts both ways."""
import json

import pytest

from domus_helper.acts import PROBE_REPLY_MS, ActCourier, dialog_options, humanize, options, people_names
from domus_helper.contract import ContractError, validate_observation
from domus_helper.spool import Spool
from domus_helper.thalamus.percepts import Extractor

MENU = {"menu_rev": 3, "room": "4", "tested": 9, "refused": 2, "build_ms": 12.0, "objects": [
    {"object_id": "11", "definition_id": "511", "class": "object_bookshelf", "distance_m": 2.0, "same_room": True,
     "acts": [{"guid64": "4242", "name": "bookshelf_ReadBook", "text_key": "77"},
              {"guid64": "4243", "name": "bookshelf_BrowseBooks", "text_key": None}]},
    {"object_id": "12", "definition_id": None, "class": "object_guitar", "distance_m": 6.5, "same_room": False,
     "acts": [{"guid64": "5000", "name": "guitar_Practice", "text_key": None}]},
]}


def test_options_name_each_act_in_the_games_words_with_short_refs():
    texts = {"77": "Read a Book", "900": "Wooden Bookshelf"}
    catalog = {"511": {"name_key": "900"}}
    result = options(MENU, texts.get, catalog.get)
    assert result == [
        {"object": "Wooden Bookshelf", "object_id": "11", "where": "here, 2.0 m", "acts": [
            {"ref": "a1", "guid64": "4242", "text": "Read a Book"},
            {"ref": "a2", "guid64": "4243", "text": "bookshelf Browse Books"}]},
        {"object": "object guitar", "object_id": "12", "where": "nearby, 6.5 m", "acts": [
            {"ref": "a3", "guid64": "5000", "text": "guitar Practice"}]},
    ]


def test_options_drop_the_farthest_objects_to_fit_and_ignore_junk():
    assert len(options(MENU, limit=260)) == 1
    assert options(MENU, limit=10) == []
    assert options(None) == [] and options({"objects": "x"}) == []
    assert options({"objects": [{"acts": [{}]}, "x"]}) == []
    assert humanize("tv_WatchKids") == "tv Watch Kids" and humanize("") == "unnamed"


def test_people_in_her_menu_are_named_as_her_senses_name_them():
    menu = {"objects": [{"object_id": "300", "definition_id": None, "class": "sim", "distance_m": 6.8,
                         "same_room": False, "acts": [{"guid64": "77", "name": "social_Greet_Neighbor", "text_key": None}]},
                        {"object_id": "301", "definition_id": None, "class": "sim", "distance_m": 7.0,
                         "same_room": False, "acts": [{"guid64": "78", "name": "sim_InviteIn", "text_key": None}]}]}
    row = {"presence": [{"id": "300", "name": "Dennis Kim"}, {"id": 100, "is_body": True, "name": "Her"}, "x"]}
    names = people_names(row)
    assert names == {"300": "Dennis Kim", "100": "Her"}
    result = options(menu, people=names)
    assert [(o["object"], o["acts"][0]["text"]) for o in result] == [
        ("Dennis Kim", "social Greet Neighbor"), ("someone", "sim Invite In")]


DIALOG_ROW = {"presence": [{"id": "100", "is_body": True, "name": "Her"}], "dialogs": {"open": [
    {"dialog_id": "555", "kind": "UiRecipePicker", "owner_id": "100", "title_key": "1", "text_key": None,
     "auto_respond": False, "responses": [{"response": "ok", "text_key": "2"}, {"response": "cancel", "text_key": "3"}],
     "rows": [{"option_id": "11", "name_key": "4", "enabled": True, "price": 5},
              {"option_id": "12", "name_key": "5", "enabled": False, "price": 9}]},
    {"dialog_id": "556", "kind": "UiDialogOkCancel", "owner_id": "42", "title_key": "1", "text_key": None,
     "auto_respond": False, "responses": [{"response": "ok", "text_key": "2"}], "rows": []}],
    "closed": [], "truncated": False}}


def test_a_question_the_game_asks_her_is_answered_by_choosing():
    texts = {"1": "What do you want to cook?", "2": "OK", "3": "Cancel", "4": "Grilled Cheese"}
    result = dialog_options(DIALOG_ROW, texts.get, start=2)
    assert result == [{"object": "The game asks: What do you want to cook?", "object_id": "dialog:555",
                       "where": "asked now", "acts": [
                           {"ref": "a3", "guid64": "11", "text": "Grilled Cheese (§5)"},
                           {"ref": "a4", "guid64": "cancel", "text": "Cancel"}]}]
    assert dialog_options({}) == [] and dialog_options({"dialogs": {"open": ["x"]}}) == []


def test_an_answer_goes_to_the_probe_as_an_answer(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    client = _Client([dict(ACT, object_id="dialog:555", guid64="11")])
    ActCourier(spool, lambda command, args: published.append((command, args))).tick(client, "h", 1000, True)
    assert published == [("answer", {"act_id": "a" * 32, "dialog_id": "555", "pick": "11"})]


def test_the_contract_carries_options_within_8_kib():
    body = {"v": 1, "observation_id": "h.1", "world": "slot8", "branch": "b", "session": "s", "attachment": "h",
            "body": "1", "snapshot": "1", "seq": 1, "source_time_ms": 1000, "expires_at_ms": 2000,
            "lineage_class": "CURRENT", "percepts": [{"kind": "need", "salience": 0.1, "facts": {}}],
            "options": options(MENU)}
    assert validate_observation(body, 1500)["options"] == body["options"]
    with pytest.raises(ContractError):
        validate_observation(dict(body, options=[{"object": "x" * 9000}]), 1500)
    with pytest.raises(ContractError):
        validate_observation(dict(body, options="a1"), 1500)


class _Client:
    def __init__(self, acts=()):
        self.acts = list(acts)
        self.bodies = []
        self.down = False

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        if self.down:
            return None
        return {"status": "ok", "applied": len(body["events"]), "acts": list(self.acts)}


ACT = {"act_id": "a" * 32, "object_id": "11", "guid64": "4242", "expires_at_ms": 99_000}


def _row(phase, **extra):
    e2 = {"act_id": "a" * 32, "phase": phase, "code": None, "object_id": "11", "guid64": "4242",
          "interaction_id": None, "tuning_name": "bookshelf_ReadBook", "finishing_type": None, "detail": None}
    e2.update(extra)
    return {"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 5000, "e2": e2}


def test_an_act_is_written_once_even_across_a_restart(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    client = _Client([ACT])
    courier = ActCourier(spool, lambda command, args: published.append((command, args)))
    assert courier.tick(client, "h", 1000, True) == ["a" * 32]
    assert published == [("act", {"act_id": "a" * 32, "object_id": "11", "guid64": "4242"})]
    assert courier.tick(client, "h", 2000, True) == []
    assert client.bodies[-1]["events"] == [{"act_id": "a" * 32, "phase": "received", "at_ms": 1000}]
    again = ActCourier(spool, lambda command, args: published.append((command, args)))
    assert again.tick(client, "h", 3000, True) == []
    assert len(published) == 1


def test_the_probes_record_goes_back_to_mint_in_order(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client([ACT])
    courier = ActCourier(spool, lambda command, args: None)
    courier.tick(client, "h", 1000, True)
    client.acts = []
    courier.on_row(_row("ACCEPTED"))
    courier.on_row(_row("PUSHED", interaction_id="777"))
    courier.on_row(_row("FINISHED", interaction_id="777", finishing_type="FinishingType.NATURAL"))
    courier.on_row({"event_kind": "presence_snapshot"})
    courier.tick(client, "h", 2000, True)
    sent = client.bodies[-1]["events"]
    assert [event["phase"] for event in sent] == ["received", "accepted", "pushed", "finished"]
    assert sent[-1]["detail"] == {"tuning_name": "bookshelf_ReadBook", "finishing_type": "FinishingType.NATURAL",
                                  "interaction_id": "777"}
    courier.tick(client, "h", 1000 + PROBE_REPLY_MS + 1, True)
    assert client.bodies[-1]["events"] == []


def test_events_wait_while_mint_is_unreachable(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client()
    courier = ActCourier(spool, lambda command, args: None)
    courier.on_row(_row("REJECTED", code="NO_OBJECT"))
    client.down = True
    courier.tick(client, "h", 1000, True)
    client.down = False
    courier.tick(client, "h", 2000, True)
    assert [event["phase"] for event in client.bodies[-1]["events"]] == ["rejected"]
    assert client.bodies[-1]["events"][0]["detail"] == {"code": "NO_OBJECT", "tuning_name": "bookshelf_ReadBook"}


def test_not_attached_or_an_inbox_failure_is_a_rejection_not_a_push(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client([ACT])
    published = []
    courier = ActCourier(spool, lambda command, args: published.append(args))
    assert courier.tick(client, "h", 1000, False) == []
    assert published == []
    client.acts = [dict(ACT, act_id="b" * 32)]

    def broken(command, args):
        raise FileNotFoundError("inbox")

    other = ActCourier(spool, broken)
    other.tick(client, "h", 2000, True)
    other.tick(client, "h", 3000, True)
    phases = [(e["act_id"][0], e["phase"], e.get("detail")) for body in client.bodies for e in body["events"]]
    assert ("a", "rejected", {"code": "NOT_ATTACHED"}) in phases
    assert ("b", "rejected", {"code": "INBOX_FileNotFoundError"}) in phases


def test_an_act_the_probe_never_answers_about_becomes_unknown_once(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client([ACT])
    courier = ActCourier(spool, lambda command, args: None)
    courier.tick(client, "h", 1000, True)
    client.acts = []
    courier.tick(client, "h", 1000 + PROBE_REPLY_MS, True)
    courier.tick(client, "h", 2000 + PROBE_REPLY_MS, True)
    unknown = [e for body in client.bodies for e in body["events"] if e["phase"] == "unknown"]
    assert unknown == [{"act_id": "a" * 32, "phase": "unknown", "at_ms": 1000 + PROBE_REPLY_MS,
                        "detail": {"code": "NO_PROBE_REPLY"}}]


def test_a_refusal_carries_the_resolved_sentence_not_the_key(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client()
    texts = {"88001": "Not possible right now."}
    courier = ActCourier(spool, lambda command, args: None, resolve=texts.get)
    courier.on_row(_row("REJECTED", code="PUSH_REFUSED", detail="debug text", reason_key="88001"))
    courier.tick(client, "h", 2000, True)
    event = client.bodies[-1]["events"][0]
    assert event["detail"]["detail"] == "debug text"
    assert event["detail"]["reason"] == "Not possible right now."
    assert "reason_key" not in event["detail"]
    assert "88001" not in json.dumps(event)
    courier._resolve = lambda key: "n" * 250
    courier.on_row(_row("REJECTED", code="PUSH_REFUSED", detail="debug text", reason_key="88001"))
    courier.tick(client, "h", 3000, True)
    assert client.bodies[-1]["events"][0]["detail"]["reason"] == "n" * 200


def test_an_unknown_reason_key_adds_no_sentence(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client()
    courier = ActCourier(spool, lambda command, args: None, resolve=lambda key: None)
    courier.on_row(_row("REJECTED", code="PUSH_REFUSED", detail="debug text", reason_key="88001"))
    courier.tick(client, "h", 2000, True)
    detail = client.bodies[-1]["events"][0]["detail"]
    assert detail == {"code": "PUSH_REFUSED", "detail": "debug text", "tuning_name": "bookshelf_ReadBook"}
    assert "reason" not in detail


def test_a_refused_or_unknown_act_wakes_her():
    extractor = Extractor()
    assert extractor.step(_row("PUSHED")) == []
    assert extractor.step(_row("FINISHED")) == []
    rejected = extractor.step(_row("REJECTED", code="GAME_REFUSED", detail="too tired"))
    assert [(p.kind, p.bucket, p.urgency) for p in rejected] == [("interaction", "act_rejected", "wake")]
    assert dict(rejected[0].facts)["code"] == "GAME_REFUSED"
    assert [p.bucket for p in extractor.step(_row("UNKNOWN"))] == ["act_unknown"]


def test_an_act_the_user_asked_for_goes_to_the_probe_marked(tmp_path):
    """2.24.0: owner travels only when Mint marked the act; her own acts carry nothing new."""
    spool = Spool(tmp_path / "spool.db")
    published = []
    client = _Client([dict(ACT, owner=True), dict(ACT, act_id="b" * 32, owner="yes")])
    ActCourier(spool, lambda command, args: published.append((command, args))).tick(client, "h", 1000, True)
    assert published == [("act", {"act_id": "a" * 32, "object_id": "11", "guid64": "4242", "owner": True}),
                         ("act", {"act_id": "b" * 32, "object_id": "11", "guid64": "4242"})]


def test_whether_the_game_began_the_act_goes_back_to_mint(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    client = _Client([ACT])
    courier = ActCourier(spool, lambda command, args: None)
    courier.tick(client, "h", 1000, True)
    client.acts = []
    courier.on_row(_row("FINISHED", interaction_id="777", finishing_type="FinishingType.INTERACTION_INCOMPATIBILITY",
                        started=False))
    courier.tick(client, "h", 2000, True)
    assert client.bodies[-1]["events"][-1]["detail"] == {
        "tuning_name": "bookshelf_ReadBook", "finishing_type": "FinishingType.INTERACTION_INCOMPATIBILITY",
        "interaction_id": "777", "started": False}


def test_an_act_the_game_ended_before_it_began_wakes_her():
    extractor = Extractor()
    assert extractor.step(_row("FINISHED", started=True)) == []
    never = extractor.step(_row("FINISHED", started=False, finishing_type="FinishingType.INTERACTION_INCOMPATIBILITY"))
    assert [(p.kind, p.bucket, p.urgency) for p in never] == [("interaction", "act_never_started", "wake")]
    assert dict(never[0].facts)["finishing_type"] == "FinishingType.INTERACTION_INCOMPATIBILITY"
