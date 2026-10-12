"""R3 (helper, Worker H): the menu merge rule after a near part (every object of the whole menu the near part does not test is
kept, with its room flag judged against the near part's room), a first-build partial menu as the merge base (R1), the zone of
a menu (R2), the choices that are pending until a final whole of the session (S2), and the choices reason of the coalescer
(SEAM3-7). Every row is invented; the game and Mint are fakes."""
import pytest

from domus_helper import coalesce
from domus_helper.acts import MenuParts, merge_near
from test_bridge_thalamus import WALL, _bridge, _data, _lineage, _snap
from test_w14_helper import _append, _ids, _menu, _menu_row, _obj, _tick


def _room_obj(object_id, room, distance=None, same_room=None, phone=None):
    item = _obj(object_id, distance, same_room, phone)
    item["room"] = str(room)
    return item


def _zoned(payload, zone):
    payload["zone_id"] = str(zone)
    return payload


# ----------------------------------------------------------------- the merge rule

def test_a_near_part_after_a_room_move_keeps_the_objects_of_the_room_she_left_as_elsewhere():
    whole = _menu(5, [_room_obj(11, 1, 1.0, True), _room_obj(22, 2, 9.0, False)])
    near = _menu(6, [_room_obj(44, 2, 1.0, True)], near=True)
    near["room"] = "2"
    shown = merge_near(near, whole)
    assert _ids(shown) == ["44", "11", "22"]
    old, far = shown["objects"][1], shown["objects"][2]
    assert old["same_room"] is False and old["distance_m"] is None  # the room she left: not here, no stale distance
    assert far["same_room"] is True and far["distance_m"] is None  # her new room now: the whole's distance is stale


def test_an_object_with_no_distance_in_the_whole_is_kept_by_a_near_part():
    whole = _menu(5, [_room_obj(33, 9, None, False)])
    shown = merge_near(_menu(6, [_room_obj(44, 4, 2.0, True)], near=True), whole)
    assert _ids(shown) == ["44", "33"]
    assert shown["objects"][1]["distance_m"] is None


def test_a_near_part_written_mid_build_keeps_the_same_room_objects_it_has_not_tested():
    whole = _menu(5, [_room_obj(11, 4, 1.0, True), _room_obj(22, 4, 2.5, True)])
    near = _menu(6, [_room_obj(44, 4, 0.5, True)], near=True)
    shown = merge_near(near, whole)
    assert _ids(shown) == ["44", "11", "22"]
    assert all(item["distance_m"] is None for item in shown["objects"][1:])


def test_the_merged_menu_takes_the_dropped_count_of_the_whole_menu():
    whole = _menu(5, [_room_obj(11, 4, 1.0, True)], dropped={"objects": 3, "rooms": ["2"]})
    shown = merge_near(_menu(6, [_room_obj(44, 4, 0.5, True)], near=True, dropped={"objects": 1}), whole)
    assert shown["dropped"] == {"objects": 3, "rooms": ["2"]}


def test_a_near_part_of_another_zone_is_the_near_part_alone():
    whole = _zoned(_menu(5, [_room_obj(22, 2, 9.0, False)]), 1)
    near = _zoned(_menu(6, [_room_obj(44, 4, 1.0, True)], near=True), 2)
    assert _ids(merge_near(near, whole)) == ["44"]
    same = _zoned(_menu(6, [_room_obj(44, 4, 1.0, True)], near=True), 1)
    assert _ids(merge_near(same, whole)) == ["44", "22"]


# ----------------------------------------------------------------- R1: the first build's partial menu

def test_a_partial_set_is_its_own_set_and_never_mixes_with_a_whole_of_the_same_revision():
    parts = MenuParts()
    assert parts.take("s", _menu(5, [_room_obj(11, 4)], part=0, parts=2, partial=True)) is None
    assert parts.take("s", _menu(5, [_room_obj(22, 4)], part=0, parts=1)) is not None
    whole = parts.take("s", _menu(5, [_room_obj(33, 4)], part=0, parts=2, partial=True))
    assert whole is None
    shown = parts.take("s", _menu(5, [_room_obj(44, 4)], part=1, parts=2, partial=True))
    assert _ids(shown) == ["33", "44"] and shown["partial"] is True


def test_the_bridge_shows_a_partial_menu_and_a_near_part_merges_with_it_while_the_choices_stay_pending(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL),
                    _menu_row(2, _menu(5, [_room_obj(11, 4, 1.0, True)], part=0, parts=2, partial=True)),
                    _menu_row(3, _menu(5, [_room_obj(22, 4, 2.0, True)], part=1, parts=2, partial=True))])
    _tick(bridge, mono, WALL)
    assert _ids(bridge._menu["payload"]) == ["11", "22"]
    assert "partial" not in bridge._menu["payload"]
    assert bridge._obs_ctx(WALL)["choices_pending"] is True
    _append(paths, [_menu_row(4, _menu(6, [_room_obj(33, 4, 0.5, True)], near=True))])
    _tick(bridge, mono, WALL + 1500)
    assert _ids(bridge._menu["payload"]) == ["33", "11", "22"]
    assert bridge._obs_ctx(WALL + 1500)["choices_pending"] is True
    _append(paths, [_menu_row(5, _menu(7, [_room_obj(55, 4, 1.0, True)]))])
    _tick(bridge, mono, WALL + 3000)
    assert bridge._obs_ctx(WALL + 3000)["choices_pending"] is False


def test_a_final_whole_menu_restored_after_a_restart_ends_the_pending_choices_and_a_partial_does_not(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _menu_row(2, _menu(5, [_room_obj(11, 4, 1.0, True)], part=0, parts=1, partial=True))])
    _tick(bridge, mono, WALL)
    bridge._persist_thalamus(WALL + 1000)
    again = _bridge(paths, mono)
    _tick(again, mono, WALL + 1500)
    assert _ids(again._menu["payload"]) == ["11"]
    assert again._obs_ctx(WALL + 2000)["choices_pending"] is True
    _append(paths, [_menu_row(3, _menu(6, [_room_obj(11, 4, 1.0, True)]))])
    _tick(again, mono, WALL + 2500)
    again._persist_thalamus(WALL + 3000)
    third = _bridge(paths, mono)
    _tick(third, mono, WALL + 3500)
    assert third._obs_ctx(WALL + 3500)["choices_pending"] is False


# ----------------------------------------------------------------- R2: the zone of a menu

def test_a_near_part_of_a_new_zone_drops_the_old_zones_whole_menu(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _menu_row(2, _zoned(_menu(5, [_room_obj(22, 2, 9.0, False)]), 1))])
    _tick(bridge, mono, WALL)
    _append(paths, [_menu_row(3, _zoned(_menu(6, [_room_obj(44, 4, 1.0, True)], near=True), 2))])
    _tick(bridge, mono, WALL + 1500)
    assert _ids(bridge._menu["payload"]) == ["44"]
    assert bridge._whole_menu is None
    _append(paths, [_menu_row(4, _zoned(_menu(7, [_room_obj(66, 4, 1.0, True)], near=True), 2))])
    _tick(bridge, mono, WALL + 3000)
    assert _ids(bridge._menu["payload"]) == ["66"]


# ----------------------------------------------------------------- SEAM3-7: the choices reason

def test_the_coalescer_sends_a_view_at_once_for_the_choices():
    assert coalesce.due(coalesce.Pending(), WALL, choices=True) == coalesce.CHOICES
    assert coalesce.due(coalesce.Pending(), WALL) is None


def test_a_whole_menu_sends_the_choices_once_and_again_only_when_its_act_list_changes(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    first = _menu(5, [_room_obj(11, 4, 1.0, True)])
    bridge._menu_shown("sess-1", dict(first), WALL)
    assert bridge._choices_due is True
    bridge._choices_due = False
    bridge._choices_sent = bridge._whole_menu["key"]  # what a view that carried these choices leaves behind
    bridge._menu_shown("sess-1", dict(first, menu_rev=6), WALL + 1)
    assert bridge._choices_due is False  # the same acts again: nothing new to say about the choices
    changed = _menu(7, [_room_obj(11, 4, 1.0, True), _room_obj(22, 4, 2.0, True)])
    bridge._menu_shown("sess-1", changed, WALL + 2)
    assert bridge._choices_due is True
    bridge._menu_shown("sess-2", dict(first), WALL + 3)
    assert bridge._choices_due is True  # a new session's first whole


# SEAM3-8: a look's view waits for the near part it asked for, or three seconds.
def test_a_look_waits_for_the_near_part_it_asked_for_and_sends_after_three_seconds(paths, tmp_path, monkeypatch):
    from domus_helper import commands as commands_module
    _data(paths, tmp_path, monkeypatch)
    sent = []
    monkeypatch.setattr(commands_module, "publish", lambda command, args, issuer, paths=None: sent.append(command))
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _snap(2, "ok", WALL, 10), _menu_row(3, _menu(5, [_room_obj(11, 4, 1.0, True)]))])
    _tick(bridge, mono, WALL)
    fires = bridge._fires
    bridge._send_look(WALL + 1000)
    assert "menu_near" in sent and bridge._fires == fires
    _tick(bridge, mono, WALL + 1500)
    assert bridge._fires == fires  # no near part yet: the look still holds
    _append(paths, [_menu_row(4, _menu(6, [_room_obj(44, 4, 1.0, True)], near=True))])
    _tick(bridge, mono, WALL + 2000)
    assert bridge._fires == fires + 1 and bridge._look_hold is None
    bridge._send_look(WALL + 5000)
    _tick(bridge, mono, WALL + 7000)
    assert bridge._fires == fires + 1 and bridge._look_hold is not None
    _tick(bridge, mono, WALL + 8100)
    assert bridge._fires == fires + 2 and bridge._look_hold is None


# ----------------------------------------------------------------- her thoughts in the game (HELPER3-5/6/7/12/20)

def _chosen(pass_id, line, at_ms=None):
    return {"inputs": "chosen", "pass": pass_id, "line": line, "at_ms": at_ms}


class _Feed(object):
    def __init__(self, items):
        self.items = items

    def post_feed(self, body):
        return {"status": "ok", "items": self.items}


W14_NOW = 1_800_000_000_000


def _overlay(tmp_path, now_ms):
    from domus_helper import overlay
    from domus_helper.spool import Spool
    spool = Spool(tmp_path / "spool.db")
    return spool, overlay.Overlay(spool, tmp_path, now_ms - overlay.HUMAN_HAND_MS - 1)


def test_a_line_said_before_a_restart_is_not_said_again_after_it(tmp_path):
    from domus_helper import overlay
    spool, view = _overlay(tmp_path, W14_NOW)
    try:
        view.poll(_Feed([_chosen("p1", "The toast smells good.", W14_NOW - 1000)]), "h1", W14_NOW)
        assert view.take_thoughts() == ["The toast smells good."]
        again = overlay.Overlay(spool, tmp_path, W14_NOW - overlay.HUMAN_HAND_MS - 1)
        again.poll(_Feed([_chosen("p1", "The toast smells good.", W14_NOW - 1000)]), "h1",
                   W14_NOW + overlay.FEED_EVERY_MS)
        assert again.take_thoughts() == []
    finally:
        spool.close()


def test_the_said_pass_ids_are_kept_to_the_last_two_hundred(tmp_path):
    import json
    from domus_helper import overlay
    spool, view = _overlay(tmp_path, W14_NOW)
    try:
        for index in range(overlay.SAID_LIMIT + 5):
            view.poll(_Feed([_chosen("p%d" % index, "Line %d." % index, W14_NOW - 1000)]), "h1",
                      W14_NOW + index * overlay.FEED_EVERY_MS)
            view.take_thoughts()
        kept = json.loads(spool.get_kv(overlay.SAID_KEY))
        assert len(kept) == overlay.SAID_LIMIT and kept[-1] == "p%d" % (overlay.SAID_LIMIT + 4) and kept[0] == "p5"
    finally:
        spool.close()


def test_the_curtain_on_means_nothing_of_hers_is_said_in_the_game(tmp_path):
    from domus_helper import overlay
    spool, view = _overlay(tmp_path, W14_NOW)
    try:
        spool.put_kv(overlay.CURTAIN_KEY, "on")
        view.poll(_Feed([_chosen("p1", "Hidden line.", W14_NOW - 1000)]), "h1", W14_NOW)
        assert view.take_thoughts() == []
        spool.put_kv(overlay.CURTAIN_KEY, "off")
        view.poll(_Feed([_chosen("p1", "Hidden line.", W14_NOW - 1000)]), "h1", W14_NOW + overlay.FEED_EVERY_MS)
        assert view.take_thoughts() == []  # said once or not at all: the curtain's pass is not a new one later
    finally:
        spool.close()


def test_the_passes_seen_in_one_process_are_capped(tmp_path):
    from domus_helper import overlay
    spool, view = _overlay(tmp_path, W14_NOW)
    try:
        for index in range(overlay.PASSES_SEEN_LIMIT + 10):
            view._accept([_chosen("q%d" % index, "x", W14_NOW - 1000)], W14_NOW, False)
        assert len(view._passes_seen) == overlay.PASSES_SEEN_LIMIT
    finally:
        spool.close()


def test_a_line_waits_in_the_overlay_while_her_sim_id_is_unknown(paths, tmp_path, monkeypatch):
    from test_bridge_thalamus import _Client
    _data(paths, tmp_path, monkeypatch)

    class _FeedClient(_Client):
        def __init__(self, items):
            self.items = items

        def post_feed(self, body):
            return {"status": "ok", "items": self.items}

    mono = {"ms": WALL}
    bridge = _bridge(paths, mono, client=_FeedClient([_chosen("p9", "Waiting line.", WALL - 1000)]))
    said = []
    bridge.talk.say = lambda text, sim_id=None: said.append((text, sim_id))
    _append(paths, [_lineage(1, WALL)])
    _tick(bridge, mono, WALL)
    assert said == []
    snap = _snap(2, "ok", WALL + 100, 10)
    snap["body"]["sim_id"] = "118245043779534862"
    _append(paths, [snap])
    _tick(bridge, mono, WALL + 200)
    assert said == [("Waiting line.", "118245043779534862")]


def _talk_reply(lines, command_id):
    return {"id": command_id, "status": "REJECTED", "code": None, "result": {"ok": False, "lines": lines}}


def test_a_talk_line_the_probe_refuses_as_too_soon_is_sent_once_more_and_no_more(tmp_path):
    from domus_helper.talk import Talk
    sent, replies = [], {}

    def publish(command, args):
        sent.append(args["text"])
        command_id = "c%d" % len(sent)
        replies[command_id] = _talk_reply(["TALK_REJECT TOO_SOON"], command_id)
        return command_id

    from domus_helper.spool import Spool
    spool = Spool(tmp_path / "spool.db")
    talk = Talk(spool, publish, reply=lambda command_id: replies.get(command_id))
    try:
        talk.say("First line.", sim_id="7")
        talk.tick(WALL, True)
        talk.tick(WALL + 3000, True)  # the refusal is read: the line goes once more
        talk.tick(WALL + 6000, True)
        talk.tick(WALL + 9000, True)
        assert sent == ["First line.", "First line."]
    finally:
        spool.close()


def test_a_talk_line_the_probe_accepts_is_not_sent_again_and_one_with_no_answer_is_given_up(tmp_path):
    from domus_helper.talk import REPLY_WAIT_MS, Talk
    from domus_helper.spool import Spool
    sent, replies = [], {}

    def publish(command, args):
        sent.append(args["text"])
        command_id = "c%d" % len(sent)
        if len(sent) == 1:
            replies[command_id] = _talk_reply(["TALK_OK"], command_id)
        return command_id

    spool = Spool(tmp_path / "spool.db")
    talk = Talk(spool, publish, reply=lambda command_id: replies.get(command_id))
    try:
        talk.say("Accepted.", sim_id="7")
        talk.say("Never answered.", sim_id="7")
        talk.tick(WALL, True)
        talk.tick(WALL + 3000, True)  # the answer to the first line is read, and the second goes
        assert sent == ["Accepted.", "Never answered."]
        talk.tick(WALL + 6000, True)  # no answer to the second: it is given up after the wait, and never sent again
        talk.tick(WALL + 6000 + REPLY_WAIT_MS, True)
        talk.tick(WALL + 9000 + REPLY_WAIT_MS, True)
        assert sent == ["Accepted.", "Never answered."]
    finally:
        spool.close()


# ----------------------------------------------------------------- HELPER3-10: a bad row never ends the bridge

_JUNK = (None, 0, 1, -1, "", "x", [], [1, "a"], {}, {"a": 1}, True, 2.5)
_KEYS = ("event_kind", "body", "presence", "dialogs", "interactions", "e2", "pace", "telemetry_session_id",
         "wall_timestamp_ms", "zone", "probe_version", "written_sequence")


@pytest.mark.parametrize("seed", [20261012, 7, 99])
def test_a_fuzz_of_bad_rows_never_ends_the_bridge_and_each_row_is_passed_over(paths, tmp_path, monkeypatch, seed):
    import random
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    rng = random.Random(seed)
    bases = [_lineage(1, WALL), _snap(2, "ok", WALL, 10), _menu_row(3, _menu(5, [_room_obj(11, 4, 1.0, True)])),
             _menu_row(4, _menu(6, [_room_obj(12, 4, 1.0, True)], near=True))]
    rows = []
    for index in range(240):
        row = dict(rng.choice(bases))
        for _ in range(rng.randint(1, 3)):
            row[rng.choice(_KEYS)] = rng.choice(_JUNK)
        if rng.random() < 0.3:
            row["e2"] = {"objects": rng.choice(_JUNK), "parts": rng.choice(_JUNK), "part": rng.choice(_JUNK),
                         "near": rng.choice(_JUNK), "menu_rev": rng.choice(_JUNK)}
        rows.append(row)
    _append(paths, rows)
    _tick(bridge, mono, WALL)
    _tick(bridge, mono, WALL + 1000)
    assert bridge._last_rowid == bridge.spool.row_count()
    _append(paths, [_snap(900, "low", WALL + 2000, 20)])
    _tick(bridge, mono, WALL + 2000)
    assert bridge._last_rowid == bridge.spool.row_count()
