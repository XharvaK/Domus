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


# N-3: a black PrintWindow fails the picture; the screen is never copied (it can hold other windows above the game).
def _fake_win(calls, hwnd, w, h):
    import ctypes
    import types
    from ctypes import wintypes

    class Header(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class Info(ctypes.Structure):
        _fields_ = [("bmiHeader", Header)]
    buffer = ctypes.create_string_buffer(w * h * 4)  # all zero: a black frame

    def record(name, result):
        def call(*args):
            calls.append(name)
            return result
        return call

    def dib(memdc, info, usage, bits, section, offset):
        calls.append("CreateDIBSection")
        bits._obj.value = ctypes.addressof(buffer)
        return 7
    user32 = types.SimpleNamespace(PrintWindow=record("PrintWindow", 1), GetForegroundWindow=record("GetForegroundWindow", hwnd),
                                   GetDC=record("GetDC", 9), ReleaseDC=record("ReleaseDC", 1),
                                   ClientToScreen=record("ClientToScreen", 1))
    gdi32 = types.SimpleNamespace(CreateCompatibleDC=record("CreateCompatibleDC", 5), CreateDIBSection=dib,
                                  SelectObject=record("SelectObject", 3), DeleteObject=record("DeleteObject", 1),
                                  DeleteDC=record("DeleteDC", 1), BitBlt=record("BitBlt", 1))
    return types.SimpleNamespace(user32=user32, gdi32=gdi32, bitmap_info=Info, bitmap_header=Header), buffer


def test_an_all_black_print_window_fails_without_copying_the_screen():
    import pytest
    from domus_helper import snapshot
    calls = []
    win, _buffer = _fake_win(calls, 42, 4, 3)
    with pytest.raises(snapshot.SnapshotFailed):
        snapshot._frame(win, 42, 4, 3)
    assert "PrintWindow" in calls
    assert not {"GetDC", "BitBlt", "ClientToScreen"} & set(calls)
    assert calls.count("DeleteDC") == 1  # the memory DC is still freed


# N-4: the proof chain survives a crash mid-append, a torn last line, and a torn .ots.
def test_the_chain_still_verifies_after_a_crash_between_the_line_and_the_kv(tmp_path):
    from domus_helper import proof
    spool = Spool(tmp_path / "spool.db")
    chain = proof.Chain(spool, tmp_path / "proof", "k")
    path = tmp_path / "proof" / "t.jsonl"
    chain.append(path, {"n": 1})
    real = spool.put_kv

    def crash(*args):
        raise OSError("crash")
    spool.put_kv = crash
    try:
        chain.append(path, {"n": 2})
    except OSError:
        pass
    spool.put_kv = real
    chain.append(path, {"n": 3})
    assert proof.verify_lines(path.read_text(encoding="utf-8").splitlines())[:2] == (True, 3)


def test_the_chain_drops_a_torn_last_line_and_still_verifies(tmp_path):
    from domus_helper import proof
    chain = proof.Chain(Spool(tmp_path / "spool.db"), tmp_path / "proof", "k")
    path = tmp_path / "proof" / "t.jsonl"
    chain.append(path, {"n": 1})
    chain.append(path, {"n": 2})
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"n":3,"prev_ha')  # power lost mid-write
    chain.append(path, {"n": 4})
    assert proof.verify_lines(path.read_text(encoding="utf-8").splitlines())[:2] == (True, 3)


def test_a_torn_ots_is_stamped_again(tmp_path):
    import hashlib
    from domus_helper import proof
    folder = tmp_path / "proof"
    folder.mkdir()
    trace = folder / "trace-20261101.jsonl"
    trace.write_text("x\n", encoding="utf-8")
    digest = hashlib.sha256(b"x\n").digest()
    (folder / "trace-20261101.jsonl.ots").write_bytes(proof.OTS_MAGIC[:10])  # torn
    result = proof.stamp_finished_days(tmp_path, "20261102", submit=lambda calendar, d: b"PENDING")
    whole = proof.OTS_MAGIC + proof.OTS_VERSION + proof.OTS_SHA256 + digest + b"PENDING"
    assert (folder / "trace-20261101.jsonl.ots").read_bytes() == whole
    assert (folder / "trace-20261101.jsonl.ots2").read_bytes() == whole
    assert result[0]["stamped"] == ["trace-20261101.jsonl.ots", "trace-20261101.jsonl.ots2"]
    assert sorted(path.name for path in folder.iterdir()) == [
        "trace-20261101.jsonl", "trace-20261101.jsonl.ots", "trace-20261101.jsonl.ots2"]  # no temp left behind


# NOTE-1: the client never follows a redirect (the token would go with it), and only https or loopback is trusted.
def test_a_302_is_not_followed_and_the_token_is_sent_once(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from domus_helper.transport import AshleyClient
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def _answer(self):
            seen.append((self.command, self.path, self.headers.get("X-Domus-Token")))
            if self.path.startswith("/domus/"):
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self._answer()

        do_GET = _answer

        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = AshleyClient("http://127.0.0.1:%d" % server.server_port, "t" * 40, timeout_s=5)
        assert client.sync_acts({"v": 1, "helper_session": "s", "events": []}) is None
        assert client.post_snapshot({"v": 1, "helper_session": "s", "snapshot_id": "s-1", "failed": "x"}).kind == \
            "unavailable"
    finally:
        server.shutdown()
        server.server_close()
    assert [path for _method, path, _token in seen] == ["/domus/acts/sync", "/domus/snapshot"]


def test_load_credentials_requires_https_or_loopback(tmp_path, monkeypatch):
    from domus_helper.paths import Paths
    from domus_helper.transport import load_credentials
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "k" * 32)
    paths = Paths(tmp_path)
    for url in ("http://ashley.example.org", "ftp://ashley.example.org", "http://127.0.0.1.example.org"):
        monkeypatch.setenv("DOMUS_ASHLEY_URL", url)
        assert load_credentials(paths).disabled == "insecure_url", url
    for url in ("https://ashley.example.org", "http://127.0.0.1:9", "http://localhost:8", "http://[::1]:7"):
        monkeypatch.setenv("DOMUS_ASHLEY_URL", url)
        assert load_credentials(paths).disabled is None, url


# NOTE-2: a frame from the local OBS socket longer than the cap is refused before any of it is read.
def test_an_oversized_obs_frame_is_refused_before_it_is_read():
    import struct
    import pytest
    from domus_helper import obs

    class Sock:
        def __init__(self, data):
            self.data, self.asked = data, 0

        def recv(self, count):
            self.asked += count
            chunk, self.data = self.data[:count], self.data[count:]
            return chunk
    sock = Sock(bytes([0x81, 127]) + struct.pack(">Q", 1 << 40))
    with pytest.raises(ConnectionError):
        obs._read(sock)
    assert sock.asked == 10
