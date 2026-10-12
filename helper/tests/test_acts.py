"""8f: her options in each observation, and the courier that carries her acts both ways."""
import json

import pytest

from domus_helper import snapshot
from domus_helper.acts import ACT_CEILING_MS, PROBE_REPLY_MS, ActCourier, act_names, dialog_options, humanize, options, people_names, queue_options
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


def test_running_acts_and_the_stop_options_use_the_games_words_from_the_newest_menu():
    # HE1: the menu's text key gives the words; an act the menu gives no text for is humanized.
    from domus_helper.thalamus import observation
    names = act_names(MENU, {"77": "Read a Book"}.get)
    assert names("bookshelf_ReadBook") == "Read a Book"
    assert names("bookshelf_BrowseBooks") == "bookshelf Browse Books"
    assert act_names(None, {"77": "Read a Book"}.get)("bookshelf_ReadBook") == "bookshelf Read Book"
    row = {"interactions": {"observed": [
        {"interaction_id": "9", "affordance_text": "<class 'sims4.tuning.instances.bookshelf_ReadBook'>",
         "membership": "RUNNING"},
        {"interaction_id": "10", "affordance_text": "<class 'sims4.tuning.instances.bookshelf_BrowseBooks'>",
         "membership": "QUEUED"}]}}
    assert observation._portrait(row, act_name=names)["running"] == ["Read a Book"]
    assert observation._portrait(row, act_name=names)["queued"] == ["bookshelf Browse Books"]
    stops = queue_options(row, act_name=names)[0]["acts"]
    assert [item["text"] for item in stops] == ["Stop: Read a Book", "Cancel (queued): bookshelf Browse Books"]


def test_options_name_each_act_in_the_games_words_with_short_refs():
    texts = {"77": "Read a Book", "900": "Wooden Bookshelf"}
    catalog = {"511": {"name_key": "900"}}
    result = options(MENU, texts.get, catalog.get, room="4")
    assert result == [
        {"object": "Wooden Bookshelf", "object_id": "11", "where": "here, 2.0 m", "near": True, "acts": [
            {"ref": "a1", "guid64": "4242", "text": "Read a Book"},
            {"ref": "a2", "guid64": "4243", "text": "bookshelf Browse Books"}]},
        {"object": "object guitar", "object_id": "12", "where": "elsewhere, 6.5 m", "near": False, "acts": [
            {"ref": "a3", "guid64": "5000", "text": "guitar Practice"}]},
    ]


def test_an_object_in_another_room_than_hers_now_is_elsewhere_never_here():
    # HE12: the menu's same_room is about the menu's room; a menu from another room never says "here".
    menu = {"room": "4", "objects": [
        {"object_id": "1", "class": "object_a", "distance_m": 2.0, "same_room": True,
         "acts": [{"guid64": "1", "name": "a_Use", "text_key": None}]},
        {"object_id": "2", "class": "object_b", "distance_m": 3.0, "same_room": False,
         "acts": [{"guid64": "2", "name": "b_Use", "text_key": None}]},
        {"object_id": "3", "class": "object_c", "distance_m": 4.0, "same_room": None,
         "acts": [{"guid64": "3", "name": "c_Use", "text_key": None}]}]}
    assert [item["where"] for item in options(menu, room="4")] == ["here, 2.0 m", "elsewhere, 3.0 m", "nearby, 4.0 m"]
    assert [item["where"] for item in options(menu, room="7")] == ["elsewhere, 2.0 m", "nearby, 3.0 m", "nearby, 4.0 m"]
    assert [item["where"] for item in options(menu)] == ["nearby, 2.0 m", "nearby, 3.0 m", "nearby, 4.0 m"]


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
    row = {"presence": [{"id": "300", "name": "Dennis Kim"}, {"id": 100, "level": 0, "is_body": True, "name": "Her"}, "x"]}
    names = people_names(row)
    assert names == {"300": "Dennis Kim", "100": "Her"}
    result = options(menu, people=names)
    # SS4-v2 (PR3): the person she cannot see (301, not on the presence row) is not offered at all.
    assert [(o["object"], o["acts"][0]["text"]) for o in result] == [
        ("Dennis Kim", "social Greet Neighbor")]


PHONE_MENU = {"menu_rev": 4, "room": "4", "tested": 3, "refused": 1, "build_ms": 2.0, "objects": [
    {"object_id": "11", "definition_id": "511", "class": "object_bookshelf", "distance_m": 2.0, "same_room": True,
     "reach": None, "phone": None, "acts": [{"guid64": "4242", "name": "bookshelf_ReadBook", "text_key": None}]},
    {"object_id": "900", "definition_id": None, "class": "phone", "distance_m": None, "same_room": None,
     "reach": None, "phone": True, "acts": [{"guid64": "6001", "name": "phone_SampleMessage", "text_key": None}]}]}


def test_her_own_phone_is_an_option_named_your_phone():
    # 2.29.0: her phone is an object she uses. It is named "your phone", placed with her, and her
    # body (the same id) is never named as a person.
    result = options(PHONE_MENU, lambda key: None, people={"900": "Dennis Kim"})
    phone = [entry for entry in result if entry["object_id"] == "900"][0]
    assert phone == {"object": "your phone", "object_id": "900", "where": "with her", "near": True, "acts": [
        {"ref": "a2", "guid64": "6001", "text": "phone Sample Message"}]}
    assert [entry["object"] for entry in result] == ["object bookshelf", "your phone"]


DIALOG_ROW = {"presence": [{"id": "100", "level": 0, "is_body": True, "name": "Her"}], "dialogs": {"open": [
    {"dialog_id": "555", "kind": "UiRecipePicker", "owner_id": "100", "title_key": "1", "text_key": None,
     "auto_respond": False, "held": True, "responses": [{"response": "ok", "text_key": "2"}, {"response": "cancel", "text_key": "3"}],
     "rows": [{"option_id": "11", "name_key": "4", "enabled": True, "price": 5},
              {"option_id": "12", "name_key": "5", "enabled": False, "price": 9}]},
    {"dialog_id": "556", "kind": "UiDialogOkCancel", "owner_id": "42", "title_key": "1", "text_key": None,
     "auto_respond": False, "responses": [{"response": "ok", "text_key": "2"}], "rows": []}],
    "closed": [], "truncated": False}}


def test_a_question_the_game_asks_her_is_answered_by_choosing():
    texts = {"1": "What do you want to cook?", "2": "OK", "3": "Cancel", "4": "Grilled Cheese"}
    result = dialog_options(DIALOG_ROW, texts.get)
    assert result == [{"object": "The game asks: What do you want to cook?", "object_id": "dialog:555",
                       "where": "asked now", "acts": [
                           {"ref": "a1", "guid64": "11", "text": "Grilled Cheese (§5)"},
                           {"ref": "a2", "guid64": "cancel", "text": "Cancel"}]}]
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
        validate_observation(dict(body, options=[{"object": "x" * 33000}]), 1500)  # N8 (F4): 32,768 bytes
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
    # W12 (B3): a rejection says by whom: no game sentence here, so the probe refused it.
    assert client.bodies[-1]["events"][0]["detail"] == {"code": "NO_OBJECT", "tuning_name": "bookshelf_ReadBook",
                                                        "by": "probe"}


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
    assert ("a", "rejected", {"code": "NOT_ATTACHED", "by": "helper"}) in phases
    assert ("b", "rejected", {"code": "INBOX_FileNotFoundError", "by": "helper"}) in phases


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


def test_an_act_the_game_never_ends_becomes_unknown_once_it_detaches_or_passes_the_ceiling(tmp_path):
    # GL8: pushed acts do not stay "pushed" forever; a finished act is left alone.
    spool = Spool(tmp_path / "spool.db")
    client = _Client([ACT])
    courier = ActCourier(spool, lambda command, args: None)
    courier.tick(client, "h", 1000, True)
    client.acts = []
    courier.on_row(_row("PUSHED", act_id="a" * 32))
    courier.tick(client, "h", 2000, True)
    courier.tick(client, "h", 3000, False)
    courier.tick(client, "h", 4000, False)
    # A9-1: a detach is only a guess after a grace of two minutes; a short one leaves the act open.
    assert [e for body in client.bodies for e in body["events"] if e["phase"] == "unknown"] == []
    courier.tick(client, "h", 3000 + 120_000, False)
    unknown = [e for body in client.bodies for e in body["events"] if e["phase"] == "unknown"]
    assert unknown == [{"act_id": "a" * 32, "phase": "unknown", "at_ms": 123_000,
                        "detail": {"code": "GAME_DETACHED"}}]
    done = ActCourier(spool, lambda command, args: None)
    other = _Client([dict(ACT, act_id="b" * 32)])
    done.tick(other, "h", 1000, True)
    done.on_row(_row("FINISHED", act_id="b" * 32))
    late = _Client()
    done.tick(late, "h", 1000 + ACT_CEILING_MS, False)
    assert [e for body in late.bodies for e in body["events"] if e["phase"] == "unknown"] == []
    spool.close()


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
    assert detail == {"code": "PUSH_REFUSED", "detail": "debug text", "tuning_name": "bookshelf_ReadBook", "by": "probe"}
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


def test_an_object_the_game_sees_no_way_to_says_so_and_stays_listed():
    """2.25.0: reach false travels as noWay; true or unread adds nothing."""
    menu = {"objects": [dict(MENU["objects"][0], reach=False), dict(MENU["objects"][1], reach=None)]}
    listed = options(menu)
    assert [item["object_id"] for item in listed] == ["11", "12"]
    assert listed[0]["noWay"] == "the game sees no way for her to get there from where she is now"
    assert "noWay" not in listed[1]


class _SnapClient(_Client):
    def sync_acts(self, body):
        payload = super().sync_acts(body)
        if payload is not None:
            payload["snapshots"] = [{"snapshot_id": "p" * 32}]
        return payload


def test_requested_pictures_go_to_the_snapshot_module_after_the_acts(tmp_path, monkeypatch):
    handed = []
    monkeypatch.setattr(snapshot, "handle_requests_in_background", lambda ids, client, **kwargs: handed.append((ids, kwargs)))
    published = []
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: published.append(command))
    assert courier.tick(_SnapClient([ACT]), "h", 1000, True) == ["a" * 32]
    assert published == ["act"]
    assert handed == [([{"snapshot_id": "p" * 32}], {"helper_session": "h"})]


def test_no_round_trip_means_no_picture_is_handed_on(tmp_path, monkeypatch):
    handed = []
    monkeypatch.setattr(snapshot, "handle_requests_in_background", lambda ids, client, **kwargs: handed.append(ids))
    client = _SnapClient([ACT])
    client.down = True
    assert ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: None).tick(client, "h", 1000, True) == []
    assert handed == []


def _dialog(dialog_id, **extra):
    """A dialog sample from the probe (invented strings)."""
    dialog = {"dialog_id": dialog_id, "kind": "UiPicker", "owner_id": "100", "title_key": "1",
              "text_key": None, "auto_respond": False, "held": True,
              "responses": [{"response": "ok", "text_key": "2"}, {"response": "cancel", "text_key": "3"}],
              "rows": [{"option_id": "11", "name_key": "4", "enabled": True, "price": None},
                       {"option_id": "12", "name_key": "5", "enabled": True, "price": None}]}
    dialog.update(extra)
    return dialog


BODY = [{"id": "100", "level": 0, "is_body": True, "name": "Her"}]
TEXTS = {"1": "Pick some", "2": "OK", "3": "Cancel", "4": "Blue Vase", "5": "Red Vase", "9": "Tip Amount"}


def _asked(*dialogs):
    return {"presence": BODY, "dialogs": {"open": list(dialogs), "closed": [], "truncated": False}}


def test_a_picker_with_several_rows_lists_ok_and_carries_its_rules():
    dialog = _dialog("600", select={"min": 1, "max": 3})
    [entry] = dialog_options(_asked(dialog), TEXTS.get)
    assert [act["text"] for act in entry["acts"]] == ["Blue Vase", "Red Vase", "OK", "Cancel"]
    assert entry["acts"][2]["guid64"] == "ok"
    assert entry["answer_rules"] == {"select": {"min": 1, "max": 3}}


def test_a_single_row_picker_keeps_today_s_shape_without_rules():
    dialog = _dialog("601", select={"min": 1, "max": 1})
    [entry] = dialog_options(_asked(dialog), TEXTS.get)
    assert [act["guid64"] for act in entry["acts"]] == ["11", "12", "cancel"]
    assert "answer_rules" not in entry


def test_counts_and_text_fields_carry_their_limits_and_resolved_labels():
    dialog = _dialog("602", counts={"max_in_row": 4, "max_rows": 2},
                     text_inputs=[{"name": "tip", "min_length": 1, "max_length": 6, "numeric": True,
                                   "min_value": 0, "max_value": 50, "profanity_checked": False,
                                   "restricted": False, "default_key": "9"},
                                  {"name": "note", "min_length": 0, "max_length": None, "numeric": False,
                                   "min_value": None, "max_value": None, "profanity_checked": True,
                                   "restricted": True, "default_key": None}])
    [entry] = dialog_options(_asked(dialog), TEXTS.get)
    assert entry["answer_rules"] == {
        "counts": {"max_in_row": 4, "max_rows": 2},
        "text": [{"name": "tip", "label": "Tip Amount", "min_length": 1, "max_length": 6, "numeric": True,
                  "min_value": 0, "max_value": 50, "profanity_checked": False, "restricted": False},
                 {"name": "note", "label": "note", "min_length": 0, "max_length": None, "numeric": False,
                  "min_value": None, "max_value": None, "profanity_checked": True, "restricted": True}]}
    assert [act["guid64"] for act in entry["acts"]] == ["11", "12", "ok", "cancel"]


def test_a_text_dialog_with_only_buttons_is_offered_with_its_rules():
    dialog = _dialog("603", rows=[], responses=[{"response": "ok", "text_key": "2"}],
                     text_inputs=[{"name": "name", "min_length": 1, "max_length": 12, "numeric": False,
                                   "min_value": None, "max_value": None, "profanity_checked": True,
                                   "restricted": False, "default_key": "77"}])
    [entry] = dialog_options(_asked(dialog), TEXTS.get)
    assert entry["answer_rules"]["text"][0]["label"] == "name"
    assert [act["guid64"] for act in entry["acts"]] == ["ok"]


def test_dialogs_on_the_users_screen_are_never_offered():
    user = _dialog("610", cause="user", owner_id="100")
    identity = _dialog("611", cause="identity_user", owner_id="100")
    hers = _dialog("612", cause="hers", owner_id="100")
    result = dialog_options(_asked(user, identity, hers), TEXTS.get)
    assert [entry["object_id"] for entry in result] == ["dialog:612"]


def test_a_window_the_probe_does_not_hold_is_not_offered():
    shown = _dialog("630", held=False, cause="hers")
    assert dialog_options(_asked(shown), TEXTS.get) == []


def test_under_schema_14_a_null_cause_is_not_hers_and_under_13_the_owner_rule_decides():
    dialog = _dialog("631", cause=None)
    assert dialog_options(dict(_asked(dialog), schema_version=14), TEXTS.get) == []
    older = dialog_options(dict(_asked(dialog), schema_version=13), TEXTS.get)
    assert [entry["object_id"] for entry in older] == ["dialog:631"]


def test_a_select_of_zero_is_no_limit_a_rule_and_keeps_the_ok_button():
    dialog = _dialog("632", select={"min": 1, "max": 0})
    [entry] = dialog_options(_asked(dialog), TEXTS.get)
    assert entry["answer_rules"] == {"select": {"min": 1, "max": 0}}
    assert [act["guid64"] for act in entry["acts"]] == ["11", "12", "ok", "cancel"]


def test_an_older_probe_without_cause_keeps_the_owner_rule():
    mine = _dialog("620", owner_id="100")
    nobody = _dialog("621", owner_id=None)
    someone = _dialog("622", owner_id="42")
    result = dialog_options(_asked(mine, nobody, someone), TEXTS.get)
    assert [entry["object_id"] for entry in result] == ["dialog:620", "dialog:621"]



def test_a_dialog_she_can_answer_goes_to_the_probe_with_her_rows_and_text(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    answer = {"rows": [{"option_id": "11", "count": 2}], "text": {"tip": "12"}}
    client = _Client([dict(ACT, object_id="dialog:600", guid64="ok", answer=answer)])
    ActCourier(spool, lambda command, args: published.append((command, args))).tick(client, "h", 1000, True)
    assert published == [("answer", {"act_id": "a" * 32, "dialog_id": "600", "pick": "ok",
                                     "rows": [{"option_id": "11", "count": 2}], "text": {"tip": "12"}})]


def test_an_answer_with_only_text_or_only_rows_is_an_ok(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    client = _Client([dict(ACT, object_id="dialog:600", guid64="ok", answer={"text": {"tip": "12"}}),
                      dict(ACT, act_id="b" * 32, object_id="dialog:600", guid64="11",
                           answer={"rows": [{"option_id": "11", "count": 1}]})])
    ActCourier(spool, lambda command, args: published.append((command, args))).tick(client, "h", 1000, True)
    assert published[0][1] == {"act_id": "a" * 32, "dialog_id": "600", "pick": "ok", "text": {"tip": "12"}}
    assert published[1][1] == {"act_id": "b" * 32, "dialog_id": "600", "pick": "ok",
                               "rows": [{"option_id": "11", "count": 1}]}


def test_an_answer_that_is_not_well_formed_is_rejected_without_its_text(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    bad = {"rows": [{"option_id": "x1", "count": 1}], "text": {"tip": "secret words"}}
    client = _Client([dict(ACT, object_id="dialog:600", guid64="ok", answer=bad)])
    courier = ActCourier(spool, lambda command, args: published.append((command, args)))
    assert courier.tick(client, "h", 1000, True) == []
    assert courier.tick(client, "h", 2000, True) == []
    assert published == []
    sent = json.dumps(client.bodies)
    assert "ANSWER_INVALID" in sent and "secret words" not in sent
