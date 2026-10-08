"""SNAPSHOT helper side: the PNG encoder, the downscale, one send per requested id, the failure
reasons, the CLI and the transport path. No window is captured here."""
import base64
import json
import struct
import types
import urllib.error
import urllib.request
import zlib

import pytest

from domus_helper import snapshot
from domus_helper.snapshot import SnapshotFailed, downscale_bgra, encode_png_rgb, handle_requests
from domus_helper.transport import SNAPSHOT_TIMEOUT_S, AshleyClient


@pytest.fixture(autouse=True)
def nothing_handled_yet(monkeypatch):
    monkeypatch.setattr(snapshot, "_HANDLED", set())


def read_png(data):
    """The chunks of a PNG as (type, data), with the signature and every CRC checked."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks = []
    pos = 8
    while pos < len(data):
        length, = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        crc, = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        assert zlib.crc32(kind + body) & 0xFFFFFFFF == crc
        chunks.append((kind, body))
        pos += 12 + length
    assert pos == len(data)
    return chunks


def test_the_png_encoder_writes_a_decodable_8_bit_rgb_picture():
    w, h = 5, 3
    rgb = bytes((index * 7) % 256 for index in range(w * h * 3))
    chunks = read_png(encode_png_rgb(rgb, w, h))
    assert [kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", chunks[0][1]) == (w, h, 8, 2, 0, 0, 0)
    raw = zlib.decompress(chunks[1][1])
    row = 1 + 3 * w
    assert len(raw) == h * row
    assert all(raw[y * row] == 0 for y in range(h))
    assert b"".join(raw[y * row + 1:(y + 1) * row] for y in range(h)) == rgb
    assert chunks[2][1] == b""


def test_the_png_encoder_refuses_a_size_that_does_not_match_the_bytes():
    with pytest.raises(ValueError):
        encode_png_rgb(b"\x00" * 10, 2, 2)
    with pytest.raises(ValueError):
        encode_png_rgb(b"", 0, 0)


def test_the_downscale_keeps_at_most_1600_wide_on_an_integer_step():
    cases = {
        (3200, 1800): (1600, 900),
        (1920, 1080): (960, 540),
        (3840, 2160): (1280, 720),
        (1000, 700): (1000, 700),
        (1601, 3): (801, 2),
    }
    for (w, h), expected in cases.items():
        rgb, out_w, out_h = downscale_bgra(bytes(w * h * 4), w, h)
        assert (out_w, out_h) == expected
        assert out_w <= 1600
        assert len(rgb) == out_w * out_h * 3


def test_the_downscale_reads_the_sampled_pixels_and_turns_bgra_into_rgb():
    w, h = 4, 4
    buf = bytearray()
    for y in range(h):
        for x in range(w):
            # red = 30x + y, green = 20x + y, blue = 10x + y, alpha = 255 (stored as B, G, R, A)
            buf += bytes([10 * x + y, 20 * x + y, 30 * x + y, 255])
    rgb, out_w, out_h = downscale_bgra(bytes(buf), w, h, max_w=2)
    assert (out_w, out_h) == (2, 2)
    expected = bytearray()
    for x, y in [(0, 0), (2, 0), (0, 2), (2, 2)]:
        expected += bytes([30 * x + y, 20 * x + y, 10 * x + y])
    assert rgb == bytes(expected)


class FakeClient:
    def __init__(self, fail_on=()):
        self.bodies = []
        self.fail_on = set(fail_on)

    def post_snapshot(self, body):
        if body["snapshot_id"] in self.fail_on:
            raise OSError("no route")
        self.bodies.append(body)
        return {"status": "ok"}


PNG = b"\x89PNG\r\n\x1a\nfake picture"


def test_a_requested_picture_is_posted_once_with_its_png_as_base64():
    client = FakeClient()
    calls = []

    def capture():
        calls.append(1)
        return PNG

    handle_requests([{"snapshot_id": "s-1"}], client, capture, helper_session="sess")
    handle_requests([{"snapshot_id": "s-1"}], client, capture, helper_session="sess")
    assert len(calls) == 1
    assert client.bodies == [{"v": 1, "helper_session": "sess", "snapshot_id": "s-1",
                              "png_base64": base64.b64encode(PNG).decode("ascii")}]


def test_each_capture_failure_is_posted_with_its_reason():
    client = FakeClient()
    outcomes = {
        "s-min": SnapshotFailed("game_minimized"),
        "s-none": SnapshotFailed("no_game_window"),
        "s-bad": RuntimeError("boom"),
        "s-empty": b"",
    }

    def capture_for(snapshot_id):
        def capture():
            outcome = outcomes[snapshot_id]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return capture

    for snapshot_id in outcomes:
        handle_requests([snapshot_id], client, capture_for(snapshot_id), helper_session="sess")
    assert [(body["snapshot_id"], body["failed"]) for body in client.bodies] == [
        ("s-min", "game_minimized"), ("s-none", "no_game_window"),
        ("s-bad", "capture_failed"), ("s-empty", "capture_failed"),
    ]
    assert all("png_base64" not in body for body in client.bodies)


def test_an_id_is_never_sent_again_even_when_its_post_failed():
    client = FakeClient(fail_on={"s-1"})
    calls = []

    def capture():
        calls.append(1)
        return PNG

    handle_requests(["s-1"], client, capture, helper_session="sess")
    client.fail_on.clear()
    handle_requests(["s-1"], client, capture, helper_session="sess")
    assert len(calls) == 1
    assert client.bodies == []


def test_a_failed_post_does_not_stop_the_others_and_nothing_raises():
    client = FakeClient(fail_on={"s-1"})
    handle_requests(["s-1", {"snapshot_id": "s-2"}, {"nope": 1}, 7, ""], client,
                    lambda: PNG, helper_session="sess")
    assert [body["snapshot_id"] for body in client.bodies] == ["s-2"]


def test_a_response_that_is_not_a_list_is_ignored():
    client = FakeClient()
    handle_requests({"snapshot_id": "s-1"}, client, lambda: PNG, helper_session="sess")
    handle_requests(None, client, lambda: PNG, helper_session="sess")
    assert client.bodies == []


def test_no_game_process_is_no_game_window(monkeypatch):
    monkeypatch.setattr(snapshot.fingerprint_reader, "_process", lambda: None)
    with pytest.raises(SnapshotFailed) as failed:
        snapshot.capture_game_window()
    assert failed.value.code == "no_game_window"


def test_the_cli_writes_the_picture_here_or_prints_the_reason(tmp_path, monkeypatch, capsys):
    out = tmp_path / "house.png"
    monkeypatch.setattr(snapshot, "capture_game_window", lambda: PNG)
    assert snapshot.main(["test", str(out)]) == 0
    assert out.read_bytes() == PNG
    assert json.loads(capsys.readouterr().out) == {"bytes": len(PNG)}

    def minimised():
        raise SnapshotFailed("game_minimized")

    monkeypatch.setattr(snapshot, "capture_game_window", minimised)
    missing = tmp_path / "none.png"
    assert snapshot.main(["test", str(missing)]) == 1
    assert not missing.exists()
    assert json.loads(capsys.readouterr().out) == {"failed": "game_minimized"}


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_post_snapshot_uses_its_path_the_token_and_a_30_second_timeout(monkeypatch):
    token = "t" * 40
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request.full_url, request.get_method(), request.get_header("X-domus-token"),
                     json.loads(request.data), timeout))
        return FakeResponse(b'{"status":"ok"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = AshleyClient("http://ashley.invalid/", token, timeout_s=10)
    body = {"v": 1, "helper_session": "sess", "snapshot_id": "s-1", "failed": "no_game_window"}
    assert client.post_snapshot(body) == {"status": "ok"}
    assert client.sync_acts({"v": 1, "helper_session": "sess", "events": []}) == {"status": "ok"}
    assert SNAPSHOT_TIMEOUT_S == 30
    assert seen[0] == ("http://ashley.invalid/domus/snapshot", "POST", token, body, 30)
    assert seen[1][1:] == ("POST", token, {"v": 1, "helper_session": "sess", "events": []}, 10)


def test_post_snapshot_is_none_when_the_round_trip_fails(monkeypatch):
    def down(request, timeout):
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    client = AshleyClient("http://ashley.invalid", "t" * 40, timeout_s=10)
    assert client.post_snapshot({"v": 1, "helper_session": "s", "snapshot_id": "s-1", "failed": "x"}) is None


def test_background_claims_here_and_posts_on_the_runner(monkeypatch):
    snapshot._HANDLED.clear()
    monkeypatch.setattr(snapshot, "capture_game_window", lambda: (_ for _ in ()).throw(SnapshotFailed("no_game_window")))
    client = types.SimpleNamespace(posted=[], post_snapshot=lambda body: client.posted.append(body))
    runs = []
    snapshot.handle_requests_in_background([{"snapshot_id": "bg-1"}], client, helper_session="s", start=runs.append)
    snapshot.handle_requests_in_background([{"snapshot_id": "bg-1"}], client, helper_session="s", start=runs.append)
    assert len(runs) == 1 and client.posted == []
    runs[0]()
    assert [(body["snapshot_id"], body["failed"]) for body in client.posted] == [("bg-1", "no_game_window")]
