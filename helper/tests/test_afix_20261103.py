"""AU_DOMUS_FULL_2026-11-03 fixes: one regression test per audit item."""
import json

from domus_helper.acts import ActCourier
from domus_helper.spool import Spool

PROBE = "2.41.7"


# N-2: every act (act, cancel, answer) is recorded and saved before its command goes out, so a helper that dies
# before tick's save and gets the same act again after a restart never pushes it twice.
def _one_push_across_a_restart(tmp_path, act):
    pushes = []

    def publish(command, args):
        pushes.append((command, args["act_id"]))
        return "%032x" % len(pushes)
    ActCourier(Spool(tmp_path / "spool.db"), publish)._receive({"acts": [act]}, 1000, True, PROBE)
    ActCourier(Spool(tmp_path / "spool.db"), publish)._receive({"acts": [act]}, 2000, True, PROBE)
    return pushes


def test_an_act_is_pushed_once_across_a_restart(tmp_path):
    act = {"act_id": "a" * 32, "object_id": "123", "guid64": "456"}
    assert _one_push_across_a_restart(tmp_path, act) == [("act", "a" * 32)]


def test_a_cancel_is_pushed_once_across_a_restart(tmp_path):
    from domus_helper.acts import QUEUE_OBJECT_ID
    act = {"act_id": "c" * 32, "object_id": QUEUE_OBJECT_ID, "guid64": "77"}
    assert _one_push_across_a_restart(tmp_path, act) == [("cancel", "c" * 32)]


def test_an_answer_is_pushed_once_across_a_restart(tmp_path):
    from domus_helper.acts import DIALOG_PREFIX
    act = {"act_id": "d" * 32, "object_id": DIALOG_PREFIX + "9", "guid64": "ok"}
    assert _one_push_across_a_restart(tmp_path, act) == [("answer", "d" * 32)]


# N-1: expire_pending never puts back a command the probe has already taken.
def _published(tmp_path):
    from domus_helper import commands
    from domus_helper.paths import Paths
    inbox = tmp_path / "AshleyE1Telemetry" / "cmd" / "inbox"
    inbox.mkdir(parents=True)
    paths = Paths(tmp_path)
    command_id = commands.publish("status", {}, "helper", paths=paths)
    return paths, inbox, inbox / (command_id + ".json")


def test_expire_pending_never_recreates_a_command_the_probe_took_between_read_and_replace(tmp_path, monkeypatch):
    import os
    import pathlib
    from domus_helper import commands
    paths, inbox, command = _published(tmp_path)
    original = pathlib.Path.read_bytes

    def racing(self):
        data = original(self)
        if self.parent == inbox and command.exists():
            os.replace(command, str(command) + ".taken")  # the probe takes it, if it still can, after the helper read
        return data
    monkeypatch.setattr(pathlib.Path, "read_bytes", racing)
    commands.expire_pending(paths)
    # A command is owned by exactly one side: never both back in the inbox and taken by the probe.
    names = sorted(entry.name for entry in inbox.iterdir())
    assert names in ([command.name], [command.name + ".taken"])


def test_expire_pending_skips_a_command_the_probe_took_before_the_claim(tmp_path, monkeypatch):
    import os
    from domus_helper import commands
    paths, inbox, command = _published(tmp_path)
    real_replace = os.replace

    def probe_first(source, target):
        if str(source) == str(command) and command.exists():
            real_replace(command, str(command) + ".taken")
        return real_replace(source, target)
    monkeypatch.setattr(commands.os, "replace", probe_first)
    assert commands.expire_pending(paths) == []
    assert sorted(entry.name for entry in inbox.iterdir()) == [command.name + ".taken"]


def test_expire_pending_still_expires_a_command_nobody_took(tmp_path):
    from domus_helper import commands
    from domus_helper.vendor import cmdbox
    paths, inbox, command = _published(tmp_path)
    assert commands.expire_pending(paths) == [command.stem]
    assert sorted(entry.name for entry in inbox.iterdir()) == [command.name]
    assert cmdbox.parse(command.read_bytes(), 10 ** 15, ())[1] == "EXPIRED"
