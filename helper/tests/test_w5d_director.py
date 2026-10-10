"""2.32.0 (HE14): the director stops the game's follow once when the User's hand comes to the controls, and turns the
camera to her when a pop-up newly opens or a need newly falls to distress."""
from domus_helper.director import HOLD_MS, IDLE_MS, MIN_GAP_MS, Director
from domus_helper.spool import Spool

HER = "111"


def _row(dialogs=None, motives=None, others=()):
    people = [{"id": HER, "is_body": True, "on_lot": True}, *others]
    row = {"event_kind": "presence_snapshot", "body": {"sim_id": HER}, "presence": people}
    if dialogs is not None:
        row["dialogs"] = {"open": [{"dialog_id": item} for item in dialogs], "closed": []}
    if motives is not None:
        row["motives"] = [{"id": name, "band": band} for name, band in motives]
    return row


def _director(tmp_path, idle):
    sent = []
    state = {"idle": idle}
    spool = Spool(tmp_path / "spool.db")
    made = Director(spool, lambda command, args: sent.append((command, args)), idle=lambda: state["idle"])
    return made, sent, state, spool


def test_the_first_input_tick_after_following_sends_one_unfollow(tmp_path):
    made, sent, state, spool = _director(tmp_path, 3500)
    made.on_row(_row(), 1_000)
    made.tick(1_000, True)
    assert sent == [("camera", {"op": "follow_sim", "target_id": HER})]
    state["idle"] = 0
    made.tick(1_000 + MIN_GAP_MS, True)
    made.tick(1_000 + MIN_GAP_MS + 500, True)
    assert sent[-1] == ("camera", {"op": "unfollow", "target_id": HER})
    assert [command for command, args in sent].count("camera") == 2
    spool.close()


def test_no_unfollow_when_she_was_never_followed(tmp_path):
    made, sent, state, spool = _director(tmp_path, 0)
    made.on_row(_row(), 1_000)
    made.tick(1_000, True)
    assert sent == []
    spool.close()


def test_a_newly_open_pop_up_turns_the_camera_to_her_once(tmp_path):
    made, sent, state, spool = _director(tmp_path, 3500)
    made.on_row(_row(dialogs=[]), 1_000)
    made.on_row(_row(dialogs=["7"]), 2_000)
    made.on_row(_row(dialogs=["7"]), 3_000)
    made.tick(2_000, True)
    assert sent == [("camera", {"op": "follow_sim", "target_id": HER})]
    assert made._cut == ("follow_sim", HER, 2_000 + HOLD_MS)
    spool.close()


def test_a_need_newly_at_distress_turns_the_camera_to_her(tmp_path):
    made, sent, state, spool = _director(tmp_path, 3500)
    made.on_row(_row(motives=[("hunger", "ok")]), 1_000)
    made.on_row(_row(motives=[("hunger", "distress")]), 2_000)
    assert made._cut == ("follow_sim", HER, 2_000 + HOLD_MS)
    made.on_row(_row(motives=[("hunger", "distress")]), 3_000)
    assert made._cut == ("follow_sim", HER, 2_000 + HOLD_MS)
    spool.close()


def test_the_first_row_is_not_a_trigger(tmp_path):
    made, sent, state, spool = _director(tmp_path, 3500)
    made.on_row(_row(dialogs=["7"], motives=[("hunger", "distress")]), 1_000)
    assert made._cut is None
    spool.close()


def test_the_probe_accepts_the_unfollow_op_the_director_sends(tmp_path):
    import json
    from domus_helper.vendor import cmdbox
    base = {"v": 1, "id": "e" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
            "issuer": "helper", "command": "camera"}
    body = json.dumps(dict(base, args={"op": "unfollow", "target_id": HER})).encode("utf-8")
    assert cmdbox.parse(body, 1500, set())[1] is None
    made, sent, state, spool = _director(tmp_path, 3500)
    made.on_row(_row(), 1_000)
    made.tick(1_000, True)
    state["idle"] = 0
    made.tick(1_000 + 2 * MIN_GAP_MS, True)
    assert sent[-1][1]["op"] == "unfollow"
    spool.close()
