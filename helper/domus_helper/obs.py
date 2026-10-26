"""E4: a minimal client for a capture tool's local control socket (obs-websocket protocol v5), standard
library only. It is used for two requests: keep the replay buffer, and mark the recording.

Settings in `obs_ws.json` in the data folder: {"port": 4455, "password": "..."}. The password is a
secret: it is never printed or logged. No file, no calls.
"""
import base64
import hashlib
import json
import os
import socket
import struct
import threading

CONFIG = "obs_ws.json"
TIMEOUT_S = 3


def load(data_dir):
    try:
        raw = json.loads((data_dir / CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    port = raw.get("port", 4455)
    if type(port) is not int or not 0 < port < 65536:
        return None
    password = raw.get("password")
    return {"port": port, "password": password if isinstance(password, str) else None}


def auth_string(password, salt, challenge):
    secret = base64.b64encode(hashlib.sha256((password + salt).encode("utf-8")).digest()).decode("ascii")
    return base64.b64encode(hashlib.sha256((secret + challenge).encode("utf-8")).digest()).decode("ascii")


def _frame(text):
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    head = bytes([0x81])
    length = len(payload)
    if length < 126:
        head += bytes([0x80 | length])
    elif length < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", length)
    return head + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


def _exactly(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("closed")
        data += chunk
    return data


def _read(sock):
    while True:
        first, second = _exactly(sock, 2)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", _exactly(sock, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _exactly(sock, 8))[0]
        mask = _exactly(sock, 4) if second & 0x80 else None
        payload = _exactly(sock, length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        opcode = first & 0x0F
        if opcode == 0x8:
            raise ConnectionError("closed")
        if opcode == 0x1:
            return json.loads(payload.decode("utf-8"))


def request(config, request_types, connect=socket.create_connection):
    """One connection: identify, send each request, return {type: success}. Never raises."""
    results = {}
    try:
        sock = connect(("127.0.0.1", config["port"]), timeout=TIMEOUT_S)
    except OSError:
        return results
    try:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock.sendall(("GET / HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n"
                      "Sec-WebSocket-Protocol: obswebsocket.json\r\n\r\n" % (config["port"], key)).encode("ascii"))
        # One byte at a time: the server's hello can follow the header in the same packet, and must stay unread.
        head = b""
        while not head.endswith(b"\r\n\r\n"):
            chunk = sock.recv(1)
            if not chunk:
                return results
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            return results
        hello = _read(sock)
        identify = {"rpcVersion": 1}
        challenge = ((hello.get("d") or {}).get("authentication")) or None
        if challenge:
            if not config.get("password"):
                return results
            identify["authentication"] = auth_string(config["password"], challenge["salt"], challenge["challenge"])
        sock.sendall(_frame(json.dumps({"op": 1, "d": identify})))
        if _read(sock).get("op") != 2:
            return results
        for index, kind in enumerate(request_types):
            sock.sendall(_frame(json.dumps({"op": 6, "d": {"requestType": kind, "requestId": "r%d" % index}})))
            while True:
                message = _read(sock)
                if message.get("op") == 7 and (message.get("d") or {}).get("requestId") == "r%d" % index:
                    results[kind] = ((message["d"].get("requestStatus") or {}).get("result")) is True
                    break
    except (OSError, ValueError, KeyError, ConnectionError, struct.error):
        return results
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return results


def keep_recording(data_dir):
    """Ask the capture tool, in the background, to save its replay buffer and mark the recording."""
    config = load(data_dir)
    if config is None:
        return False
    threading.Thread(target=request, args=(config, ("SaveReplayBuffer", "CreateRecordChapter")),
                     name="obs", daemon=True).start()
    return True
