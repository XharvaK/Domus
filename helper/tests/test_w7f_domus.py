"""W7f (A9-1, A9-2, A9-4, A9-9): the act round trip, the flush budget, Ashley's refusals and the probe gate."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from domus_helper.acts import ActCourier
from domus_helper.bridge import Bridge
from domus_helper.spool import Spool
from domus_helper.transport import AshleyClient

NOW = 1_700_000_000_000


def sample(now=NOW, **overrides):
    body = {
        "v": 1, "observation_id": "obs-1", "world": "willow", "branch": "main", "session": "sess",
        "attachment": "attached", "body": "note", "snapshot": "snap", "seq": 1,
        "source_time_ms": now, "expires_at_ms": now + 60_000, "lineage_class": "HOUSEHOLD",
        "percepts": [{"kind": "light", "salience": 0.5, "facts": {"n": 1}}],
    }
    body.update(overrides)
    return body


class _Refusing(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        status, body = self.server.answers.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass


@pytest.fixture
def ashley():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Refusing)
    server.answers = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


def _client(server):
    return AshleyClient("http://127.0.0.1:%d" % server.server_address[1], "t" * 40, timeout_s=2)


# A9-4: the server's reason reaches the caller, and a clock or unknown-key refusal is retried, not final.

def test_a_400_carries_the_servers_reason(ashley):
    client = _client(ashley)
    ashley.answers[:] = [(400, {"error": "clock_skew"})]
    result = client.post_observation(sample(), now_ms=NOW)
    assert (result.kind, result.status, result.reason) == ("rejected", 400, "clock_skew")


def test_clock_skew_and_an_unknown_key_are_retried_with_backoff(tmp_path, ashley):
    spool = Spool(tmp_path / "spool.db")
    spool.enqueue_observation(sample(), NOW)
    client = _client(ashley)
    ashley.answers[:] = [(400, {"error": "clock_skew"}), (400, {"error": "invalid_body"})]
    spool.flush(client, NOW)
    row = spool.outbox_row("obs-1")
    assert row["state"] == "pending" and row["last_status"] == "refused:clock_skew" and row["next_attempt_ms"] == NOW + 1000
    spool.flush(client, NOW + 1000)
    row = spool.outbox_row("obs-1")
    assert row["state"] == "pending" and row["last_status"] == "refused:invalid_body" and row["next_attempt_ms"] == NOW + 1000 + 2000
    assert spool.refusal_counts() == {"invalid_body": 1}


def test_another_refusal_stays_final_and_says_why(tmp_path, ashley):
    spool = Spool(tmp_path / "spool.db")
    spool.enqueue_observation(sample(), NOW)
    ashley.answers[:] = [(400, {"error": "not_png"})]
    spool.flush(_client(ashley), NOW)
    row = spool.outbox_row("obs-1")
    assert row["state"] == "rejected" and row["last_status"] == "refused:not_png"
    assert spool.refusal_counts() == {"not_png": 1}


# A9-2: acts are carried before the observations are flushed, and one flush has a time budget.

class _Posts:
    def __init__(self):
        self.sent = 0

    def post_observation(self, body, now_ms=None):
        self.sent += 1
        return type("R", (), {"kind": "admitted", "status": 202, "reason": None})()


def test_a_flush_stops_at_its_time_budget_and_keeps_the_rest_due(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    for index in range(5):
        spool.enqueue_observation(sample(observation_id="obs-%d" % index), NOW)
    clock = {"t": 0.0}

    def tick_clock():
        clock["t"] += 1.0
        return clock["t"]

    posts = _Posts()
    spool.flush(posts, NOW, budget_s=3.0, clock=tick_clock)
    assert posts.sent == 2
    assert spool.outbox_counts()["pending"] == 3


def test_the_act_round_trip_runs_before_the_observation_flush(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOMUS_ASHLEY_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "s" * 48)
    order = []

    class Fake:
        def post_heartbeat(self, body):
            order.append("heartbeat")
            return type("R", (), {"kind": "admitted", "status": 200})()

        def post_observation(self, body, now_ms=None):
            order.append("observation")
            return type("R", (), {"kind": "admitted", "status": 202, "reason": None})()

        def sync_acts(self, body):
            order.append("acts")
            return {"status": "ok", "applied": 0, "acts": [], "planned": 0, "snapshots": []}

        def __repr__(self):
            return "Fake"

    bridge = Bridge(paths, client=Fake(), process=(1, "t"), detected_build="1.128.90.1030", mono=lambda: 0)
    bridge.spool.enqueue_observation(sample(), NOW)
    bridge.tick(NOW)
    assert order.index("acts") < order.index("observation")


# A9-1: a short detach is not the end of an act the game may still finish.

class _Sync:
    def __init__(self):
        self.bodies = []

    def sync_acts(self, body):
        self.bodies.append(body)
        return {"status": "ok", "applied": 0, "acts": [], "planned": 0, "snapshots": []}


def _courier(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    published = []
    return ActCourier(spool, lambda name, args: published.append((name, args))), published


def test_a_short_detach_does_not_mark_a_running_act_unknown(tmp_path):
    courier, _ = _courier(tmp_path)
    courier._known["act1"] = {"written_ms": NOW, "answered": True, "pushed_ms": NOW}
    client = _Sync()
    courier.tick(client, "sess", NOW + 1000, False)
    courier.tick(client, "sess", NOW + 60_000, False)
    courier.tick(client, "sess", NOW + 61_000, True)
    assert [event["phase"] for event in courier._events] == []
    courier.tick(client, "sess", NOW + 62_000, False)
    courier.tick(client, "sess", NOW + 62_000 + 120_000, False)
    sent = [(event["phase"], event.get("detail", {}).get("code")) for body in client.bodies for event in body["events"]]
    assert sent == [("unknown", "GAME_DETACHED")]


# A9-9: a probe too old for what an act needs refuses it with its reason, and sends nothing to the game.

def _act(act_id, **extra):
    return {"act_id": act_id, "object_id": "1001", "guid64": "14000", **extra}


def test_an_owner_act_is_refused_by_a_probe_that_predates_owner(tmp_path):
    courier, published = _courier(tmp_path)
    client = type("C", (), {"sync_acts": lambda self, body: {"status": "ok", "applied": 0, "acts": [_act("a1", owner=True)],
                                                             "planned": 0, "snapshots": []}})()
    courier.tick(client, "sess", NOW, True, probe="2.23.0")
    assert published == []
    assert [(event["act_id"], event["phase"], event["detail"]["code"]) for event in courier._events] == [("a1", "rejected", "PROBE_TOO_OLD")]


def test_an_owner_act_goes_to_a_probe_new_enough_for_it(tmp_path):
    courier, published = _courier(tmp_path)
    client = type("C", (), {"sync_acts": lambda self, body: {"status": "ok", "applied": 0, "acts": [_act("a2", owner=True)],
                                                             "planned": 0, "snapshots": []}})()
    courier.tick(client, "sess", NOW, True, probe="2.24.0")
    assert published == [("act", {"act_id": "a2", "object_id": "1001", "guid64": "14000", "owner": True})]
