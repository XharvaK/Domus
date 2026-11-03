import json
import threading
import time
import uuid
from contextlib import contextmanager

import pytest

from domus_helper.paths import Paths
from domus_helper.vendor import cmdbox, schema


@pytest.fixture(autouse=True)
def fake_game_root(tmp_path, monkeypatch):
    """Keep the session away from any real Sims install (R1)."""
    root = tmp_path / "fake-game-root"
    bin_dir = root / "Game" / "Bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "Default.ini").write_text(
        "[Version]\ngameversion = 1.129.39.1030\n", encoding="utf-8")
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(root))
    # AU note: a test that falls back to the default data folder (E:\\Domus) writes in tmp_path, not in the checkout.
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "domus-data"))
    return root


@pytest.fixture
def paths(tmp_path, monkeypatch):
    root = tmp_path / "Sims"
    paths = Paths(root)
    for directory in (paths.inbox, paths.outbox, paths.done, root / "saves"):
        directory.mkdir(parents=True, exist_ok=True)
    paths.ledger.write_text('{}\n')
    (root / "saves" / "Slot_00000001.save").write_bytes(b"save fixture")
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(root))
    return paths


def event(kind, seq=0, **payload):
    return schema.make_record(kind, telemetry_session_id="a" * 32,
                              written_sequence=seq, **payload)


def opened(seq=0):
    return event("session_open", seq, attestation=dict(
        armed_name="LAB_E1", snapshot_guid="1", snapshot_slot="2", snapshot_sim="3"))


@contextmanager
def replier(paths, handler=None, key=None):
    """A stand-in probe: answers each command. OPENVULN F8: signs its reply under cmd/key as the probe does, or under
    `key` when given (b"" leaves it unsigned)."""
    stop = threading.Event()
    failures = []
    seen = []
    def worker():
        try:
            while not stop.is_set():
                for path in paths.inbox.glob("*.json"):
                    if path.name in seen:
                        continue
                    seen.append(path.name)
                    row = json.loads(path.read_bytes())
                    result = handler(row) if handler else dict(status="OK", code=None, result={})
                    reply = dict(id=row["id"], issuer=row["issuer"], **result)
                    signing = key
                    if signing is None and (paths.telemetry / "cmd" / "key").exists():
                        signing = bytes.fromhex((paths.telemetry / "cmd" / "key").read_text(encoding="ascii"))
                    if signing and hasattr(cmdbox, "mac"):
                        reply["mac"] = cmdbox.mac(signing, reply)
                    temporary = paths.outbox / (path.name + ".tmp")
                    temporary.write_text(json.dumps(reply))
                    temporary.replace(paths.outbox / path.name)
                stop.wait(0.002)
        except BaseException as error:
            failures.append(error)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        yield seen
    finally:
        stop.set()
        thread.join(2)
        assert not thread.is_alive()
        if failures:
            raise failures[0]


def session_file(paths, records):
    path = paths.telemetry / f"ashley_e1_{uuid.uuid4()}.jsonl"
    path.write_bytes(b"".join(schema.serialize_record(row) + b"\n" for row in records))
    return path
