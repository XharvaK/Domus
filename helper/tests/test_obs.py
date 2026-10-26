import json
import socket
import struct
import threading

from domus_helper import inputs, obs, overlay, proof
from domus_helper.spool import Spool

NOW = 1_800_000_000_000


def test_the_auth_string_matches_the_protocol_example():
    # The worked example in the obs-websocket v5 protocol document.
    assert obs.auth_string("supersecretpassword", "lM1GncleQOaCu9lT1yeUZhFYnqhsLLP1G5lAGo3ixaI=",
                           "+IxH4CnCiqpX1rM9scsNynZzbOe4KhDeYcTNS3PDaeY=") == "1Ct943GAT+6YQUUX47Ia/ncufilbe6+oD6lY+5kaCu4="


def _send(conn, message):
    payload = json.dumps(message).encode("utf-8")
    head = bytes([0x81]) + (bytes([len(payload)]) if len(payload) < 126 else bytes([126]) + struct.pack(">H", len(payload)))
    conn.sendall(head + payload)


def _fake_server(password, seen):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def run():
        conn, _ = server.accept()
        with conn:
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(1024)
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
            _send(conn, {"op": 0, "d": {"rpcVersion": 1, "authentication": {"salt": "s4lt", "challenge": "ch4l"}}})
            sock_file = conn
            while True:
                try:
                    message = obs._read(sock_file)
                except ConnectionError:
                    return
                seen.append(message)
                if message["op"] == 1:
                    if message["d"].get("authentication") != obs.auth_string(password, "s4lt", "ch4l"):
                        return
                    _send(conn, {"op": 2, "d": {"negotiatedRpcVersion": 1}})
                elif message["op"] == 6:
                    _send(conn, {"op": 7, "d": {"requestType": message["d"]["requestType"],
                                                "requestId": message["d"]["requestId"],
                                                "requestStatus": {"result": True, "code": 100}}})
    threading.Thread(target=run, daemon=True).start()
    return server


def test_it_identifies_and_sends_both_requests(tmp_path):
    seen = []
    server = _fake_server("pw", seen)
    try:
        port = server.getsockname()[1]
        assert obs.request({"port": port, "password": "pw"}, ("SaveReplayBuffer", "CreateRecordChapter")) == {
            "SaveReplayBuffer": True, "CreateRecordChapter": True}
        assert [message["op"] for message in seen] == [1, 6, 6]
    finally:
        server.close()


def test_a_wrong_password_or_no_tool_is_quietly_nothing(tmp_path):
    seen = []
    server = _fake_server("pw", seen)
    try:
        assert obs.request({"port": server.getsockname()[1], "password": "nope"}, ("SaveReplayBuffer",)) == {}
    finally:
        server.close()
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()
    assert obs.request({"port": port, "password": None}, ("SaveReplayBuffer",)) == {}
    assert obs.load(tmp_path) is None
    (tmp_path / obs.CONFIG).write_text(json.dumps({"port": 70000}), encoding="utf-8")
    assert obs.load(tmp_path) is None


class Feed:
    def __init__(self, marks):
        self.marks = marks

    def post_feed(self, body):
        return {"status": "ok", "items": [], "marks": self.marks}


def test_a_flag_is_ledgered_once_and_the_recording_kept(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(obs, "keep_recording", lambda data_dir: asked.append(data_dir) or True)
    spool = Spool(tmp_path / "spool.db")
    try:
        inputs.set_mode(spool, tmp_path, inputs.GAME_ONLY, NOW)
        view = overlay.Overlay(spool, tmp_path, NOW)
        view.poll(Feed([{"id": 7, "at_ms": NOW}]), "h1", NOW)
        view.poll(Feed([{"id": 7, "at_ms": NOW}, {"id": 8, "at_ms": NOW}]), "h1", NOW + overlay.FEED_EVERY_MS)
        view.poll(Feed([{"id": 8, "at_ms": NOW}]), "h1", NOW + 2 * overlay.FEED_EVERY_MS)
        entries = [json.loads(line) for line in (tmp_path / proof.DIR / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        assert [entry["note"] for entry in entries] == ["word watch flag 7 (review on the host)", "word watch flag 8 (review on the host)"]
        assert all(entry["kind"] == "flagged" for entry in entries)
        assert len(asked) == 2 and view.kept is True
    finally:
        spool.close()
