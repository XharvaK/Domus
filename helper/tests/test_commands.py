import ast
import json
from pathlib import Path

import pytest

from domus_helper import commands
from domus_helper.vendor import cmdbox
from conftest import replier


def test_atomic_envelope(paths, monkeypatch):
    original = commands.os.replace
    published = []
    def replace(source, target):
        if source.parent != paths.inbox:
            return original(source, target)
        assert source.name == target.name + ".tmp"
        assert not target.exists()
        raw = source.read_bytes()
        assert len(raw) <= 4096
        row = json.loads(raw.decode("utf-8"))
        assert set(row) == cmdbox.KEYS
        assert row["expires_at_ms"] - row["issued_at_ms"] == 30000
        assert cmdbox.parse(raw, row["issued_at_ms"], ())[1] is None
        published.append(row)
        original(source, target)
    monkeypatch.setattr(commands.os, "replace", replace)
    with replier(paths):
        reply = commands.send("prepare", {"object_id": "123"}, "agent:test")
    assert reply.id == published[0]["id"]
    assert len(list(paths.inbox.glob("*.json"))) == 1
    assert not list(paths.inbox.glob("*.tmp"))


def test_reply_id_match(paths):
    def handler(row):
        wrong = dict(id="f" * 32, status="OK", code=None, result={}, issuer=row["issuer"])
        (paths.outbox / ("f" * 32 + ".json")).write_text(json.dumps(wrong))
        return dict(status="OK", code=None, result={"matched": True})
    with replier(paths, handler):
        assert commands.send("status", {}, "helper").result == {"matched": True}


def test_wrong_id_in_expected_filename(paths):
    def handler(row):
        return dict(status="OK", code=None, result={})
    # Override decoding only for the received reply, to simulate a wrong id.
    original = commands.cmdbox.decode
    def decode(raw):
        payload = original(raw)
        payload["id"] = "f" * 32
        return payload
    from unittest.mock import patch
    with replier(paths, handler), patch.object(commands.cmdbox, "decode", decode):
        with pytest.raises(commands.InboxNotAnswering):
            commands.send("status", {}, "helper", timeout_s=0.05)


def test_timeout_preserves_files(paths):
    with pytest.raises(commands.InboxNotAnswering, match="type ashley_e1.inbox"):
        commands.send("status", {}, "helper", timeout_s=0.01)
    assert len(list(paths.inbox.glob("*.json"))) == 1
    assert paths.ledger.exists()


@pytest.mark.parametrize("command,args", [("prepare", {"object_id": 123}),
    ("sit_trial", {"object_id": "1" * 21}), ("arm", {"name": "other"}),
    ("sit", {"token": "A" * 16}), ("start", {"extra": 1})])
def test_invalid_arguments(paths, command, args):
    with pytest.raises(ValueError, match="BAD_ARGS"):
        commands.send(command, args, "helper")
    assert not list(paths.inbox.iterdir())


@pytest.mark.parametrize("module", ["cmdbox", "schema"])
def test_ast_drift(module):
    root = Path(__file__).resolve().parents[2]
    source = root / "sims-e1" / "src" / "ashley_e1" / (module + ".py")
    vendor = root / "helper" / "domus_helper" / "vendor" / (module + ".py")
    assert ast.dump(ast.parse(source.read_text())) == ast.dump(ast.parse(vendor.read_text()))


def test_unowned_tmp_is_preserved(paths, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(commands.uuid, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    existing = paths.inbox / ("a" * 32 + ".json.tmp")
    existing.write_bytes(b"not ours")
    with pytest.raises(FileExistsError):
        commands.send("status", {}, "helper")
    assert existing.read_bytes() == b"not ours"
