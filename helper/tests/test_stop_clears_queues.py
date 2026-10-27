"""R4/L4: one stop clears every helper-side queue.

The probe's stop command ends sampling and the game's own work, but the helper
also holds commands and acts that have not reached or been answered by the
probe.  After ``stop``:

* the probe must still receive its stop command (the queues are drained after
  it is forwarded, never instead of it);
* every pending command file in ``cmd/inbox`` is gone or is no longer a live
  command for ``cmdbox.parse`` (the existing TTL/EXPIRED path);
* the pending acts of a live ``ActCourier`` and its persisted ``acts_known``
  queue are gone or marked answered/terminal;
* telemetry rows, act events, the lineage ledger, decision logs and finished
  command/reply records are kept.
"""
import json
import threading
import time
from contextlib import contextmanager

from conftest import opened, session_file
from domus_helper import commands, mcp_server as mcp
from domus_helper.acts import ActCourier
from domus_helper.spool import Spool
from domus_helper.vendor import cmdbox

ACT = {"act_id": "a" * 32, "object_id": "11", "guid64": "4242", "expires_at_ms": 99_000}


class _Client:
    """The acts round trip Mint's side, as test_acts.py's fake."""

    def __init__(self, acts=()):
        self.acts = list(acts)
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        return {"status": "ok", "applied": len(body["events"]), "acts": list(self.acts)}


@contextmanager
def _probe(paths):
    """A probe that consumes only status and stop, and leaves every helper command alone.

    It stands in for a real probe that has not reached the helper's pending
    commands yet: those files must be the stop path's work, not the fake's.
    """
    stopping = threading.Event()
    answered = []
    failures = []

    def worker():
        try:
            while not stopping.is_set():
                for path in sorted(paths.inbox.glob("*.json")):
                    try:
                        row = json.loads(path.read_bytes())
                    except (OSError, ValueError):
                        continue
                    if row.get("command") not in ("status", "stop"):
                        continue
                    if any(item["id"] == row["id"] for item in answered):
                        continue
                    answered.append(row)
                    reply = {"id": row["id"], "issuer": row["issuer"],
                             "status": "OK", "code": None, "result": {}}
                    temporary = paths.outbox / (path.name + ".tmp")
                    temporary.write_text(json.dumps(reply))
                    temporary.replace(paths.outbox / path.name)
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                stopping.wait(0.002)
        except BaseException as error:  # surfaced below, on the test's thread
            failures.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        yield answered
    finally:
        stopping.set()
        thread.join(2)
        assert not thread.is_alive()
        if failures:
            raise failures[0]


def _stop(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    monkeypatch.setattr(mcp, "tools", lambda: mcp.DomusTools(paths=paths))
    return mcp.stop()


def _live_commands(paths, now_ms=None):
    """The command files a probe would still accept now (EXPIRED files are not pending)."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    live = []
    for path in sorted(paths.inbox.glob("*.json")):
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        command, _error = cmdbox.parse(raw, now_ms, ())
        if command is not None:
            live.append(command)
    return live


def _pending_act_ids(courier):
    """Acts the courier still treats as waiting for the probe."""
    return [act_id for act_id, known in courier._known.items()
            if not known.get("answered") and not known.get("terminal") and not known.get("timed_out")]


def _publish_pending_commands(paths):
    """Valid helper commands a probe may not have consumed yet, of every kind the bridge publishes."""
    pending = [
        ("act", {"act_id": "1" * 32, "object_id": "11", "guid64": "4242"}),
        ("answer", {"act_id": "2" * 32, "dialog_id": "55", "pick": "ok"}),
        ("cancel", {"act_id": "3" * 32, "interaction_id": "66"}),
        ("talk", {"text": "an invented line"}),
        ("camera", {"op": "follow_sim", "target_id": "77"}),
        ("pace", {"need_drain": 1.0, "slow_time": 1.0}),
        ("menu_near", {}),
        ("lists_now", {}),
        ("catalog_dump", {}),
    ]
    return [commands.publish(command, args, "helper", paths=paths) for command, args in pending]


def test_stop_is_still_sent_and_pending_command_files_are_cancelled(
        paths, tmp_path, monkeypatch):
    pending_ids = _publish_pending_commands(paths)
    assert len(_live_commands(paths)) == len(pending_ids)

    paths.telemetry.mkdir(parents=True, exist_ok=True)
    session = session_file(paths, [opened(0)])
    session_before = session.read_bytes()
    ledger_before = paths.ledger.read_bytes()
    decision_log = tmp_path / "thalamus" / "decisions-20261027.jsonl"
    decision_log.parent.mkdir(parents=True)
    decision_log.write_text('{"wall_ms": 1, "trigger": "invented"}\n', encoding="utf-8")
    decision_before = decision_log.read_bytes()
    done = paths.done / ("d" * 32 + ".json")
    done.write_text('{"invented": "finished"}\n', encoding="utf-8")
    done_before = done.read_bytes()
    reply = paths.outbox / ("e" * 32 + ".json")
    reply.write_text('{"invented": "reply"}\n', encoding="utf-8")
    reply_before = reply.read_bytes()

    with _probe(paths) as answered:
        _stop(paths, tmp_path, monkeypatch)

    sent = [row["command"] for row in answered]
    assert "stop" in sent, "the probe stop command must still be forwarded"
    assert sent[-1] == "stop"

    live = _live_commands(paths)
    live_ids = {row["id"] for row in live}
    assert live_ids.isdisjoint(pending_ids), "a pending command the probe has not consumed is still live"
    assert live == [], "every pending command must be removed or marked expired/cancelled"

    # (c) history is never a queue: it stays byte for byte.
    assert session.read_bytes() == session_before
    assert paths.ledger.read_bytes() == ledger_before
    assert decision_log.read_bytes() == decision_before
    assert done.read_bytes() == done_before
    assert reply.read_bytes() == reply_before


def test_stop_clears_the_pending_act_queue_and_keeps_act_and_telemetry_history(
        paths, tmp_path, monkeypatch):
    spool = Spool(tmp_path / "spool.db")
    pending = {
        "a" * 32: {"written_ms": 1_000, "object": "11", "cmd": "b" * 32},
        "c" * 32: {"written_ms": 900, "answered": True, "terminal": True},
    }
    events = [{"act_id": "a" * 32, "phase": "received", "at_ms": 1_000}]
    spool.put_many_kv({"acts_known": json.dumps(pending, sort_keys=True),
                       "acts_events": json.dumps(events)})
    spool.ingest("session", 0, 0, {"event_kind": "act_event", "invented": True}, raw_len=10)
    spool.close()

    with _probe(paths) as answered:
        _stop(paths, tmp_path, monkeypatch)
    assert [row["command"] for row in answered][-1] == "stop"

    spool = Spool(tmp_path / "spool.db")
    try:
        known = json.loads(spool.get_kv("acts_known") or "{}")
        waiting = {act_id: entry for act_id, entry in known.items()
                   if not entry.get("answered") and not entry.get("terminal") and not entry.get("timed_out")}
        assert waiting == {}, "the persisted pending act queue must be empty after stop"
        # The act events are history to send, not a command queue; telemetry rows are history too.
        assert json.loads(spool.get_kv("acts_events")) == events
        assert spool.row_count() == 1
    finally:
        spool.close()


def test_stop_clears_a_live_act_couriers_pending_acts(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    spool = Spool(tmp_path / "spool.db")
    published = []
    courier = ActCourier(spool, lambda command, args: published.append((command, args)))
    try:
        client = _Client([dict(ACT)])
        assert courier.tick(client, "h", 1_000, True) == [ACT["act_id"]]
        assert _pending_act_ids(courier) == [ACT["act_id"]]

        with _probe(paths) as answered:
            _stop(paths, tmp_path, monkeypatch)
        assert [row["command"] for row in answered][-1] == "stop"

        # A live courier may notice the stop on its next tick; the act must not stay waiting
        # for a probe that has stopped (this is well inside PROBE_REPLY_MS, so no timeout can
        # be what clears it).
        courier.tick(_Client(), "h", 1_500, True)
        assert _pending_act_ids(courier) == []
    finally:
        spool.close()
