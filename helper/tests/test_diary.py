"""Diary watch: the recorded day leaves when a night's sleep starts."""
import json

import pytest

from domus_helper.contract import ContractError, validate_observation
from domus_helper.diary import CHECK_EVERY_MS, DAY_LIMIT, KV_LAST, KV_PENDING, DiaryWatch, asleep, day_digest


def _row(name, membership="RUNNING"):
    return {
        "event_kind": "presence_snapshot",
        "interactions": {"observed": [{
            "membership": membership,
            "affordance_text": name,
        }]},
    }


def _act(name, start, **extra):
    record = {
        "act_id": "act-%s-%d" % (name, start),
        "interaction": {"name": name},
        "origin": extra.get("origin", "owner"),
        "span": {
            "start": "c%d" % start,
            "end": "c%d" % (start + extra.get("minutes", 10)),
            "start_minute": start,
            "game_minutes": extra.get("minutes", 10),
        },
        "company": extra.get("company") or [],
        "needs": {"delta": extra.get("delta") or {}},
        "moodlets": {"gained": extra.get("gained") or []},
        "reactions": extra.get("reactions") or [],
        "relationships": extra.get("relationships"),
    }
    return record


def test_asleep_is_a_running_night_sleep():
    assert asleep(_row("bed_sleep")) is True
    assert asleep(_row("bed_sleep", "QUEUED")) is False
    assert asleep(_row("nap_rest")) is False
    assert asleep({}) is False


def test_day_digest_keeps_first_moodlets_and_reactions_and_fits():
    records = [
        _act("cook", 10, delta={"hunger": 3, "fun": 6}),
        _act("cook", 20),
        _act("chat", 30, gained=[{"name": "bright"}]),
        _act("chat", 40, reactions=[{"reaction": "wave"}, {"reaction": "wave"}]),
        _act("visit", 50, relationships=[{"with": "Rin", "role": "target", "tracks": {"friend": 2}}]),
        _act("visit", 60, relationships=[{"with": "Rin", "role": "bystander", "tracks": {"friend": 1}}]),
    ]
    digest = day_digest(records, None, 100)
    kept = [item["what"] for item in digest["acts"]]
    assert kept == ["cook", "chat", "chat", "visit"]
    assert digest["also"] == {"cook": 1, "visit": 1}
    cook = digest["acts"][0]
    assert cook["needs"] == {"fun": 6}
    assert "hunger" not in cook["needs"]
    assert digest["acts"][1]["moodlets"] == ["bright"]
    assert digest["acts"][2]["reactions"] == ["wave"]
    assert digest["acts"][3]["people"] == [{"who": "Rin", "role": "target", "tracks": {"friend": 2}}]
    assert digest["frames"] and digest["omitted"] == 0
    many = [_act("job%d" % i, i, origin="body") for i in range(500)]
    packed = day_digest(many, None, 500)
    raw = json.dumps(packed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(raw) <= DAY_LIMIT
    assert packed["omitted"] > 0
    assert sum(packed["also"].values()) == packed["omitted"]


class _Kv:
    def __init__(self):
        self.store = {}

    def get_kv(self, key):
        return self.store.get(key)

    def put_kv(self, key, value):
        self.store[key] = value


def _sleep_records():
    return [
        _act("cook", 100, minutes=15),
        _act("bed_sleep", 400, minutes=40, origin="body"),
    ]


def test_watch_writes_pending_once_per_onset():
    spool = _Kv()
    calls = {"n": 0}

    def read_records(session):
        calls["n"] += 1
        assert session == "sess"
        return _sleep_records()

    watch = DiaryWatch(spool, None, read_records)
    row = _row("bed_sleep")
    row["telemetry_session_id"] = "sess"
    pending = watch.tick(1_000, row, "slot1")
    assert pending["onset_minute"] == 400
    assert pending["day"]["to_minute"] == 400
    assert watch.pending()["world"] == "slot1"
    assert json.loads(spool.store[KV_LAST])["slot1"] == 400
    assert watch.tick(1_000 + CHECK_EVERY_MS - 1, row, "slot1") is None
    assert calls["n"] == 1
    assert watch.tick(1_000 + CHECK_EVERY_MS, row, "slot1") is None
    assert json.loads(spool.store[KV_LAST])["slot1"] == 400
    awake = _row("cook")
    awake["telemetry_session_id"] = "sess"
    before = calls["n"]
    assert watch.tick(1_000 + CHECK_EVERY_MS * 3, awake, "slot1") is None
    assert calls["n"] == before
    watch.clear()
    assert watch.pending() is None


def _observation(**extra):
    body = {
        "v": 1,
        "observation_id": "helper.0",
        "world": "slot1",
        "branch": "guid",
        "session": "sess",
        "attachment": "helper",
        "body": "sim",
        "snapshot": "1",
        "seq": 0,
        "source_time_ms": 5_000,
        "expires_at_ms": 65_000,
        "lineage_class": "HOUSEHOLD",
        "percepts": [{"kind": "sleep_onset", "salience": 1.0, "facts": {"onset_minute": 1}}],
    }
    body.update(extra)
    return body


def test_contract_accepts_a_day_object_within_the_cap():
    now = 5_000
    ok = validate_observation(_observation(day={"v": 1, "acts": []}), now)
    assert ok["day"]["v"] == 1
    with pytest.raises(ContractError):
        validate_observation(_observation(day={"blob": "x" * 20_000}), now)


BUILD = "1.128.90.1030"
WALL = 1_700_000_000_000


def test_bridge_enqueues_one_diary_observation(paths, tmp_path, monkeypatch):
    from domus_helper.bridge import Bridge
    data = tmp_path / "data"
    monkeypatch.setenv("DOMUS_DATA_DIR", str(data))
    monkeypatch.delenv("DOMUS_ASHLEY_URL", raising=False)
    monkeypatch.delenv("DOMUS_ASHLEY_TOKEN", raising=False)

    class Client:
        def post_heartbeat(self, body):
            return type("R", (), {"kind": "admitted", "status": 200})()

        def post_observation(self, body, now_ms=None):
            return type("R", (), {"kind": "admitted", "status": 200})()

    bridge = Bridge(paths, client=Client(), process=(1, "t"), detected_build=BUILD, mono=lambda: WALL)
    row = {
        "event_kind": "presence_snapshot", "written_sequence": 2, "wall_timestamp_ms": WALL,
        "telemetry_session_id": "sess-1", "body": {"sim_id": "ASH"},
        "interactions": {"observed": []}, "motives": [],
    }
    day = {"v": 1, "from_minute": None, "to_minute": 400, "frames": [], "acts": [], "also": {}, "omitted": 0}
    bridge.spool.put_kv("last_row", json.dumps(row))
    bridge.spool.put_kv(KV_PENDING, json.dumps({"world": "slot1", "onset_minute": 400, "day": day}))
    bridge.tick(WALL)
    payloads = [json.loads(item["payload_json"]) for item in bridge.spool._con.execute(
        "SELECT payload_json FROM outbox ORDER BY created_ms, observation_id")]
    assert len(payloads) == 1
    assert payloads[0]["day"] == day
    assert any(item["kind"] == "sleep_onset" for item in payloads[0]["percepts"])
    assert bridge.diary.pending() is None
    assert bridge._enqueued == 1
