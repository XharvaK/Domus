"""Synthetic rows for percept extraction and the online forward models."""

import json

import pytest

from domus_helper.telemetry import file_rows, raw_rows
from domus_helper.thalamus.forward import DurationModel, NeedModel
from domus_helper.thalamus.percepts import Extractor
from domus_helper.thalamus.types import Percept


def _row(seq, *, kind="presence_snapshot", session="sess", ticks=100, paused=False,
         sim="ASH", motives=None, observed=None, posture="stand", target="chair",
         zone_id=1, lot_id=9, wall=1_000_000, speed="NORMAL", presence=None,
         social=None, include_presence=False, e2=None, extra=None):
    row = {
        "event_kind": kind,
        "written_sequence": seq,
        "wall_timestamp_ms": wall + seq * 1000,
        "monotonic_ns": (wall + seq * 1000) * 1_000_000,
        "telemetry_session_id": session,
        "game": {"ticks": ticks, "clock_speed": speed, "paused": paused},
        "body": {
            "sim_id": sim,
            "posture": {"posture_name": posture, "target_id": target},
        },
        "interactions": {"observed": observed or []},
        "motives": motives if motives is not None else [],
        "zone": {"zone_id": zone_id, "lot_id": lot_id, "room": None, "position": None},
    }
    if include_presence:
        row["presence"] = presence or []
        row["social"] = social or []
    if e2 is not None:
        row["e2"] = e2
    if extra:
        row.update(extra)
    return row


def _motive(mid, value, band):
    return {"id": mid, "value": value, "band": band, "age_ticks": 0}


def _entry(aff, membership="RUNNING", iid="i1", source="InteractionSource.AUTONOMY", text="sit"):
    return {
        "entry_key": iid, "interaction_id": iid, "affordance_id": aff,
        "affordance_text": text, "target_id": "t", "source_raw": source,
        "source_norm": "autonomy", "membership": membership,
    }


def _kinds(percepts):
    return [p.kind for p in percepts]


def test_raw_rows_skips_validation(tmp_path):
    path = tmp_path / "old.jsonl"
    path.write_bytes(b'{"event_kind":"not-a-kind","schema_version":2}\n{"partial":')
    loaded = list(raw_rows(path))
    assert loaded == [{"event_kind": "not-a-kind", "schema_version": 2}]
    with pytest.raises(Exception):
        list(file_rows(path))


def test_need_model_learns_rate_and_z():
    model = NeedModel()
    # first pair sets the rate; z stays 0 because there is no prior rate
    z0 = model.observe("hunger", (), 10, 50.0, 20, 40.0)
    assert z0 == 0.0
    assert model.rate("hunger", ()) == pytest.approx(-1.0)
    # prediction 40 + -1*10 = 30; value 50; |e|=20; sigma was 1; z=20
    z1 = model.observe("hunger", (), 20, 40.0, 30, 50.0)
    assert z1 == pytest.approx(20.0)
    blob = model.to_dict()
    again = NeedModel.from_dict(blob)
    assert again.rate("hunger", ()) == pytest.approx(model.rate("hunger", ()))
    model.reset()
    assert model.rate("hunger", ()) is None


def test_duration_surprise_and_seed():
    model = DurationModel()
    assert model.surprise(10, 14244) == 0.0
    for value in (10, 10, 10):
        model.observe(14244, value)
    assert model.surprise(10, 14244) == 0.0
    assert model.surprise(100, 14244) == 3.0
    assert model.surprise(1, 14244) == 3.0
    seeded = DurationModel().seed_from_calibration({
        "durations": [{"affordance_id": 5, "median_ticks": 40}, {"affordance_id": 6}],
    })
    seeded.seed_from_calibration({})
    seeded.seed_from_calibration({"durations": None})
    assert seeded.seeds[5] == 40
    assert 6 not in seeded.seeds
    roundtrip = DurationModel.from_dict(model.to_dict())
    assert roundtrip.surprise(100, 14244) == 3.0


def test_band_transitions_and_quiet_need():
    ext = Extractor()
    base = [_motive("hunger", 80, "ok")]
    assert ext.step(_row(1, ticks=10, motives=base)) == []
    low = ext.step(_row(2, ticks=20, motives=[_motive("hunger", 40, "low")]))
    assert [(p.bucket, p.urgency) for p in low if p.kind == "need"] == [("low", "wake")]
    distress = ext.step(_row(3, ticks=30, motives=[_motive("hunger", 10, "distress")]))
    assert [(p.bucket, p.urgency) for p in distress if p.kind == "need"] == [
        ("distress", "always_through")]
    recover_low = ext.step(_row(4, ticks=40, motives=[_motive("hunger", 40, "low")]))
    assert [(p.bucket, p.urgency) for p in recover_low if p.kind == "need"] == [
        ("low", "normal")]
    recover_ok = ext.step(_row(5, ticks=50, motives=[_motive("hunger", 80, "ok")]))
    assert [(p.bucket, p.urgency) for p in recover_ok if p.kind == "need"] == [
        ("ok", "normal")]
    quiet = ext.step(_row(6, ticks=60, motives=[_motive("hunger", 79, "ok")]))
    assert [p for p in quiet if p.kind == "need"] == []
    direct = Extractor()
    direct.step(_row(1, ticks=10, motives=[_motive("energy", 90, "ok")]))
    jumped = direct.step(_row(2, ticks=20, motives=[_motive("energy", 5, "distress")]))
    assert jumped[0].urgency == "always_through"
    other = Extractor()
    other.step(_row(1, sim="OTHER", motives=[_motive("fun", 10, "distress")]))
    second = other.step(_row(2, sim="OTHER", ticks=20, motives=[_motive("fun", 9, "distress")]))
    assert second == []


def test_need_surprise_when_z_is_large():
    ext = Extractor()
    ext.step(_row(1, ticks=0, motives=[_motive("fun", 50, "ok")], observed=[_entry(1)]))
    ext.step(_row(2, ticks=10, motives=[_motive("fun", 40, "ok")], observed=[_entry(1)]))
    surprising = ext.step(_row(3, ticks=20, motives=[_motive("fun", 80, "ok")], observed=[_entry(1)]))
    needs = [p for p in surprising if p.kind == "need"]
    assert len(needs) == 1
    assert needs[0].bucket == "ok"
    assert needs[0].surprise >= 2.0
    assert needs[0].urgency == "normal"
    assert ("band", "ok") in needs[0].facts
    assert any(key == "value" for key, _ in needs[0].facts)


def test_interaction_start_end_cancel_and_user_intent():
    ext = Extractor()
    started = ext.step(_row(1, ticks=100, observed=[_entry(14244, text="sit down")]))
    assert [(p.bucket, p.object, p.pressure) for p in started if p.kind == "interaction"] == [
        ("started", "14244", None)]
    assert ("affordance_text", "sit down") in started[0].facts
    ended = ext.step(_row(2, ticks=160, observed=[]))
    end = [p for p in ended if p.kind == "interaction" and p.bucket != "idle"]
    assert len(end) == 1
    assert [p.urgency for p in ended if p.bucket == "idle"] == ["wake"]
    assert end[0].bucket == "ended"
    assert end[0].pressure is None
    assert end[0].surprise == 0.0
    user = Extractor()
    user.step(_row(1, ticks=0, observed=[_entry(
        9, iid="u", source="InteractionSource.SCRIPT_WITH_USER_INTENT")]))
    stopped = user.step(_row(2, ticks=5, observed=[]))
    assert stopped[0].pressure == "action_end"
    cancel = Extractor()
    cancel.step(_row(1, ticks=0, observed=[_entry(
        9, iid="c", source="InteractionSource.BODY_CANCEL_AOP")]))
    cancelled = cancel.step(_row(2, ticks=5, observed=[_entry(
        9, iid="c", membership="QUEUED", source="InteractionSource.BODY_CANCEL_AOP")]))
    assert cancelled[0].bucket == "ended"
    assert cancelled[0].surprise == 3.0


def test_unambiguous_duration_is_recorded_once():
    ext = Extractor()
    ext.step(_row(1, ticks=0, observed=[_entry(7)]))
    ext.step(_row(2, ticks=30, paused=True, observed=[_entry(7)]))
    ext.step(_row(3, ticks=40, observed=[]))
    assert ext.durations.samples.get(7, []) == []
    clean = Extractor()
    clean.step(_row(1, ticks=10, observed=[_entry(8)]))
    clean.step(_row(2, ticks=25, observed=[]))
    assert clean.durations.samples[8] == [15]
    # a sequence hole makes the close ambiguous
    gappy = Extractor()
    gappy.step(_row(1, ticks=0, observed=[_entry(8, iid="g")]))
    percepts = gappy.step(_row(4, ticks=50, observed=[]))
    assert any(p.kind == "gap" for p in percepts)
    assert gappy.durations.samples.get(8, []) == []


def test_posture_and_zone():
    ext = Extractor()
    first = ext.step(_row(1, posture="stand", zone_id=None, lot_id=None))
    assert _kinds(first) == []
    moved = ext.step(_row(2, posture="sit", target="sofa", zone_id=4, lot_id=8))
    posture = [p for p in moved if p.kind == "posture"]
    env = [p for p in moved if p.kind == "env"]
    assert (posture[0].subject, posture[0].object, posture[0].bucket) == ("ASH", "sofa", "sit")
    assert (env[0].subject, env[0].object, env[0].bucket, env[0].urgency) == (
        "zone", "4", "8", "wake")
    same = ext.step(_row(3, posture="sit", target="sofa", zone_id=4, lot_id=8))
    assert [p for p in same if p.kind in ("posture", "env")] == []
    cleared = ext.step(_row(4, posture="sit", target="sofa", zone_id=None, lot_id=None))
    assert [p for p in cleared if p.kind == "env"] == []


def test_gap_and_lineage_reset_models():
    ext = Extractor()
    ext.step(_row(1, ticks=0, motives=[_motive("hunger", 50, "ok")]))
    ext.step(_row(2, ticks=10, motives=[_motive("hunger", 40, "ok")]))
    assert ext.needs.rate("hunger", ()) is not None
    jumped = ext.step(_row(5, ticks=40, motives=[_motive("hunger", 10, "ok")]))
    assert any(p.kind == "gap" and p.urgency == "wake" and p.bucket == "gap" for p in jumped)
    assert ext.needs.rate("hunger", ()) is None
    opened = ext.step(_row(6, kind="session_open", ticks=41))
    assert any(p.kind == "gap" for p in opened)
    lineage = ext.step(_row(
        7, kind="lineage_event", ticks=42,
        e2={"slot_id": "2", "guid": "G", "lineage_class": "load"}))
    lin = [p for p in lineage if p.kind == "lineage"]
    assert (lin[0].subject, lin[0].object, lin[0].bucket, lin[0].urgency) == (
        "2", "G", "load", "wake")
    assert ext.lineage_id == "2:G"
    later = ext.step(_row(8, ticks=50, posture="sleep"))
    assert later[0].lineage == "2:G"
    assert all(p.lineage == "" or p.kind != "lineage" for p in lin)


def test_presence_social_and_owner():
    ext = Extractor(owner_sim_id="OWNER")
    ext.step(_row(1, include_presence=True, presence=[{"id": "A"}], social=[]))
    arrived = ext.step(_row(
        2, include_presence=True,
        presence=[{"id": "A"}, {"id": "B"}],
        social=[{
            "entry_key": "s1", "target_id": "ASH", "affordance_id": 99,
            "source_sim": "OWNER",
        }]))
    presence = [p for p in arrived if p.kind == "presence"]
    social = [p for p in arrived if p.kind == "social"]
    assert [(p.subject, p.bucket) for p in presence] == [("B", "arrived")]
    assert (social[0].subject, social[0].object, social[0].bucket, social[0].urgency) == (
        "OWNER", "99", "addressed", "always_through")
    left = ext.step(_row(3, include_presence=True, presence=[], social=[]))
    assert sorted((p.subject, p.bucket) for p in left if p.kind == "presence") == [
        ("A", "left"), ("B", "left")]
    # schema without the keys does not invent presence percepts
    bare = Extractor()
    bare.step(_row(1))
    assert bare.step(_row(2, posture="sit"))[0].kind == "posture"


def test_a_left_sim_is_named_with_her_last_room_even_after_a_restart():
    # HE3: "left" carries who and where; the names survive the extractor's saved state.
    ext = Extractor(owner_sim_id="OWNER")
    ext.step(_row(1, include_presence=True, presence=[{"id": "A", "name": "Ada", "room": "Kitchen"}], social=[]))
    restored = Extractor.from_dict(json.loads(json.dumps(ext.to_dict())))
    left = restored.step(_row(2, include_presence=True, presence=[], social=[]))
    gone = [p for p in left if p.kind == "presence" and p.bucket == "left"]
    assert [(p.subject, dict(p.facts)) for p in gone] == [("A", {"ticks": "100", "name": "Ada", "room": "Kitchen"})]


def test_a_sequence_gap_says_how_many_rows_were_lost():
    # HE16: the gap percept carries the lost-row count (the sequence numbers skipped).
    ext = Extractor(owner_sim_id="OWNER")
    ext.step(_row(1, include_presence=True, presence=[], social=[]))
    gaps = [p for p in ext.step(_row(5, include_presence=True, presence=[], social=[])) if p.bucket == "gap"]
    assert [dict(p.facts)["lost"] for p in gaps] == ["3"]


def test_facts_stay_under_the_wire_cap():
    ext = Extractor()
    text = "x" * 5000
    percepts = ext.step(_row(1, observed=[_entry(1, text=text)]))
    encoded = json.dumps(percepts[0].facts).encode("utf-8")
    assert len(encoded) <= 2048
    assert len(percepts[0].facts) <= 4
    text_fact = dict(percepts[0].facts)["affordance_text"]
    assert len(text_fact) <= 120


def test_percept_lineage_on_need_after_lineage():
    ext = Extractor()
    ext.step(_row(1, kind="lineage_event", e2={
        "slot_id": 3, "guid": "abc", "lineage_class": "fresh"}))
    ext.step(_row(2, ticks=1, motives=[_motive("bladder", 80, "ok")]))
    changed = ext.step(_row(3, ticks=2, motives=[_motive("bladder", 40, "low")]))
    assert changed[0].lineage == "3:abc"
    assert isinstance(changed[0], Percept)


def test_interaction_origin_marks_the_bodys_own_actions():
    """Owner ruling (DA6F O1): the game's distress reflex is her body acting, reported
    as origin native_autonomy, not as an error; her pushed actions are script."""
    ext = Extractor()
    started = ext.step(_row(1, ticks=0, observed=[
        _entry(13993, iid="d", text="sim_BladderDistress"),
        _entry(13949, iid="s", source="InteractionSource.SCRIPT_WITH_USER_INTENT"),
        _entry(1, iid="p", source="InteractionSource.PIE_MENU"),
        _entry(2, iid="g", source="InteractionSource.POSTURE_GRAPH"),
        _entry(3, iid="r", source="InteractionSource.SCRIPT")]))
    origins = {p.object: dict(p.facts)["origin"] for p in started if p.kind == "interaction"}
    assert origins == {"13993": "native_autonomy", "13949": "script", "1": "pie_menu",
                       "2": "game", "3": "native_reaction"}
    ended = ext.step(_row(2, ticks=5, observed=[]))
    assert {p.object: dict(p.facts)["origin"] for p in ended if p.kind == "interaction" and p.bucket != "idle"} == origins


def test_ds3_presence_facts_skip_her_body_and_room_moves():
    """DS3 (schema 6): her own body is listed but never arrives; an arrival carries
    who and where; moving rooms is an env percept."""
    ext = Extractor()
    body = {"id": "100", "is_body": True, "name": "E1 Proband", "room": "3"}
    bella = {"id": "200", "is_body": False, "name": "Bella Goth", "room": "3",
             "distance_m": 1.0, "doing": "<class 'social_Chat'>"}
    first = ext.step(_row(1, include_presence=True, presence=[body], social=[],
                          extra={"zone": {"zone_id": "1", "lot_id": "9", "room": "3",
                                          "position": None}}))
    assert [p for p in first if p.kind == "presence"] == []
    second = ext.step(_row(2, include_presence=True, presence=[body, bella], social=[],
                           extra={"zone": {"zone_id": "1", "lot_id": "9", "room": "4",
                                           "position": None}}))
    arrived = [p for p in second if p.kind == "presence"]
    assert [(p.subject, p.bucket) for p in arrived] == [("200", "arrived")]
    facts = dict(arrived[0].facts)
    assert facts["name"] == "Bella Goth" and facts["room"] == "3"
    assert facts["distance_m"] == "1.0" and facts["doing"] == "<class 'social_Chat'>"
    room = [p for p in second if p.kind == "env" and p.subject == "room"]
    assert [(p.object, dict(p.facts)["from_room"]) for p in room] == [("4", "3")]


def test_someone_stepping_onto_her_lot_wakes_her_with_their_situation():
    """2.17.0 (live 2026-10-06): the welcome wagon walked from the street to her door and
    waited, ungreeted, while she stood at the mirror. The step onto the lot wakes her."""
    ext = Extractor()
    body = {"id": "100", "is_body": True, "name": "E1 Proband", "room": "3"}
    street = {"id": "300", "name": "Dennis Kim", "room": "0", "distance_m": 40.0, "on_lot": False}
    zone = {"zone": {"zone_id": "1", "lot_id": "9", "room": "3", "position": None}}
    ext.step(_row(1, include_presence=True, presence=[body, street], social=[], extra=zone))
    door = dict(street, distance_m=6.8, on_lot=True, situations=[
        {"situation": "situation_welcomeWagon", "role": "Role_welcomeWagon_WelcomingNeighbor_Wait_Ungreeted"}])
    second = ext.step(_row(2, include_presence=True, presence=[body, door], social=[], extra=zone))
    came = [p for p in second if p.kind == "presence" and p.bucket == "on_lot"]
    assert [(p.subject, p.urgency) for p in came] == [("300", "wake")]
    assert dict(came[0].facts)["role"] == "Role_welcomeWagon_WelcomingNeighbor_Wait_Ungreeted"
    third = ext.step(_row(3, include_presence=True, presence=[body, door], social=[], extra=zone))
    assert [p for p in third if p.kind == "presence"] == []


def test_a_new_save_is_its_own_world_and_nothing_is_compared_across_sessions():
    """D51 (live 2026-10-05): after a switch from the lab fork to her home save, the first
    observation still said slot0 and four lab Sims "left" her new home."""
    lab = [{"id": "LAB1", "name": "Summer"}, {"id": "LAB2", "name": "Travis"}]
    ex = Extractor()
    ex.step(_row(0, kind="session_open", session="lab", extra={"save": {"slot_id": "0", "save_slot_guid": "111"}}))
    ex.step(_row(1, session="lab", include_presence=True, presence=lab, zone_id=1, lot_id=9))
    ex.step(_row(2, kind="lineage_event", session="lab", e2={"slot_id": 0, "guid": 111, "lineage_class": "X"}))
    assert (ex.slot_id, ex.guid) == (0, 111)
    home = [{"id": "N1", "name": "Dennis"}]
    first = ex.step(_row(0, kind="session_open", session="home", zone_id=5, lot_id=7, posture="sit",
                         include_presence=True, presence=home,
                         extra={"save": {"slot_id": "8", "save_slot_guid": "222"}}))
    assert (ex.slot_id, ex.guid, ex.lineage_class) == ("8", "222", "")
    assert ex.lineage_id == "8:222"
    buckets = [(p.kind, p.bucket) for p in first]
    assert ("presence", "left") not in buckets
    assert ("presence", "arrived") in buckets
    assert not [p for p in first if p.kind in ("posture", "env")]
    # The same save again (a relaunch) keeps its lineage class.
    ex.step(_row(1, kind="lineage_event", session="home", e2={"slot_id": 8, "guid": 222, "lineage_class": "Y"}))
    ex.step(_row(0, kind="session_open", session="home2", extra={"save": {"slot_id": "8", "save_slot_guid": "222"}}))
    assert ex.lineage_class == "Y"


def test_a_question_the_game_asks_her_wakes_her_once():
    """2.19.0 (live 2026-10-06): a work event asked her to nuke or remake a dish; the game
    paused for her answer and nothing woke her."""
    ext = Extractor()
    asked = {"dialogs": {"open": [
        {"dialog_id": "3", "owner_id": "ASH", "title_key": "1474017446", "auto_respond": False},
        {"dialog_id": "4", "owner_id": "OTHER", "title_key": "1", "auto_respond": False},
        {"dialog_id": "5", "owner_id": None, "title_key": "2", "auto_respond": True}]}}
    ext.step(_row(1))
    first = [p for p in ext.step(_row(2, extra=asked)) if p.subject == "dialog"]
    assert [(p.kind, p.object, p.bucket, p.urgency) for p in first] == [("env", "3", "asked", "wake")]
    assert dict(first[0].facts)["title_key"] == "1474017446"
    assert [p for p in ext.step(_row(3, extra=asked)) if p.subject == "dialog"] == []
    restored = Extractor.from_dict(json.loads(json.dumps(ext.to_dict())))
    assert [p for p in restored.step(_row(4, extra=asked)) if p.subject == "dialog"] == []
    ext.step(_row(5, extra={"dialogs": {"open": []}}))
    again = [p for p in ext.step(_row(6, extra=asked)) if p.subject == "dialog"]
    assert [p.object for p in again] == ["3"]
