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
    assert "reason" not in facts and "urgency" not in facts and "ticks" not in facts  # HE11: trace only
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
        "wall_ms": wall, "clock_ms": 10, "row_seq": 3, "fired": True, "reason": "threshold",
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
        "wall_ms", "clock_ms", "row_seq", "fired", "reason", "theta", "arousal",
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
    assert need["facts"]["bucket"] == "low" and "reason" not in need["facts"]
    _append(paths, [_snap(4, "distress", WALL + 4000, 30)])
    mono["ms"] = WALL + 4000
    bridge.tick(WALL + 4000)
    payloads = _payloads(bridge)
    assert [item["seq"] for item in payloads] == [0, 1]
    assert payloads[1]["observation_id"].endswith(".1")
    fired = [line for line in _log_lines(data) if line["fired"]]
    assert fired[0]["enqueued"] is True and fired[0]["reason"] == "wake"
    assert fired[0]["urgency"] and "ticks" in fired[0]  # HE11: the wake mechanics are in the trace
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
    assert second.status()["thalamus"]["last_fire_reason"] == "wake"


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


def test_act_menu_then_fire_puts_notebook_on_portrait(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)

    def menu(room, seq, wall):
        return {
            "event_kind": "act_menu", "written_sequence": seq, "wall_timestamp_ms": wall,
            "telemetry_session_id": "sess-1",
            "e2": {"menu_rev": 1, "room": room, "objects": [{
                "object_id": "501", "class": "object_fridge_X", "same_room": True, "acts": []}]},
        }

    _append(paths, [
        _lineage(1, WALL),
        menu("7", 2, WALL),
        menu("9", 3, WALL + 1),
        _snap(4, "ok", WALL + 2, 10),
        _snap(5, "low", WALL + 3, 20),
    ])
    mono = {"ms": WALL + 3}
    bridge = _bridge(paths, mono)
    bridge.tick(WALL + 3)
    mono["ms"] = WALL + 1500
    bridge.tick(WALL + 1500)
    moved = _payloads(bridge)[-1]["portrait"]["notebook"]["moved"]
    assert moved[0]["was_in"] == "7" and moved[0]["now_in"] == "9"


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
    assert portrait["addressed_by"] == [{"by": "200", "interaction": "social_Chat"}]
    assert portrait["mood"] == "Mood_Uncomfortable"


def test_thalamus_keeps_firing_after_a_reboot_or_game_relaunch(paths, tmp_path, monkeypatch):
    """D50: the thalamus runs on the wall clock. Live 2026-10-05 it ran on the game's monotonic
    clock (restarts every launch) and the bridge's uptime (restarts every boot) and froze."""
    from domus_helper.bridge import Bridge
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_lineage(1, WALL)])
    uptime = {"ms": 10 ** 10}
    first = _bridge(paths, uptime)
    first.tick(WALL)
    first.spool.close()
    restarted = {"ms": 1000}
    second = Bridge(paths, client=_Client(), process=(1, "t"), detected_build=BUILD,
                    mono=lambda: restarted["ms"])

    def relaunched(row):
        row["monotonic_ns"] = 5_000_000
        return row

    _append(paths, [relaunched(_snap(2, "ok", WALL + 60_000, 10))])
    second.tick(WALL + 60_000)
    assert len(_payloads(second)) == 1
    _append(paths, [relaunched(_snap(3, "low", WALL + 100_000, 20))])
    second.tick(WALL + 100_000)
    restarted["ms"] += 1500
    second.tick(WALL + 101_500)
    payloads = _payloads(second)
    assert len(payloads) == 2
    assert payloads[1]["portrait"]["needs"]["hunger"]["band"] == "low"


def test_her_options_ride_on_each_observation_from_the_newest_menu_of_this_session(paths, tmp_path, monkeypatch):
    """8f: the probe's act_menu becomes the observation's options; a menu of another session never does."""
    from domus_helper.contract import validate_observation as check
    _data(paths, tmp_path, monkeypatch)
    menu = {"menu_rev": 1, "room": "4", "tested": 1, "refused": 0, "build_ms": 1.0, "objects": [
        {"object_id": "11", "definition_id": None, "class": "object_bookshelf", "distance_m": 2.0, "same_room": True,
         "acts": [{"guid64": "4242", "name": "bookshelf_ReadBook", "text_key": None}]}]}
    stale = dict(menu, objects=[dict(menu["objects"][0], object_id="99")])
    _append(paths, [
        _lineage(1, WALL),
        {"event_kind": "act_menu", "written_sequence": 2, "wall_timestamp_ms": WALL, "monotonic_ns": WALL * 1_000_000,
         "telemetry_session_id": "old-session", "sims_build": BUILD, "probe_version": "2.16.0", "e2": stale},
        {"event_kind": "act_menu", "written_sequence": 3, "wall_timestamp_ms": WALL, "monotonic_ns": WALL * 1_000_000,
         "telemetry_session_id": "sess-1", "sims_build": BUILD, "probe_version": "2.16.0", "e2": menu},
        dict(_snap(4, "ok", WALL, 10), zone={"zone_id": 7, "lot_id": 9, "room": "4"}),
        dict(_snap(5, "low", WALL, 20), zone={"zone_id": 7, "lot_id": 9, "room": "4"}),
    ])
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    bridge.tick(WALL)
    mono["ms"] = WALL + 1500
    bridge.tick(WALL + 1500)
    payloads = _payloads(bridge)
    assert len(payloads) == 1
    obs = check(payloads[0], WALL + 1500)
    assert bridge._menu["at_ms"] == WALL  # HE12: the menu keeps its wall time
    assert obs["options"] == [{"object": "object bookshelf", "object_id": "11", "where": "here, 2.0 m",
                               "acts": [{"ref": "a1", "guid64": "4242", "text": "bookshelf Read Book"}]}]
    bridge._menu = dict(bridge._menu, session="another")
    assert bridge._options(bridge._last_row) == []


def _activity(seq, wall, source):
    row = _snap(seq, "ok", wall, seq * 10)
    row["interactions"]["observed"] = [] if source is None else [{
        "entry_key": "a", "interaction_id": "a", "affordance_id": 5, "affordance_text": "play",
        "membership": "RUNNING", "source_raw": source}]
    return row


def test_h05_her_idle_wakes_her_unless_a_plan_step_is_still_to_follow(paths, tmp_path, monkeypatch):
    """H0.5: an act ending into idle is a decision point; mid-plan Ashley sends the next step itself."""
    mine = "InteractionSource.SCRIPT_WITH_USER_INTENT"
    for planned, expected in ((0, 1), (2, 0)):
        _data(paths, tmp_path / str(planned), monkeypatch)
        (paths.telemetry / SESSION).unlink(missing_ok=True)
        _append(paths, [_lineage(1, WALL), _activity(2, WALL, mine)])
        mono = {"ms": WALL}
        bridge = _bridge(paths, mono)
        bridge.tick(WALL)
        bridge.tick(WALL + 2_000)
        before = len(_payloads(bridge))
        bridge._acts.planned = planned
        _append(paths, [_activity(3, WALL + 60_000, None)])
        bridge.tick(WALL + 60_000)
        bridge.tick(WALL + 62_000)
        woke = [item for item in _payloads(bridge)[before:]
                if any(p["facts"].get("bucket") == "idle" for p in item["percepts"])]
        assert len(woke) == expected, planned


def _act(seq, wall):
    return {
        "event_kind": "act_event", "written_sequence": seq, "wall_timestamp_ms": wall,
        "monotonic_ns": wall * 1_000_000, "telemetry_session_id": "sess-1",
        "sims_build": BUILD, "probe_version": "2.5.1",
        "e2": {"act_id": "act-9", "phase": "FINISHED", "object_id": "11"},
    }


def _body(seq, band, wall, ticks):
    row = _snap(seq, band, wall, ticks)
    row["mood"] = {"name": "Mood_Bright"}
    row["zone"] = {"zone_id": 7, "lot_id": 9, "room": "4"}
    row["body"]["posture"] = {"posture_name": "sit", "target_id": "stool"}
    row["presence"] = [
        {"id": "1", "is_body": True, "name": "Ada Quill"},
        {"id": "2", "is_body": False, "name": "Nia Cole", "room": "4"},
    ]
    return row


def test_portrait_comes_from_the_body_sample_not_the_act_event(paths, tmp_path, monkeypatch):
    """Answering a dialog writes an act row. Her portrait stays the latest sample."""
    _data(paths, tmp_path, monkeypatch)
    acted = WALL + 400
    _append(paths, [
        _lineage(1, WALL),
        _body(2, "ok", WALL, 10),
        _body(3, "low", WALL, 20),
        _act(4, acted),
    ])
    mono = {"ms": acted}
    bridge = _bridge(paths, mono)
    bridge.tick(acted)
    assert _payloads(bridge) == []
    bridge.tick(acted + 1_500)
    obs = _payloads(bridge)[-1]
    portrait = obs["portrait"]
    assert portrait["needs"]["hunger"] == {"value": 40, "band": "low"}
    assert portrait["mood"] == "Mood_Bright"
    assert portrait["posture"] == "sit"
    assert portrait["zone"] == {"zone_id": 7, "lot_id": 9, "room": "4"}
    assert [item["name"] for item in portrait["company"]] == ["Nia Cole"]
    assert obs["source_time_ms"] == acted
    assert obs["snapshot"] == "4"
    assert obs["body"] == "ASH"


def test_a_session_checkpoint_never_replaces_her_body_sample(paths, tmp_path, monkeypatch):
    """Live 2026-10-08: a checkpoint row (empty body skeleton) became her portrait and her running
    act vanished from it. Her portrait stays the latest presence snapshot."""
    _data(paths, tmp_path, monkeypatch)
    acted = WALL + 400
    checkpoint = _act(4, acted - 100)
    checkpoint.update({"event_kind": "session_checkpoint", "checkpoint_reason": "interval", "e2": None,
                       "motives": [], "zone": {"zone_id": None, "lot_id": None, "room": None},
                       "body": {"sim_id": None, "posture": None},
                       "interactions": {"observed": []}, "presence": []})
    _append(paths, [
        _lineage(1, WALL),
        _body(2, "ok", WALL, 10),
        _body(3, "low", WALL, 20),
        checkpoint,
        _act(5, acted),
    ])
    mono = {"ms": acted}
    bridge = _bridge(paths, mono)
    bridge.tick(acted)
    bridge.tick(acted + 1_500)
    portrait = _payloads(bridge)[-1]["portrait"]
    assert portrait["posture"] == "sit"
    assert portrait["zone"] == {"zone_id": 7, "lot_id": 9, "room": "4"}
    assert portrait["needs"]["hunger"] == {"value": 40, "band": "low"}
    assert bridge._last_body_row["written_sequence"] == 3


def test_only_event_rows_still_build_a_portrait(paths, tmp_path, monkeypatch):
    """No sample yet: the portrait is the event row's, and nothing raises."""
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_lineage(1, WALL), _act(2, WALL + 10)])
    mono = {"ms": WALL + 10}
    bridge = _bridge(paths, mono)
    bridge.tick(WALL + 10)
    bridge.tick(WALL + 10 + 1_500)
    obs = _payloads(bridge)[-1]
    portrait = obs["portrait"]
    assert portrait["needs"] == {}
    assert portrait["mood"] is None
    assert portrait["posture"] is None
    assert portrait["company"] == []
    assert portrait["zone"]["lot_id"] is None
    assert bridge._last_body_row is None


def test_last_body_row_survives_a_restart(paths, tmp_path, monkeypatch):
    """Old spools have no last_body_row. Once saved, a new bridge loads it."""
    from domus_helper.bridge import Bridge
    _data(paths, tmp_path, monkeypatch)
    fresh = _bridge(paths, {"ms": WALL})
    fresh.spool.put_kv("last_row", json.dumps(_act(1, WALL)))
    fresh.thalamus_status()
    assert fresh.spool.get_kv("last_body_row") is None
    assert fresh._last_body_row is None
    sample = _body(2, "low", WALL, 10)
    _append(paths, [_lineage(1, WALL), sample])
    fresh.tick(WALL)
    saved = json.loads(fresh.spool.get_kv("last_body_row"))
    assert saved["mood"]["name"] == "Mood_Bright"
    assert saved["motives"][0]["band"] == "low"
    second = Bridge(
        paths, client=_Client(), process=(1, "t"), detected_build=BUILD, mono=lambda: WALL)
    second.thalamus_status()
    assert second._last_body_row == saved


def test_a_crash_leaves_its_traceback_in_the_data_folder(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pytest
    from domus_helper import bridge as bridge_module

    monkeypatch.setattr(bridge_module.Paths, "from_env", staticmethod(lambda: SimpleNamespace(data_dir=tmp_path)))

    def boom(argv=None):
        raise RuntimeError("invented failure")

    monkeypatch.setattr(bridge_module, "main", boom)
    with pytest.raises(RuntimeError):
        bridge_module._crash_logged([])
    text = (tmp_path / "bridge_crash.log").read_text(encoding="utf-8")
    assert "invented failure" in text and "Traceback" in text
