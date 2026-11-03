"""OPENVULN 2026-11-03 (Domus, helper side): one regression test per finding."""
import json
import os
import stat

import pytest

from domus_helper import commands
from domus_helper.vendor import cmdbox


# F1: every envelope the helper writes carries a MAC under the shared cmd/key, which the helper makes once (0600).
def test_f1_the_helper_signs_every_envelope_with_its_key(paths):
    command_id = commands.publish("status", {}, "helper", paths=paths)
    key_file = paths.telemetry / "cmd" / "key"
    key = bytes.fromhex(key_file.read_text(encoding="ascii"))
    assert len(key) == 32
    if os.name == "posix":
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    row = json.loads((paths.inbox / (command_id + ".json")).read_bytes())
    assert cmdbox.mac_ok(key, row)
    assert cmdbox.parse(json.dumps(row).encode(), row["issued_at_ms"], ())[1] is None
    commands.publish("status", {}, "helper", paths=paths)
    assert bytes.fromhex(key_file.read_text(encoding="ascii")) == key


def test_f1_expire_pending_keeps_the_envelope_signed(paths):
    command_id = commands.publish("status", {}, "helper", paths=paths)
    assert commands.expire_pending(paths) == [command_id]
    key = bytes.fromhex((paths.telemetry / "cmd" / "key").read_text(encoding="ascii"))
    assert cmdbox.mac_ok(key, json.loads((paths.inbox / (command_id + ".json")).read_bytes()))


# F8: a reply is believed only with a valid MAC under the shared key; public id and issuer are not enough.
def _forged_replier(paths, key=None):
    from conftest import replier

    def handler(row):
        return dict(status="OK", code=None, result={"forged": True})
    return replier(paths, handler, key=key)


def test_f8_send_ignores_an_unsigned_reply(paths):
    with _forged_replier(paths, key=b""):
        with pytest.raises(commands.InboxNotAnswering):
            commands.send("status", {}, "helper", timeout_s=0.3, paths=paths)


def test_f8_send_ignores_a_reply_signed_with_another_key(paths):
    with _forged_replier(paths, key=bytes(32)):
        with pytest.raises(commands.InboxNotAnswering):
            commands.send("status", {}, "helper", timeout_s=0.3, paths=paths)


def test_f8_read_reply_ignores_an_unsigned_reply(paths):
    command_id = commands.publish("status", {}, "helper", paths=paths)
    (paths.outbox / (command_id + ".json")).write_text(json.dumps(
        dict(id=command_id, status="OK", code=None, result={}, issuer="helper")))
    assert commands.read_reply(command_id, paths=paths) is None


def test_f8_a_signed_reply_is_accepted(paths):
    from conftest import replier
    with replier(paths):
        assert commands.send("status", {}, "helper", timeout_s=2, paths=paths).status == "OK"


# F4, F5, F6: the reply poll reads a bounded, regular file without blocking, and keeps its deadline.
import threading
import time
import tracemalloc


def _planting_replier(paths, plant, delay=0.3):
    """For the first command: plant something at its reply path, then after `delay` write the real signed reply."""
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            found = list(paths.inbox.glob("*.json"))
            if found:
                row = json.loads(found[0].read_bytes())
                target = paths.outbox / (row["id"] + ".json")
                cleanup = plant(target)
                if stop.wait(delay):
                    return
                if cleanup:
                    cleanup()
                key = bytes.fromhex((paths.telemetry / "cmd" / "key").read_text(encoding="ascii"))
                reply = dict(id=row["id"], issuer=row["issuer"], status="OK", code=None, result={})
                reply["mac"] = cmdbox.mac(key, reply)
                temporary = paths.outbox / "real.tmp"
                temporary.write_text(json.dumps(reply))
                os.replace(temporary, target)
                return
            stop.wait(0.002)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return stop, thread


def test_f4_an_oversized_reply_file_is_not_read_into_memory(paths):
    def plant(target):
        with open(target, "wb") as handle:
            handle.truncate(256 * 1024 * 1024)  # sparse: no disk, but read_bytes would allocate it all
        return None
    stop, thread = _planting_replier(paths, plant)
    tracemalloc.start()
    try:
        reply = commands.send("status", {}, "helper", timeout_s=5, paths=paths)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        stop.set()
        thread.join(2)
    assert reply.status == "OK"
    assert peak < 32 * 1024 * 1024


def test_f5_a_folder_at_the_reply_path_reads_as_no_reply_yet(paths):
    def plant(target):
        target.mkdir()
        return target.rmdir
    stop, thread = _planting_replier(paths, plant)
    try:
        assert commands.send("status", {}, "helper", timeout_s=5, paths=paths).status == "OK"
    finally:
        stop.set()
        thread.join(2)


def test_f5_read_reply_reads_a_folder_as_no_reply(paths):
    command_id = commands.publish("status", {}, "helper", paths=paths)
    (paths.outbox / (command_id + ".json")).mkdir()
    assert commands.read_reply(command_id, paths=paths) is None
