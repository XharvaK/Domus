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
