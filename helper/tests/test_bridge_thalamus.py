"""DT2C: spool v2, thalamus bridge, decision log, prune, shadow scorer."""
import json
import sqlite3

from domus_helper.contract import validate_observation
from domus_helper.spool import Spool
from domus_helper.thalamus.core import decide, prune
from domus_helper.thalamus.log import DecisionLog
from domus_helper.thalamus.observation import build
from domus_helper.thalamus.parameters import DECISION_LOG_QUOTA_BYTES, Parameters
from domus_helper.thalamus.scorer import NullScorer, load_scorer, run_scorer
from domus_helper.thalamus.types import Context, Decision, KeyState, Percept, ThalamusState


def _v1(path):
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE rows (
            session TEXT NOT NULL, segment INTEGER NOT NULL, offset INTEGER NOT NULL,
            written_sequence INTEGER, event_kind TEXT, wall_ms INTEGER, json TEXT NOT NULL,
            PRIMARY KEY (session, segment, offset)
        );
        CREATE TABLE gaps (
            id INTEGER PRIMARY KEY, session TEXT,
            kind TEXT NOT NULL CHECK (kind IN ('gap', 'cap', 'drop')),
            detail_json TEXT, at_ms INTEGER
        );
        CREATE TABLE cursors (
            session TEXT NOT NULL, segment INTEGER NOT NULL, offset INTEGER NOT NULL,
            PRIMARY KEY (session, segment)
        );
        CREATE TABLE outbox (
            observation_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
            state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_ms INTEGER NOT NULL, last_status TEXT,
            expires_at_ms INTEGER NOT NULL, created_ms INTEGER NOT NULL
        );
    """)
    con.execute("PRAGMA user_version = 1")
    con.execute(
        "INSERT INTO rows (session, segment, offset, written_sequence, event_kind, wall_ms, json) "
        "VALUES ('s', 0, 0, 1, 'speed_event', 1, ?)",
        (json.dumps({"written_sequence": 1, "event_kind": "speed_event"}),))
    con.execute(
        "INSERT INTO outbox (observation_id, payload_json, state, attempts, next_attempt_ms, "
        "expires_at_ms, created_ms) VALUES ('obs-1', '{}', 'pending', 0, 0, 1, 1)")
    con.commit()
    con.close()


def test_spool_v1_upgrades_and_rows_after_respects_order_and_limit(tmp_path):
    path = tmp_path / "spool.db"
    _v1(path)
    spool = Spool(path)
    version = spool._con.execute("PRAGMA user_version").fetchone()[0]
    assert version == 2
    assert spool.row_count() == 1
    assert spool.outbox_counts()["pending"] == 1
    assert spool.get_kv("missing") is None
    spool.put_kv("last_rowid", "1")
    assert spool.get_kv("last_rowid") == "1"
    again = Spool(path)
    assert again.get_kv("last_rowid") == "1"
    spool.ingest("s", 0, 10, {"written_sequence": 2, "n": "b"}, raw_len=1, at_ms=2)
    spool.ingest("s", 0, 20, {"written_sequence": 3, "n": "c"}, raw_len=1, at_ms=3)
    paired = list(spool.rows_after(0, limit=2))
    assert [record["written_sequence"] for _rowid, record in paired] == [1, 2]
    assert paired[0][0] < paired[1][0]
    rest = list(spool.rows_after(paired[1][0]))
    assert [record["written_sequence"] for _rowid, record in rest] == [3]
    assert list(spool.rows_after(rest[-1][0])) == []


def _percept(facts=(("value", "1"), ("band", "low"))):
    return Percept("need", "hunger", "", "low", urgency="wake", lineage="3:abc", facts=facts)


def test_build_clamps_salience_and_fits_caps():
    huge = "x" * 5000
    decision = Decision(True, "threshold", ((_percept((("blob", huge),)), 4.5),), 0.2, 1.0, ())
    row = {
        "written_sequence": 3,
        "wall_timestamp_ms": 5_000,
        "telemetry_session_id": "sess-1",
        "body": {"sim_id": "ASH", "posture": {"posture_name": "stand"}},
        "game": {"clock_speed": "NORMAL", "paused": False},
        "zone": {"zone_id": 7, "lot_id": 9},
        "motives": [{"id": "hunger", "value": 10, "band": "low"}],
        "interactions": {"observed": [
            {"membership": "RUNNING", "affordance_text": "y" * 200} for _ in range(12)
        ]},
    }
    obs = build(decision, {
        "helper_session": "a" * 32, "obs_seq": 0, "slot_id": 3, "guid": "abc",
        "lineage_class": "load", "row": row,
    })
    normalized = validate_observation(obs, 5_000)
    assert normalized["observation_id"] == ("a" * 32) + ".0"
    assert normalized["seq"] == 0
    assert normalized["world"] == "slot3" and normalized["branch"] == "abc"
    assert normalized["lineage_class"] == "PENDING"
    assert normalized["expires_at_ms"] - normalized["source_time_ms"] == 600_000
    assert normalized["percepts"][0]["salience"] == 1.0
    facts = normalized["percepts"][0]["facts"]
    assert facts["reason"] == "threshold" and facts["urgency"] == "wake"
    assert len(json.dumps(facts, separators=(",", ":")).encode()) <= 2048
    assert len(normalized["portrait"]["running"]) <= 8
    assert all(len(item) <= 80 for item in normalized["portrait"]["running"])
    assert len(json.dumps(normalized["portrait"], separators=(",", ":")).encode()) <= 8192


def test_decision_log_shape_and_quota(tmp_path):
    assert DECISION_LOG_QUOTA_BYTES == 50 * 1024 * 1024
    log = DecisionLog(tmp_path, quota=100)
    old = tmp_path / "thalamus"
    old.mkdir()
    (old / "decisions-20200101.jsonl").write_text("a" * 80, encoding="utf-8")
    (old / "decisions-20200102.jsonl").write_text("b" * 80, encoding="utf-8")
    wall = 1_700_000_000_000
    log.write({
        "wall_ms": wall, "mono_ms": 10, "row_seq": 3, "fired": True, "reason": "threshold",
        "theta": 1.0, "arousal": 0.2, "traces": [{
            "key": "need:hunger::low", "raw": 1.1, "h_before": 1.0, "h_after": 0.7,
            "salience": 1.1, "novelty": 0.6,
        }],
        "enqueued": False, "observation_id": None, "scorer": None,
    })
    day = "20231114"
    today = old / ("decisions-%s.jsonl" % day)
    assert today.is_file()
    line = json.loads(today.read_text(encoding="utf-8").splitlines()[0])
    assert set(line) == {
        "wall_ms", "mono_ms", "row_seq", "fired", "reason", "theta", "arousal",
        "traces", "enqueued", "observation_id", "scorer",
    }
    names = sorted(path.name for path in old.glob("decisions-*.jsonl"))
    assert "decisions-20200101.jsonl" not in names
    assert today.name in names


def test_prune_drops_recovered_keys_and_foreign_novelty():
    params = Parameters()
    context = Context()
    key = "need:hunger::low"
    state = ThalamusState(
        last_now_ms=0, idle_since_ms=0,
        keys={key: KeyState(h=1.0, last_ms=0), "fresh": KeyState(h=0.2, last_ms=10_000_000)},
        novelty_counts={("old", key): 4, ("L", key): 2},
    )
    now = 10_000_000
    pruned = prune(state, now, params, "L")
    assert key not in pruned.keys and "fresh" in pruned.keys
    assert pruned.novelty_counts == {("L", key): 2}
    percept = Percept("need", "hunger", "", "low", lineage="L")
    _kept, decided = decide(state, [percept], now, params, context)
    _dropped, after = decide(pruned, [percept], now, params, context)
    assert decided.trace[0].h_before == after.trace[0].h_before == 1.0
    assert decided.fired == after.fired
    assert decided.arousal == after.arousal
    assert decided.reason == after.reason


def test_scorer_null_by_default_and_timeout(monkeypatch):
    monkeypatch.delenv("DOMUS_SHADOW_SCORER", raising=False)
    scorer, note = load_scorer()
    assert isinstance(scorer, NullScorer) and note is None
    assert scorer.score({"v": 1}) is None
    monkeypatch.setenv("DOMUS_SHADOW_SCORER", "not_a_real_scorer")
    unknown, note = load_scorer()
    assert isinstance(unknown, NullScorer) and "not_a_real_scorer" in note

    class Slow:
        def score(self, observation):
            import time
            time.sleep(0.2)
            return {"ok": True}

    assert run_scorer(Slow(), {"v": 1}, timeout_s=0.01)["error"]
    class Boom:
        def score(self, observation):
            raise RuntimeError("boom")
    assert "boom" in run_scorer(Boom(), {"v": 1})["error"]


BUILD = "1.128.90.1030"
WALL = 1_700_000_000_000
SESSION = "ashley_e1_01234567-89ab-cdef-0123-456789abcdef.jsonl"


def _data(paths, tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("DOMUS_DATA_DIR", str(data))
    monkeypatch.delenv("DOMUS_ASHLEY_URL", raising=False)
    monkeypatch.delenv("DOMUS_ASHLEY_TOKEN", raising=False)
    monkeypatch.delenv("DOMUS_SHADOW_SCORER", raising=False)
    return data


def _append(paths, rows):
    path = paths.telemetry / SESSION
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        for row in rows:
            handle.write(json.dumps(row).encode("utf-8") + b"\n")


def _lineage(seq, wall):
    return {
        "event_kind": "lineage_event", "written_sequence": seq, "wall_timestamp_ms": wall,
        "monotonic_ns": wall * 1_000_000, "telemetry_session_id": "sess-1",
        "sims_build": BUILD, "probe_version": "2.5.1",
        "e2": {"slot_id": 3, "guid": "abc", "lineage_class": "HOUSEHOLD"},
    }


def _snap(seq, band, wall, ticks):
    return {
        "event_kind": "presence_snapshot", "written_sequence": seq, "wall_timestamp_ms": wall,
        "monotonic_ns": wall * 1_000_000, "telemetry_session_id": "sess-1",
        "sims_build": BUILD, "probe_version": "2.5.1",
        "game": {"ticks": ticks, "clock_speed": "NORMAL", "paused": False},
        "body": {"sim_id": "ASH", "posture": {"posture_name": "stand", "target_id": "chair"}},
        "interactions": {"observed": [{
            "entry_key": "i1", "interaction_id": "i1", "affordance_id": 1,
            "affordance_text": "sit here", "membership": "RUNNING", "source_raw": "x",
        }]},
        "motives": [{"id": "hunger", "value": 40, "band": band, "age_ticks": 0}],
        "zone": {"zone_id": 7, "lot_id": 9},
    }


class _Client:
    def post_heartbeat(self, body):
        return type("R", (), {"kind": "admitted", "status": 200})()

    def post_observation(self, body, now_ms=None):
        return type("R", (), {"kind": "admitted", "status": 200})()


class _Mark:
    def score(self, observation):
        return {"mark": observation["seq"]}


class _Boom:
    def score(self, observation):
        raise RuntimeError("boom")


def _bridge(paths, mono_at, **kw):
    from domus_helper.bridge import Bridge
    kwargs = dict(
        client=kw.get("client", _Client()), process=(1, "t"),
        detected_build=kw.get("detected_build", BUILD), mono=lambda: mono_at["ms"])
    if "scorer" in kw:
        kwargs["scorer"] = kw["scorer"]
    return Bridge(paths, **kwargs)


def _payloads(bridge):
    rows = bridge.spool._con.execute(
        "SELECT payload_json FROM outbox ORDER BY created_ms, observation_id").fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def _log_lines(data):
    day = "20231114"
    path = data / "thalamus" / ("decisions-%s.jsonl" % day)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_need_window_enqueues_one_then_seq_increases(paths, tmp_path, monkeypatch):
    from domus_helper.contract import validate_observation as check
    data = _data(paths, tmp_path, monkeypatch)
    _append(paths, [
        _lineage(1, WALL),
        _snap(2, "ok", WALL, 10),
        _snap(3, "low", WALL, 20),
    ])
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    bridge.tick(WALL)
    assert _payloads(bridge) == []
    mono["ms"] = WALL + 1500
    bridge.tick(WALL + 1500)
    payloads = _payloads(bridge)
    assert len(payloads) == 1
    obs = check(payloads[0], WALL + 1500)
    need = next(item for item in obs["percepts"] if item["kind"] == "need")
    assert obs["seq"] == 0 and obs["observation_id"].endswith(".0")
    assert obs["world"] == "slot3" and obs["snapshot"] == "3"
    assert obs["portrait"]["needs"]["hunger"]["band"] == "low"
    assert need["facts"]["bucket"] == "low" and need["facts"]["reason"] == "threshold"
    _append(paths, [_snap(4, "distress", WALL + 4000, 30)])
    mono["ms"] = WALL + 4000
    bridge.tick(WALL + 4000)
    payloads = _payloads(bridge)
    assert [item["seq"] for item in payloads] == [0, 1]
    assert payloads[1]["observation_id"].endswith(".1")
    fired = [line for line in _log_lines(data) if line["fired"]]
    assert fired[0]["enqueued"] is True and fired[0]["reason"] == "threshold"
    traced = [line for line in _log_lines(data) if line["traces"]]
    assert traced and "key" in traced[0]["traces"][0]
    status = bridge.status()
    assert status["thalamus"]["enqueued"] == 2
    assert status["thalamus"]["fires"] >= 2
    blob = json.dumps(status)
    assert "super-secret-token-value" not in blob


def test_telemetry_only_logs_fire_without_enqueue(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    _append(paths, [
        _lineage(1, WALL), _snap(2, "ok", WALL, 10), _snap(3, "low", WALL, 20),
    ])
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono, detected_build="other-build")
    bridge.tick(WALL)
    mono["ms"] = WALL + 1500
    bridge.tick(WALL + 1500)
    assert _payloads(bridge) == []
    fired = [line for line in _log_lines(data) if line["fired"]]
    assert fired and fired[0]["enqueued"] is False and fired[0]["observation_id"] is None


def test_restart_resumes_rowid_seq_and_does_not_duplicate(paths, tmp_path, monkeypatch):
    from domus_helper.bridge import Bridge
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [
        _lineage(1, WALL), _snap(2, "ok", WALL, 10), _snap(3, "low", WALL, 20),
    ])
    mono = {"ms": WALL}
    first = _bridge(paths, mono)
    first.tick(WALL)
    assert _payloads(first) == []
    mono["ms"] = WALL + 1500
    first.tick(WALL + 1500)
    assert len(_payloads(first)) == 1
    assert first.spool.get_kv("obs_seq") == "1"
    second = Bridge(
        paths, client=_Client(), process=(1, "t"), detected_build=BUILD,
        mono=lambda: mono["ms"])
    second.tick(WALL + 1500)
    assert len(_payloads(second)) == 1
    assert second.spool.get_kv("obs_seq") == "1"
    assert second.status()["thalamus"]["last_fire_reason"] == "threshold"


def test_scorer_result_and_error_land_in_the_log(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    _append(paths, [
        _lineage(1, WALL), _snap(2, "ok", WALL, 10), _snap(3, "low", WALL, 20),
    ])
    mono = {"ms": WALL + 1500}
    marked = _bridge(paths, mono, scorer=_Mark())
    marked.tick(WALL + 1500)
    fired = [line for line in _log_lines(data) if line["fired"]]
    assert fired[-1]["scorer"] == {"mark": 0}
    assert len(_payloads(marked)) == 1
    marked.spool.close()
    other = tmp_path / "data-b"
    monkeypatch.setenv("DOMUS_DATA_DIR", str(other))
    session = paths.telemetry / SESSION
    # fresh spool, same telemetry file is already consumed only in the first spool
    boom = _bridge(paths, mono, scorer=_Boom())
    # cursor offsets live in the new spool, so the file is read again
    boom.tick(WALL + 1500)
    assert len(_payloads(boom)) == 1
    fired = [line for line in _log_lines(other) if line["fired"]]
    assert "boom" in fired[-1]["scorer"]["error"]
    assert fired[-1]["enqueued"] is True


def test_status_thalamus_block_without_secrets(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "super-secret-token-value-0123456789")
    monkeypatch.setenv("DOMUS_ASHLEY_URL", "http://127.0.0.1:9")
    from domus_helper.bridge import Bridge
    bridge = Bridge(paths, process=(None, None), detected_build=BUILD, client=None)
    block = bridge.status()["thalamus"]
    assert set(block) == {
        "fires", "last_fire_reason", "last_fire_wall_ms", "pending", "theta", "keys",
        "enqueued", "scorer",
    }
    assert block["scorer"] == "NullScorer"
    blob = json.dumps(bridge.status())
    assert "super-secret-token-value" not in blob and "127.0.0.1" not in blob


def test_ds3_portrait_has_time_room_company_moodlets():
    """DS3: she could not know the game time, the room, or who else is here."""
    from domus_helper.thalamus import observation
    assert observation.game_time("13:10:04.200 day:3 week:0") == {
        "hour": 13, "minute": 10, "weekday": "Wednesday", "day_index": 3, "week": 0}
    assert observation.game_time("garbage") is None
    assert observation.game_time("25:00:00.000 day:1 week:0") is None
    row = {
        "game": {"calendar": "07:05:00.000 day:0 week:2", "clock_speed": "NORMAL",
                 "paused": False},
        "zone": {"zone_id": "1", "lot_id": "2", "room": "3", "position": None},
        "presence": [{"id": "100", "is_body": True, "name": "E1 Proband"},
                     {"id": "200", "is_body": False, "name": "Bella Goth", "room": "3",
                      "distance_m": 1.0, "doing": "<class 'social_Chat'>"}],
        "sim_signals": [
            {"kind": "MOODLET", "tuning_id": "902", "tuning_name": "Buff_Hungry",
             "text_key": "3291712568", "magnitude": "w:2", "mood_type": "Mood_Uncomfortable",
             "visible": True},
            {"kind": "MOODLET", "tuning_id": "901", "tuning_name": "Buff_Hidden",
             "text_key": None, "magnitude": "w:0", "mood_type": None, "visible": False}],
        "social": [{"actor_id": "200", "affordance_text": "<class 'social_Chat'>"}],
        "mood": {"type": "1", "intensity": 1, "name": "Mood_Uncomfortable"},
    }
    portrait = observation._portrait(row, {"3291712568": "Hungry"}.get)
    assert portrait["moodlets"][0]["text"] == "Hungry"
    assert observation._portrait(row)["moodlets"][0]["text"] is None
    assert portrait["time"]["weekday"] == "Sunday" and portrait["time"]["hour"] == 7
    assert portrait["zone"]["room"] == "3"
    assert [item["name"] for item in portrait["company"]] == ["Bella Goth"]
    assert [item["name"] for item in portrait["moodlets"]] == ["Buff_Hungry"]
    assert portrait["addressed_by"] == [{"by": "200", "interaction": "<class 'social_Chat'>"}]
    assert portrait["mood"] == "Mood_Uncomfortable"
