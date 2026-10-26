"""E5: the camera director follows her when the overlay is live and the User is quiet."""
import pytest

from domus_helper.director import HOLD_MS, IDLE_MS, MIN_GAP_MS, Director, idle_ms
from domus_helper.spool import Spool

HER = "111"


def presence(*others, her=HER):
    people = [{"id": her, "is_body": True, "on_lot": True}]
    people.extend(others)
    return {"event_kind": "presence_snapshot", "body": {"sim_id": her}, "presence": people}


def director(tmp_path, idle_value):
    sent = []

    def publish(command, args):
        sent.append((command, args))

    state = {"idle": idle_value}
    spool = Spool(tmp_path / "spool.db")
    made = Director(spool, publish, idle=lambda: state["idle"])
    return made, sent, state, spool


def test_quiet_and_live_are_both_required(tmp_path):
    made, sent, state, spool = director(tmp_path, IDLE_MS + 500)
    made.on_row(presence(), 1_000)
    assert made.tick(1_000, False) is None
    assert sent == []
    state["idle"] = 500
    assert made.tick(1_000, True) is None
    assert sent == []
    spool.close()


def test_one_follow_per_quiet_period(tmp_path):
    made, sent, state, spool = director(tmp_path, 3500)
    made.on_row(presence(), 5_000)
    assert made.tick(5_000, True) == ("follow_sim", HER)
    assert sent == [("camera", {"op": "follow_sim", "target_id": HER})]
    assert made.tick(6_000, True) is None
    assert made.tick(9_000, True) is None
    assert len(sent) == 1
    spool.close()


def test_a_new_quiet_period_follows_again(tmp_path):
    made, sent, state, spool = director(tmp_path, 3500)
    made.on_row(presence(), 5_000)
    made.tick(5_000, True)
    state["idle"] = 200
    assert made.tick(6_000, True) is None
    state["idle"] = 3200
    assert made.tick(5_000 + MIN_GAP_MS, True) == ("follow_sim", HER)
    assert len(sent) == 2
    spool.close()


def test_a_pushed_act_cuts_to_its_object_then_back(tmp_path):
    made, sent, state, spool = director(tmp_path, 3500)
    made.on_row(presence(), 10_000)
    made.tick(10_000, True)
    made.on_row({"event_kind": "act_event", "e2": {"phase": "ACCEPTED", "object_id": "555"}}, 11_000)
    made.on_row({"event_kind": "act_event", "e2": {"phase": "FINISHED", "object_id": "555"}}, 11_000)
    assert made.tick(11_000, True) is None
    made.on_row({"event_kind": "act_event", "e2": {"phase": "PUSHED", "object_id": "555"}}, 11_000)
    assert made.tick(11_000, True) is None
    assert made.tick(10_000 + MIN_GAP_MS, True) == ("focus_object", "555")
    assert made.tick(11_000 + HOLD_MS, True) == ("follow_sim", HER)
    spool.close()


def test_an_arrival_on_her_lot_is_a_cut(tmp_path):
    made, sent, state, spool = director(tmp_path, 4000)
    made.on_row(presence({"id": "222", "is_body": False, "on_lot": True}), 1_000)
    made.tick(1_000, True)
    assert sent[0][1]["target_id"] == HER
    made.on_row(presence(
        {"id": "222", "is_body": False, "on_lot": True},
        {"id": "333", "is_body": False, "on_lot": True},
    ), 1_000 + MIN_GAP_MS)
    assert made.tick(1_000 + MIN_GAP_MS, True) == ("follow_sim", "333")
    assert made.tick(1_000 + MIN_GAP_MS + HOLD_MS, True) == ("follow_sim", HER)
    before = len(sent)
    made.on_row(presence({"id": "444", "is_body": False, "on_lot": False}), 20_000)
    made.tick(20_000, True)
    assert len(sent) == before
    spool.close()


def test_the_switch_stops_and_starts_it(tmp_path):
    made, sent, state, spool = director(tmp_path, 4000)
    made.on_row(presence(), 1_000)
    spool.put_kv("director", "off")
    assert made.tick(1_000, True) is None
    assert sent == []
    spool.put_kv("director", "on")
    assert made.tick(1_000, True) == ("follow_sim", HER)
    spool.close()


def test_two_targets_inside_the_gap_send_the_first_then_the_second(tmp_path):
    made, sent, state, spool = director(tmp_path, 4000)
    made.on_row(presence(), 0)
    made.tick(0, True)
    made.on_row({"event_kind": "act_event", "e2": {"phase": "PUSHED", "object_id": "555"}}, 500)
    assert made.tick(500, True) is None
    assert len(sent) == 1
    assert made.tick(MIN_GAP_MS, True) == ("focus_object", "555")
    spool.close()


def test_a_failed_publish_stays_inside_tick(tmp_path):
    spool = Spool(tmp_path / "spool.db")

    def publish(command, args):
        raise OSError("full")

    made = Director(spool, publish, idle=lambda: 4000)
    made.on_row(presence(), 1_000)
    assert made.tick(1_000, True) is None
    assert made.last == "publish failed"
    spool.close()


def test_idle_ms_on_this_machine():
    value = idle_ms()
    assert value is None or (type(value) is int and value >= 0)
