"""DT1 bridge: cursor, spool, contract, transport, outbox, attachment."""
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from domus_helper import commands
from domus_helper.attachment import AttachmentMonitor
from domus_helper.bridge import Bridge, main
from domus_helper.contract import ContractError, validate_heartbeat, validate_observation
from domus_helper.cursor import TelemetryCursor
from domus_helper.spool import OutboxConflict, Spool
from domus_helper.transport import AshleyClient, load_credentials


NOW = 1_700_000_000_000


def sample(now=NOW, **overrides):
    body = {
        "v": 1,
        "observation_id": "obs-1",
        "world": "willow",
        "branch": "main",
        "session": "sess",
        "attachment": "attached",
        "body": "note",
        "snapshot": "snap",
        "seq": 1,
        "source_time_ms": now,
        "expires_at_ms": now + 60_000,
        "lineage_class": "HOUSEHOLD",
        "percepts": [{"kind": "light", "salience": 0.5, "facts": {"n": 1}}],
    }
    body.update(overrides)
    return body


def test_contract_accepts_sample_and_rejects_each_rule():
    assert validate_observation(sample(), NOW)["observation_id"] == "obs-1"
    heart = {"v": 1, "helper_session": "abc", "sent_at_ms": NOW, "attached": True, "world": "", "probe_version": "2.5.1"}
    assert validate_heartbeat(heart)["world"] == ""
    with pytest.raises(ContractError):
        validate_observation(sample(extra=1), NOW)
    with pytest.raises(ContractError):
        validate_observation(sample(percepts=[
            {"kind": "k%d" % i, "salience": 0, "facts": {}} for i in range(33)
        ]), NOW)
    with pytest.raises(ContractError):
        validate_observation(sample(percepts=[{
            "kind": "light", "salience": 0, "facts": {"blob": "x" * 2100},
        }]), NOW)
    with pytest.raises(ContractError):
        validate_observation(sample(observation_id="has space"), NOW)
    with pytest.raises(ContractError):
        validate_observation(sample(percepts=[{"kind": "Bad", "salience": 0, "facts": {}}]), NOW)
    with pytest.raises(ContractError) as expired:
        validate_observation(sample(source_time_ms=NOW - 10_000, expires_at_ms=NOW - 1), NOW)
    assert expired.value.code == "expired"
    with pytest.raises(ContractError) as window:
        validate_observation(sample(expires_at_ms=NOW + 600_001), NOW)
    assert window.value.code == "invalid_body"
    with pytest.raises(ContractError) as skew:
        validate_observation(sample(source_time_ms=NOW + 120_001, expires_at_ms=NOW + 180_000), NOW)
    assert skew.value.code == "clock_skew"
    with pytest.raises(ContractError):
        validate_heartbeat({**heart, "nope": 1})


def _session(paths):
    path = paths.telemetry / "ashley_e1_01234567-89ab-cdef-0123-456789abcdef.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append(path, obj):
    with path.open("ab") as handle:
        handle.write(json.dumps(obj).encode("utf-8") + b"\n")


def _row(seq, kind="speed_event", wall=NOW, **extra):
    body = {"event_kind": kind, "written_sequence": seq, "wall_timestamp_ms": wall, "sims_build": "1.128.90.1030", "probe_version": "2.5.1"}
    body.update(extra)
    return body


def test_cursor_no_rescan_partial_rotation_resume(paths, tmp_path):
    session = _session(paths)
    db = tmp_path / "spool.db"
    cursor = TelemetryCursor(Spool(db), paths)
    _append(session, _row(1))
    with session.open("ab") as handle:
        handle.write(b"{\"event_kind\": \"speed_event\", \"cut\":")
    assert [row["written_sequence"] for row in cursor.read_new()] == [1]
    assert cursor.read_new() == []
    with session.open("ab") as handle:
        handle.write(b" true}\n")
    held = cursor.read_new()
    assert len(held) == 1 and "written_sequence" not in held[0]
    assert TelemetryCursor(Spool(db), paths).read_new() == []
    _append(session.with_name(session.name + ".1"), _row(2))
    assert [row["written_sequence"] for row in TelemetryCursor(Spool(db), paths).read_new()] == [2]


def test_a_rotated_segment_is_not_a_gap(tmp_path):
    # GL12: after a rotation the newest row is the last one written, in the newest segment.
    spool = Spool(tmp_path / "spool.db")
    for offset, seq in ((0, 1), (10, 2), (20, 3)):
        spool.ingest("sess.jsonl", 0, offset, _row(seq), raw_len=10)
    spool.ingest("sess.jsonl", 1, 0, _row(4), raw_len=10)
    spool.ingest("sess.jsonl", 1, 10, _row(5), raw_len=10)
    spool.ingest("sess.jsonl", 1, 20, _row(6), raw_len=10)
    assert [row["kind"] for row in spool.gaps()] == []
    spool.ingest("sess.jsonl", 1, 30, _row(8), raw_len=10)
    assert [json.loads(row["detail_json"]) for row in spool.gaps()] == [{"from": 6, "to": 8}]
    spool.close()


def test_spool_gap_drop_and_cap(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    spool.row_cap = 2
    spool.ingest("sess.jsonl", 0, 0, _row(1), raw_len=10)
    spool.ingest("sess.jsonl", 0, 10, _row(4), raw_len=10)
    spool.ingest("sess.jsonl", 0, 20, _row(5, kind="dropped_summary", reason="QUEUE_SATURATION"), raw_len=10)
    spool.ingest("sess.jsonl", 0, 30, _row(6), raw_len=10)
    gaps = spool.gaps()
    kinds = [row["kind"] for row in gaps]
    assert "gap" in kinds and "drop" in kinds and "cap" in kinds
    gap = next(row for row in gaps if row["kind"] == "gap")
    assert json.loads(gap["detail_json"]) == {"from": 1, "to": 4}
    drop = next(row for row in gaps if row["kind"] == "drop")
    assert json.loads(drop["detail_json"])["reason"] == "QUEUE_SATURATION"
    cap = next(row for row in gaps if row["kind"] == "cap")
    assert json.loads(cap["detail_json"])["count"] >= 1
    assert spool.row_count() <= 2


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.server.seen.append(self.path)
        status = self.server.statuses.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, fmt, *args):
        logging.getLogger("domus.test.http").info(fmt, *args)


@pytest.fixture
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.statuses = []
    server.seen = []
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def test_transport_status_map_and_secret_repr(http_server, caplog):
    token = "t" * 40
    url = "http://127.0.0.1:%d" % http_server.server_address[1]
    client = AshleyClient(url, token, timeout_s=2)
    assert token not in repr(client)
    assert url not in repr(client)
    caplog.set_level(logging.DEBUG)
    expected = {
        202: "admitted", 200: "duplicate", 409: "conflict", 410: "expired",
        400: "rejected", 401: "unauthorized", 413: "too_large", 500: "unavailable",
    }
    http_server.statuses[:] = list(expected)
    for status, kind in expected.items():
        result = client.post_observation(sample(), now_ms=NOW)
        assert result.kind == kind and result.status == status
    http_server.statuses[:] = [200]
    assert client.post_heartbeat({
        "v": 1, "helper_session": "abc", "sent_at_ms": NOW, "attached": True,
    }).kind == "admitted"
    logged = caplog.text
    assert token not in logged
    dead = AshleyClient("http://127.0.0.1:1", token, timeout_s=0.2)
    assert dead.post_observation(sample(), now_ms=NOW).kind == "unavailable"
    assert dead.post_observation(sample(extra=1), now_ms=NOW).kind == "rejected"


def test_load_credentials(paths, monkeypatch, tmp_path):
    monkeypatch.delenv("DOMUS_ASHLEY_URL", raising=False)
    monkeypatch.delenv("DOMUS_ASHLEY_TOKEN", raising=False)
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert load_credentials(paths).disabled == "missing_url"
    (tmp_path / "ashley_url").write_text("http://127.0.0.1:9\n", encoding="utf-8")
    assert load_credentials(paths).disabled == "missing_token"
    (tmp_path / "ashley_token").write_text("short\n", encoding="utf-8")
    assert load_credentials(paths).disabled == "short_token"
    (tmp_path / "ashley_token").write_text("k" * 32, encoding="utf-8")
    loaded = load_credentials(paths)
    assert loaded.disabled is None and loaded.url == "http://127.0.0.1:9" and loaded.token == "k" * 32
    monkeypatch.setenv("DOMUS_ASHLEY_URL", "http://127.0.0.1:8")
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "e" * 32)
    override = load_credentials(paths)
    assert override.url == "http://127.0.0.1:8" and override.token == "e" * 32


def test_kv_is_written_only_when_its_value_changes(tmp_path):
    # HE17: an unchanged value is not rewritten; a changed one is.
    from domus_helper.spool import Spool
    spool = Spool(tmp_path / "spool.db")
    spool.put_kv("k", "v")
    before = spool._con.total_changes
    spool.put_kv("k", "v")
    spool.put_many_kv({"k": "v"})
    assert spool._con.total_changes == before
    spool.put_many_kv({"k": "w", "j": "1"})
    assert spool._con.total_changes == before + 2
    assert spool.get_kv("k") == "w" and spool.get_kv("j") == "1"
    spool.close()


def test_outbox_idempotent_conflict_backoff_expiry_auth(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    spool.enqueue_observation(sample(), NOW)
    spool.enqueue_observation(sample(), NOW)
    assert spool.outbox_counts()["pending"] == 1
    with pytest.raises(OutboxConflict):
        spool.enqueue_observation(sample(body="other"), NOW)

    class Script:
        def __init__(self, kinds):
            self.kinds = list(kinds)
            self.sent = 0

        def post_observation(self, body, now_ms=None):
            self.sent += 1
            kind = self.kinds.pop(0)
            return type("R", (), {"kind": kind, "status": 0})()

    unavailable = Script(["unavailable", "unavailable"])
    assert spool.flush(unavailable, NOW) is None
    row = spool.outbox_row("obs-1")
    assert row["attempts"] == 1 and row["next_attempt_ms"] == NOW + 1000 and row["state"] == "pending"
    assert spool.flush(unavailable, NOW + 1000) is None
    row = spool.outbox_row("obs-1")
    assert row["attempts"] == 2 and row["next_attempt_ms"] == NOW + 1000 + 2000

    expired = sample(observation_id="old", source_time_ms=NOW - 50_000, expires_at_ms=NOW - 1)
    # enqueue validates expiry against now, so store with a future expiry then age it.
    spool.enqueue_observation(sample(observation_id="old"), NOW - 120_000)
    spool.set_expires("old", NOW - 1)
    quiet = Script([])
    spool.flush(quiet, NOW)
    assert quiet.sent == 0
    assert spool.outbox_row("old")["state"] == "expired"

    spool.enqueue_observation(sample(observation_id="z1"), NOW)
    spool.enqueue_observation(sample(observation_id="z2"), NOW)
    auth = Script(["unauthorized", "admitted"])
    assert spool.flush(auth, NOW) == "auth_failed"
    assert auth.sent == 1
    assert spool.outbox_row("z1")["state"] == "pending"
    assert spool.outbox_row("z2")["state"] == "pending"

    spool.flush(Script(["admitted", "conflict", "rejected"]), NOW + 3000)
    assert spool.outbox_row("obs-1")["state"] == "acked"
    assert spool.outbox_row("z1")["state"] == "conflict"
    assert spool.outbox_row("z2")["state"] == "rejected"


def test_attachment_states_and_one_shot_sleep():
    monitor = AttachmentMonitor(detected_build="1.128.90.1030")
    fresh = _row(1, wall=NOW)
    assert monitor.observe(NOW, 0, (1, "t"), fresh)["state"] == "attached"
    assert monitor.observe(NOW + 31_000, 31_000, (1, "t"), fresh)["state"] == "stale"
    closed = _row(2, kind="session_close", wall=NOW, close_reason="DISARM_CLEAN")
    assert monitor.observe(NOW + 31_000, 62_000, None, closed)["state"] == "game_exited"
    assert monitor.observe(NOW + 31_000, 93_000, None, fresh)["state"] == "crash_suspected"
    mismatch = _row(3, wall=NOW + 31_000, sims_build="9.9.9.9")
    got = monitor.observe(NOW + 31_000, 124_000, (1, "t"), mismatch)
    assert got["state"] == "version_mismatch" and got["telemetry_only"] is True
    slept = monitor.observe(NOW + 100_000, 130_000, (1, "t"), {**mismatch, "wall_timestamp_ms": NOW + 100_000})
    assert slept["state"] == "sleep_resume"
    after = monitor.observe(NOW + 101_000, 131_000, (1, "t"), {**mismatch, "wall_timestamp_ms": NOW + 101_000})
    assert after["state"] == "version_mismatch"


def test_bridge_heartbeat_cadence_and_status_has_no_secret(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_ASHLEY_URL", "http://127.0.0.1:9")
    token = "s" * 48
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", token)
    session = _session(paths)
    _append(session, _row(1, wall=NOW))
    sent = []

    class Fake:
        def post_heartbeat(self, body):
            sent.append(body)
            return type("R", (), {"kind": "admitted", "status": 200})()

        def post_observation(self, body, now_ms=None):
            raise AssertionError("no observation")

        def __repr__(self):
            return "Fake"

    mono_at = {"ms": 0}

    def mono():
        return mono_at["ms"]

    bridge = Bridge(paths, client=Fake(), process=(1, "t"), detected_build="1.128.90.1030", mono=mono)
    bridge.tick(NOW)
    assert bridge.status()["attachment"] == "attached"
    mono_at["ms"] = 59_000
    bridge.tick(NOW + 59_000)
    mono_at["ms"] = 60_000
    bridge.tick(NOW + 60_000)
    # The minute cadence, except that a change of attachment goes out at once (stale at 59 s).
    assert [body["sent_at_ms"] for body in sent] == [NOW, NOW + 59_000]
    assert [body["attached"] for body in sent] == [True, False]
    assert sent[0]["v"] == 1 and len(sent[0]["helper_session"]) == 32
    status = bridge.status()
    blob = json.dumps(status)
    assert token not in blob and "127.0.0.1" not in blob
    assert status["transport"]["enabled"] is True
    assert status["attachment"] == "stale"
    assert status["outbox"]["pending"] == 0


def test_probe_version_warns_once_and_withholds_camera(paths, tmp_path, monkeypatch, capsys):
    from domus_helper.vendor import schema as probe_schema

    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    # W3h: the attached bridge sends the pace command; the vendored cmdbox learns it at the W3p merge.
    monkeypatch.setattr(commands, "publish", lambda *args, **kwargs: "stub")

    class Fake:
        def post_heartbeat(self, body):
            return type("R", (), {"kind": "admitted", "status": 200})()

        def post_observation(self, body, now_ms=None):
            return type("R", (), {"kind": "admitted", "status": 200})()

    def bridge_for(version):
        # SEAM3-21: the probe version is the one of a session's first row, and each game run has its own session file.
        run = 2 if version == probe_schema.PROBE_VERSION else 1
        session = paths.telemetry / ("ashley_e1_01234567-89ab-cdef-0123-%012d.jsonl" % run)
        session.parent.mkdir(parents=True, exist_ok=True)
        _append(session, _row(1, wall=NOW, probe_version=version))
        bridge = Bridge(paths, client=Fake(), process=(1, "t"), detected_build="1.128.90.1030",
                        mono=lambda: 0)
        seen = []
        bridge.overlay.publish = lambda now, attached: bridge.overlay.__dict__.__setitem__(
            "published", {"mode": "live"})
        bridge.director.tick = lambda now, live: seen.append(live)
        return bridge, seen

    older, older_live = bridge_for("2.20.1")
    older.tick(NOW)
    older.tick(NOW + 1)
    warning = "probe 2.20.1 is installed; this helper expects %s" % probe_schema.PROBE_VERSION
    assert capsys.readouterr().out.strip().splitlines() == [warning]
    assert older.status()["probe"] == {
        "installed": "2.20.1", "expected": probe_schema.PROBE_VERSION, "match": False}
    assert older_live == [False, False]

    current, current_live = bridge_for(probe_schema.PROBE_VERSION)
    current.tick(NOW)
    assert capsys.readouterr().out == ""
    assert current.status()["probe"]["match"] is True
    assert current_live == [True]


def test_cli_once_and_interval(paths, tmp_path, monkeypatch):
    import domus_helper.bridge as bridge_module
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(paths.sims_root))
    monkeypatch.delenv("DOMUS_ASHLEY_URL", raising=False)
    monkeypatch.delenv("DOMUS_ASHLEY_TOKEN", raising=False)
    # OP19: the archive and the string indexes are other tests' business; this one checks the CLI loop.
    monkeypatch.setattr(bridge_module, "_archive_quietly", lambda now: None)
    monkeypatch.setattr(bridge_module, "_strings_quietly", lambda: None)
    assert main(["--once"]) == 0
    calls = {"n": 0}

    def tick(self, now):
        calls["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(Bridge, "tick", tick)
    assert main(["--interval", "5"]) == 0
    assert calls["n"] == 1


def test_cli_with_game_lives_as_long_as_the_game(paths, tmp_path, monkeypatch):
    import domus_helper.bridge as bridge_module
    from domus_helper import fingerprints
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(paths.sims_root))
    monkeypatch.delenv("DOMUS_ASHLEY_URL", raising=False)
    monkeypatch.delenv("DOMUS_ASHLEY_TOKEN", raising=False)
    clock = {"s": 1_000_000.0}
    monkeypatch.setattr(bridge_module.time, "time", lambda: clock["s"])
    monkeypatch.setattr(bridge_module.time, "sleep", lambda seconds: clock.__setitem__("s", clock["s"] + seconds))
    monkeypatch.setattr(bridge_module, "_archive_quietly", lambda now: None)
    monkeypatch.setattr(bridge_module, "_strings_quietly", lambda: None)
    ticks = []
    monkeypatch.setattr(Bridge, "tick", lambda self, now: ticks.append(now))
    # The watcher saw the game, but the bridge's own check can't find it (still launching, or
    # already closed): the bridge keeps ticking for the drain, then exits.
    monkeypatch.setattr(fingerprints, "_process", lambda: None)
    assert main(["--interval", "5", "--with-game"]) == 0
    assert len(ticks) == bridge_module.GAME_DRAIN_S // 5
    ticks.clear()
    # The game runs for 30 s, then closes: the bridge keeps ticking for the drain, then exits.
    closes_at = clock["s"] + 30
    monkeypatch.setattr(fingerprints, "_process", lambda: (4242, "0:00:01") if clock["s"] < closes_at else None)
    assert main(["--interval", "5", "--with-game"]) == 0
    assert len(ticks) == 6 + bridge_module.GAME_DRAIN_S // 5 - 1
    assert ticks[-1] - ticks[5] == (bridge_module.GAME_DRAIN_S - 5) * 1000


def test_bridge_heartbeat_goes_at_once_when_the_game_attaches(paths, tmp_path, monkeypatch):
    """Live 2026-10-08: the bridge starts before the save loads; its first heartbeat says not
    attached, and her first game moments waited a minute for the next one."""
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_ASHLEY_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "s" * 48)
    session = _session(paths)
    _append(session, _row(1, wall=NOW - 120_000))
    sent = []

    class Fake:
        def post_heartbeat(self, body):
            sent.append(body)
            return type("R", (), {"kind": "admitted", "status": 200})()

        def post_observation(self, body, now_ms=None):
            return type("R", (), {"kind": "admitted", "status": 202})()

    mono_at = {"ms": 0}
    bridge = Bridge(paths, client=Fake(), process=(1, "t"), detected_build="1.128.90.1030",
                    mono=lambda: mono_at["ms"])
    bridge.tick(NOW)
    assert [body["attached"] for body in sent] == [False]
    _append(session, _row(2, wall=NOW + 5_000))
    mono_at["ms"] = 5_000
    bridge.tick(NOW + 5_000)
    assert [body["attached"] for body in sent] == [False, True]
    mono_at["ms"] = 6_000
    bridge.tick(NOW + 6_000)
    assert len(sent) == 2


def test_no_probe_warning_from_the_previous_sessions_file(paths, tmp_path, monkeypatch, capsys):
    # Live 2026-10-26 (bridge.log 04:57:49Z): at start the newest file was still the 10-13 session (probe 2.41.1), the
    # running game had not written its own yet, and the bridge said "probe 2.41.1 is installed" while 2.41.2 was.
    from domus_helper.attachment import STALE_AFTER_MS
    from domus_helper.vendor import schema as probe_schema

    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(commands, "publish", lambda *args, **kwargs: "stub")
    old = paths.telemetry / "ashley_e1_01234567-89ab-cdef-0123-000000000001.jsonl"
    old.parent.mkdir(parents=True, exist_ok=True)
    _append(old, _row(1, wall=NOW - 13 * 86_400_000, probe_version="2.0.0"))
    bridge = Bridge(paths, client=None, process=(1, "t"), detected_build="1.128.90.1030", mono=lambda: 0)
    bridge.overlay.publish = lambda now, attached: None
    if bridge.director is not None:
        bridge.director.tick = lambda now, live: None
    bridge.tick(NOW)
    assert "is installed; this helper expects" not in capsys.readouterr().out
    new = paths.telemetry / "ashley_e1_01234567-89ab-cdef-0123-000000000002.jsonl"
    _append(new, _row(1, wall=NOW + STALE_AFTER_MS // 2, probe_version=probe_schema.PROBE_VERSION))
    bridge.tick(NOW + STALE_AFTER_MS // 2 + 1)
    assert "is installed; this helper expects" not in capsys.readouterr().out
