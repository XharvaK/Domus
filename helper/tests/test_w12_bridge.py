"""2.39.0 (W12 helper, the bridge side): her words to a Sim go out as one talk line (S2), the refs follow the game and
not the attach flip (B2), a view waits for the acts round trip and is not sent from a restored old row (F1, F3), a
refused view's changes go back in the queue (F4), the spot stages reach the decision log (C11), a look asks for the
near part on a probe that has it (C1), a menu keeps its part-zero facts (C8, C11), and the command folder keeps seven
days (F6). Every row is invented; the game and Mint are fakes."""
import json
import os
from types import SimpleNamespace

from domus_helper import coalesce
from domus_helper import commands as commands_module
from domus_helper.acts import ActCourier, MenuParts
from domus_helper.bridge import REQUEUE_LIMIT, STALE_BODY_MS
from domus_helper.commands import prune_done
from domus_helper.contract import ContractError
from domus_helper.spool import Spool
from domus_helper.talk import Talk
from domus_helper.thalamus.types import Percept
from test_bridge_thalamus import WALL, _append, _bridge, _data, _lineage, _log_lines

ACT_ID = "d" * 32


class _Mint:
    def __init__(self, acts=()):
        self.acts = list(acts)
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        return {"status": "ok", "applied": len(body["events"]), "acts": list(self.acts)}


def _requested(**extra):
    act = {"act_id": ACT_ID, "object_id": "11", "guid64": "4242"}
    act.update(extra)
    return act


def _pushed(at=5000):
    return {"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": at,
            "e2": {"act_id": ACT_ID, "phase": "PUSHED", "tuning_name": "bookshelf_ReadBook"}}


def _refusing(bridge, error):
    def refuse(obs, now_ms):
        raise error
    bridge.spool.enqueue_observation = refuse


def _percept(band="low"):
    return Percept("need", "self", "", "normal", facts=(("band", band),))


# S2: one talk line, in her name, once, when the act is pushed.
def test_her_words_are_one_talk_line_in_her_name_when_the_act_is_pushed(tmp_path):
    said = []
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: "cmd-1",
                         say=lambda text, object_id: said.append((text, object_id)), her_name=lambda: "Ida")
    courier.tick(_Mint(acts=[_requested(words="Hello there, Bo.")]), "h", 1000, True, probe="2.39.0")
    courier.on_row(_pushed())
    courier.on_row(_pushed(at=5500))
    assert said == [('Ida: "Hello there, Bo."', "11")]


def test_words_are_not_said_without_a_name_and_an_act_without_words_says_nothing(tmp_path):
    said = []
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: "cmd-1",
                         say=lambda text, object_id: said.append(text), her_name=lambda: None)
    courier.tick(_Mint(acts=[_requested(words="Hi")]), "h", 1000, True, probe="2.39.0")
    courier.on_row(_pushed())
    plain = ActCourier(Spool(tmp_path / "two.db"), lambda command, args: "cmd-2",
                       say=lambda text, object_id: said.append(text), her_name=lambda: "Ida")
    plain.tick(_Mint(acts=[_requested(act_id="e" * 32)]), "h", 1000, True, probe="2.39.0")
    plain.on_row(dict(_pushed(), e2=dict(_pushed()["e2"], act_id="e" * 32)))
    assert said == []


def test_talk_says_her_words_through_the_switch_and_the_throttle(tmp_path):
    published = []
    talk = Talk(Spool(tmp_path / "talk.db"), lambda command, args: published.append((command, args)))
    talk.say('Ida: "Hi"', "11")
    talk.tick(1000, live=False)  # not live: the line is dropped, as the sentences are
    assert published == []
    talk.say('Ida: "Hi"', "11")
    talk.tick(1000, live=True)
    talk.say('Ida: "Again"', "11")
    talk.tick(1100, live=True)  # inside the throttle gap: it waits
    talk.tick(3200, live=True)
    assert published == [("talk", {"text": 'Ida: "Hi"', "sim_id": "11"}),
                         ("talk", {"text": 'Ida: "Again"', "sim_id": "11"})]


# B2: the refs are kept across an attach flip; a new game starts its own and the view's attachment says so.
def test_the_refs_are_kept_across_an_attach_flip_and_reset_with_a_new_game(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    first_refs = bridge._refs
    bridge._follow_refs({"telemetry_session_id": "game-1"})
    bridge._state = "detached"
    bridge._follow_refs({"telemetry_session_id": "game-1"})
    assert bridge._refs is first_refs and bridge._attachment() == bridge.helper_session
    bridge._follow_refs({"telemetry_session_id": "game-2"})
    assert bridge._refs is not first_refs
    assert bridge._attachment() == "%s:1" % bridge.helper_session


# F3: a body row from before this run, older than two minutes, is no view of now; a fresh one is.
def test_a_restored_body_row_older_than_two_minutes_is_no_view_of_now(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    bridge._last_body_row = {"wall_timestamp_ms": WALL - STALE_BODY_MS - 1}
    assert bridge._body_is_restored(WALL) is True
    bridge._body_fresh = True
    assert bridge._body_is_restored(WALL) is False
    bridge._body_fresh = False
    bridge._last_body_row = None
    assert bridge._body_is_restored(WALL) is False


# F1: a view waits while the acts round trip failed; the diary and the views go after the acts once it answers.
def test_the_views_wait_while_the_acts_round_trip_failed(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    flushed = []
    monkeypatch.setattr(bridge, "_flush_views", lambda wall: flushed.append(wall))
    monkeypatch.setattr(bridge, "_send_diary", lambda wall: None)
    bridge._acts.sync_ok = False
    bridge._send_due(WALL)
    assert flushed == []
    bridge._acts.sync_ok = True
    bridge._send_due(WALL + 1)
    assert flushed == [WALL + 1]


# F4: a refused view puts its changes back and says so in the log; after the requeues are spent they are let go.
def test_a_refused_view_puts_its_changes_back_and_says_so_in_the_log(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    _refusing(bridge, ContractError("invalid_body", "world"))
    percept = _percept()
    bridge._send_view((percept,), "quiet", WALL)
    assert [item[0].key for item in bridge._coalesced.items] == [percept.key]
    assert _log_lines(data)[-1]["requeued"] is True


def test_a_refused_view_is_let_go_once_its_requeues_are_spent(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    _refusing(bridge, ContractError("invalid_body", "world"))
    bridge._coalesced = coalesce.add(bridge._coalesced, [_percept()], WALL)
    for attempt in range(REQUEUE_LIMIT + 1):
        bridge._flush_views(WALL + 10_000 * (attempt + 1))  # each flush takes the queue and sends it, refused
    assert bridge._coalesced.items == () and bridge._requeued == 0
    assert _log_lines(data)[-1]["dropped_percepts"] == 1


# C11: the spot stages reach the decision log, once per change.
def test_the_spot_stages_reach_the_decision_log_once_per_change(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    stages = {"anchors": 3, "placement": True, "terrain": True, "offers": 0}
    bridge._log_spot_stages({"spot_stages": stages}, WALL)
    bridge._log_spot_stages({"spot_stages": dict(stages)}, WALL + 1)
    bridge._log_spot_stages({"spot_stages": dict(stages, offers=1)}, WALL + 2)
    lines = [line for line in _log_lines(data) if line.get("trigger") == "spot_stages"]
    assert [line["stages"]["offers"] for line in lines] == [0, 1]
    assert lines[0]["stages"] == stages


# C1: a look asks the probe for the near part, on a probe that has it.
def test_a_look_asks_for_the_near_part_of_the_menu_on_a_probe_that_has_it(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    sent = []
    monkeypatch.setattr(commands_module, "publish", lambda command, args, issuer, paths=None: sent.append(command))
    bridge = _bridge(paths, {"ms": WALL})
    bridge.spool.ingest("s", 0, 0, dict(_lineage(1, WALL), probe_version="2.38.0"), raw_len=10)
    bridge._send_look(WALL)
    assert "menu_near" not in sent
    bridge.spool.ingest("t", 0, 0, dict(_lineage(2, WALL + 1), probe_version="2.39.0"), raw_len=10)  # a new game session's file
    bridge._send_look(WALL + 2)
    assert "menu_near" in sent
    assert data.exists()


# C8, C11: the part-zero facts of a menu (dropped objects, spot stages) survive the parts' merge.
def test_a_menu_keeps_its_part_zero_facts_across_the_merge():
    parts = MenuParts()
    head = {"menu_rev": 5, "part": 0, "parts": 2, "room": "4", "objects": [{"object_id": "1", "acts": []}],
            "dropped": {"objects": 2, "rooms": ["7"]}, "spot_stages": {"anchors": 1}}
    tail = {"menu_rev": 5, "part": 1, "parts": 2, "room": "4", "objects": [{"object_id": "2", "acts": []}]}
    assert parts.take("s", head) is None
    whole = parts.take("s", tail)
    assert whole["dropped"] == {"objects": 2, "rooms": ["7"]}
    assert whole["spot_stages"] == {"anchors": 1}
    assert [item["object_id"] for item in whole["objects"]] == ["1", "2"]


# F6: command replies older than seven days leave cmd/done, one named file at a time; nothing else goes.
def test_a_command_folder_keeps_seven_days_and_loses_only_older_json_replies(tmp_path):
    done = tmp_path / "done"
    done.mkdir()
    day = 24 * 3600
    now_s = 2_000_000_000
    old = done / ("a" * 32 + ".json")
    recent = done / ("b" * 32 + ".json")
    other = done / "notes.txt"
    for path in (old, recent, other):
        path.write_text("{}", encoding="utf-8")
    os.utime(old, (now_s - 8 * day, now_s - 8 * day))
    os.utime(recent, (now_s - 6 * day, now_s - 6 * day))
    os.utime(other, (now_s - 30 * day, now_s - 30 * day))
    removed = prune_done(SimpleNamespace(done=done), now_s * 1000)
    assert removed == [old.name]
    assert not old.exists() and recent.exists() and other.exists()
    assert prune_done(SimpleNamespace(done=tmp_path / "missing"), now_s * 1000) == []


# F2: one tick reads at most 500 lines of the telemetry; the rest wait for the next tick, in order.
def test_a_tick_reads_at_most_500_telemetry_rows_and_the_rest_come_next_tick(paths, tmp_path):
    from test_bridge import _row, _session
    from domus_helper.cursor import TelemetryCursor
    session = _session(paths)
    with session.open("ab") as handle:
        for seq in range(1, 1202):
            handle.write(json.dumps(_row(seq)).encode("utf-8") + b"\n")
    cursor = TelemetryCursor(Spool(tmp_path / "spool.db"), paths)
    first = cursor.read_new()
    second = cursor.read_new()
    third = cursor.read_new()
    assert [len(first), len(second), len(third)] == [500, 500, 201]
    assert [row["written_sequence"] for row in first + second + third] == list(range(1, 1202))
    assert cursor.read_new() == []
