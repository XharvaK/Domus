"""Crawl planner, unattended driver, and trials ledger. No game process."""
import json
import sqlite3

import pytest

from domus_helper import atlas, crawl, mcp_server
from domus_helper.commands import Reply
from domus_helper.mcp_server import SafetyError
from domus_helper.paths import Paths


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "domus-data"))


def _affordance(guid, name="sit", **extra):
    row = {
        "kind": "affordance", "guid64": guid, "name": name, "is_super": True,
        "is_social": False, "target_type": "OBJECT", "allow_autonomous": False,
        "allow_user_directed": True, "require_current_posture": False,
        "posture_preferences": None, "static_commodities": [],
    }
    row.update(extra)
    return row


def _import(db, build, rows):
    lines = [{
        "kind": "atlas_header", "probe_version": "2.8.0", "sims_build": build,
        "total": len(rows), "started_ms": 1,
    }]
    lines.extend(rows)
    lines.append({
        "kind": "atlas_footer", "count": len(rows), "errors": 0,
        "chunks": 1, "max_chunk_ms": 1, "p50_chunk_ms": 1,
    })
    path = db.parent / "tuning.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    atlas.import_tuning(db, path)


def _tuned(object_id, guids):
    return {"kind": "tuned_on_class", "object_id": str(object_id),
            "affordance_guid64s": list(guids)}


class Clock:
    def __init__(self):
        self.t = 0.0
        self.slept = []

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


from domus_helper.mcp_server import CommandFailed


class FakeTools:
    def __init__(self, tmp_path):
        self.paths = Paths(tmp_path / "sims", tmp_path / "game")
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.status = {
            "state": "SAMPLING", "armed_name": "LAB_E1_FORK", "calibrate": False,
            "lineage_class": "A", "designated_sim_id": "9",
        }
        self.replies = []
        self.sent = []
        self.rows = []
        self._raise = None

    def checked_status(self):
        if self._raise and self._raise[0] == "status":
            raise self._raise[1]
        return Reply("s", "OK", None, dict(self.status), "agent:test")

    def command(self, name, args=None):
        self.sent.append((name, args))
        if name in ("tuned_scan", "preflight"):
            return Reply("c", "OK", None, {"ok": True, "lines": []}, "agent:test")
        if self._raise and self._raise[0] == "command":
            raise self._raise[1]
        line = self.replies.pop(0)
        if line.startswith("TRIAL_REJECT") or line.startswith("PUSH_FAILED"):
            # Like the live probe: a refused or failed trial is inbox status REJECTED.
            raise CommandFailed(Reply("c", "REJECTED", None, {"ok": False, "lines": [line]},
                                      "agent:test"))
        return Reply("c", "OK", None, {"ok": True, "lines": [line]}, "agent:test")


def _drive(tools, db, tuned, clock, **kwargs):
    try:
        return crawl.drive(
            client=tools, build="1.1", tuned_rows=tuned, atlas_db=db,
            per_hour=kwargs.pop("per_hour", 60), max_trials=kwargs.pop("max_trials", 20),
            verdict_timeout_s=kwargs.pop("verdict_timeout_s", 10),
            sleep=clock.sleep, monotonic=clock.monotonic,
            telemetry_rows=lambda: list(tools.rows), session="sess", **kwargs)
    except crawl.CrawlStop as error:
        print(error)
        return 2


def _verdict(experiment_id, code="PASS", guid=1, name="sit"):
    return {"event_kind": "experiment_event", "written_sequence": 4,
            "e2": {"phase": "VERDICT", "code": code, "experiment_id": experiment_id,
                   "object_id": "1", "guid64": guid, "tuning_name": name,
                   "ambiguous": ["foreign"] if code == "OUTCOME_UNKNOWN" else []}}


def test_plan_filters_orders_and_one_object(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [
        _affordance(1, "sit"),
        _affordance(2, "watch", is_super=False),
        _affordance(3, "use", allow_user_directed=False),
        _affordance(4, "chat", is_social=True),
        _affordance(5, "sim_delete_object"),
        _affordance(6, "ObjectPicker"),
        _affordance(7, "read"),
        _affordance(8, "nap"),
        _affordance(9, "cook"),
    ])
    atlas.record_trial(db, "1.1", "e-pass", 8, "1", "PASS", "PASS", None, "nap", "sess")
    atlas.record_trial(db, "1.1", "e-pass2", 8, "1", "PASS", "PASS", None, "nap", "sess")
    atlas.record_trial(db, "1.1", "e-pass3", 8, "1", "PASS", "PASS", None, "nap", "sess")
    atlas.record_trial(db, "1.1", "e-bad", 9, "1", "PUSH_FAILED", None, None, "cook", "sess")
    atlas.record_trial(db, "1.1", "e-bad2", 9, "1", "PUSH_FAILED", None, None, "cook", "sess")
    atlas.record_trial(db, "1.1", "e-mid", 7, "1", "PASS", "PASS", None, "read", "sess")
    tuned = [
        _tuned(20, [1]), _tuned(3, [1]), _tuned(9, [2, 3, 4, 5, 6]),
        _tuned(4, [7]), _tuned(5, [8]), _tuned(6, [9]),
        {"kind": "tuned_header"}, {"kind": "tuned_error", "object_id": "1"},
    ]
    planned = crawl.plan("1.1", tuned, db, limit=20)
    assert [(item["guid64"], item["object_id"]) for item in planned] == [
        (1, "3"), (7, "4")]
    skipped = crawl.plan("1.1", tuned, db, limit=20, skip=("SIT",))
    assert [item["guid64"] for item in skipped] == [7]


def test_qualification_states(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1), _affordance(2, "watch"), _affordance(3, "read")])
    for index in range(3):
        atlas.record_trial(db, "1.1", "p%d" % index, 1, "1", "PASS", "PASS", None, "sit", "s")
    for index in range(3):
        atlas.record_trial(db, "1.1", "u%d" % index, 2, "1", "OUTCOME_UNKNOWN",
                           "OUTCOME_UNKNOWN", "[\"foreign\"]", "watch", "s",
                           probe_version="2.10.0")
    atlas.record_trial(db, "1.1", "r1", 3, "1", "TRIAL_REJECT", "TRIAL_EXCLUDED", None, "read", "s")
    states = {row["guid64"]: row for row in atlas.qualification(db, "1.1")}
    assert states[1]["state"] == "QUALIFIED" and states[1]["pass_n"] == 3
    assert states[1]["unknown_n"] == 0
    assert states[2]["state"] == "FAILED" and states[2]["unknown_n"] == 3
    assert states[3]["state"] == "FAILED" and states[3]["reject_n"] == 1
    assert atlas.qualification(db, "9.9") == []


def test_migration_keeps_rows(tmp_path):
    db = tmp_path / "atlas.db"
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE affordances (
            build TEXT NOT NULL, guid64 INTEGER NOT NULL, name TEXT,
            is_super INTEGER, is_social INTEGER, target_type TEXT,
            allow_autonomous INTEGER, allow_user_directed INTEGER,
            require_current_posture INTEGER, posture_preferences TEXT,
            static_commodities_json TEXT,
            ladder TEXT NOT NULL DEFAULT 'KNOWN',
            PRIMARY KEY (build, guid64));
        CREATE TABLE imports (file_sha256 TEXT PRIMARY KEY, build TEXT);
        CREATE TABLE cards (
            build TEXT NOT NULL, card_id TEXT NOT NULL, card_class TEXT NOT NULL,
            affordance_guid64 INTEGER, object_id TEXT, body_json TEXT NOT NULL,
            origin TEXT NOT NULL, created_ms INTEGER NOT NULL,
            PRIMARY KEY (build, card_id));
        INSERT INTO affordances (build, guid64, name, is_super, is_social,
            allow_user_directed) VALUES ('1.1', 10, 'sit', 1, 0, 1);
        INSERT INTO imports VALUES ('abc', '1.1');
        INSERT INTO cards VALUES ('1.1', 'c', 'posture', 10, '1', '{}', 'learned', 1);
        PRAGMA user_version = 2;
        """)
    connection.commit()
    connection.close()
    atlas.record_trial(db, "1.1", "sess:1", 10, "1", "TIMEOUT", "TIMEOUT", None, None, "sess")
    connection = sqlite3.connect(db)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
    assert connection.execute("SELECT name FROM affordances").fetchone()[0] == "sit"
    assert connection.execute("SELECT build FROM imports").fetchone()[0] == "1.1"
    assert connection.execute("SELECT card_id FROM cards").fetchone()[0] == "c"
    assert connection.execute("SELECT outcome FROM trials").fetchone()[0] == "TIMEOUT"
    connection.close()


def test_driver_pass_timeout_and_busy_retry(tmp_path, capsys):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_REJECT BODY_BUSY", "TRIAL_PUSHED exp1 interaction 5",
                     "TRIAL_PUSHED exp2 interaction 6"]
    clock = Clock()

    def rows():
        found = list(tools.rows)
        if any(item[1].get("guid64") == "1" for item in tools.sent) and len(tools.sent) >= 2:
            if not any(row["e2"].get("experiment_id") == "exp1" for row in found):
                tools.rows.append(_verdict("exp1"))
        return list(tools.rows)

    try:
        crawl.drive(
            client=tools, build="1.1", tuned_rows=[_tuned(4, [1])], atlas_db=db,
            per_hour=60, max_trials=2, verdict_timeout_s=10,
            sleep=clock.sleep, monotonic=clock.monotonic, telemetry_rows=rows, session="sess")
    except crawl.CrawlStop:
        pass
    recorded = atlas.trials_for(db, "1.1")
    assert [row["outcome"] for row in recorded] == ["PASS", "TIMEOUT"]
    assert len(tools.sent) == 3
    assert tools.sent[0][0] == "trial"
    assert tools.sent[0][1] == {"object_id": "4", "guid64": "1"}
    assert 15 in clock.slept
    out = capsys.readouterr().out
    assert "trial 1 1 sit 4 -> PASS (PASS)" in out
    assert "trial 2 1 sit 4 -> TIMEOUT (TIMEOUT)" in out
    log = (tools.paths.data_dir / "runs" / "crawl_sess.jsonl").read_text(encoding="utf-8")
    assert log.count('"kind": "send"') == 3
    assert '"outcome": "PASS"' in log
    assert "BODY_BUSY" not in "".join(
        line for line in log.splitlines() if '"kind": "outcome"' in line)


def test_spacing(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit"), _affordance(2, "watch")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_PUSHED exp1 interaction 1", "TRIAL_PUSHED exp2 interaction 2"]
    tools.rows = [_verdict("exp1", guid=1), _verdict("exp2", guid=2, name="watch")]
    clock = Clock()
    stamps = []
    original = tools.command

    def command(name, args=None):
        stamps.append(clock.monotonic())
        return original(name, args)

    tools.command = command
    _drive(tools, db, [_tuned(1, [1]), _tuned(2, [2])], clock, max_trials=2)
    assert stamps[1] - stamps[0] >= 60


def test_stop_rules(tmp_path, capsys):
    tuned = [_tuned(i, [i]) for i in range(1, 13)]

    def run(replies, **kwargs):
        case = tmp_path / ("c%d" % len(list(tmp_path.iterdir())))
        case.mkdir()
        db = case / "atlas.db"
        _import(db, "1.1", [_affordance(i, "sit") for i in range(1, 13)])
        tools = FakeTools(case)
        tools.replies = list(replies)
        if "status" in kwargs:
            tools.status.update(kwargs.pop("status"))
        if "raise_on" in kwargs:
            tools._raise = kwargs.pop("raise_on")
        clock = Clock()
        code = _drive(tools, db, tuned, clock, **kwargs)
        text = capsys.readouterr().out.strip().splitlines()
        return code, text[-1] if text else "", tools, db

    code, line, tools, db = run(["PUSH_FAILED"] * 5, max_trials=20)
    assert code == 2 and "PUSH_FAILED" in line
    assert len(atlas.trials_for(db, "1.1")) == 5

    pattern = (["PUSH_FAILED"] * 4 + ["TRIAL_REJECT NO_OBJECT"]
               + ["PUSH_FAILED"] * 3 + ["TRIAL_REJECT NO_OBJECT"]
               + ["PUSH_FAILED"] * 2)
    code, line, _, _ = run(pattern, max_trials=20)
    assert code == 2 and "8" in line

    code, line, _, _ = run(["TRIAL_REJECT TRIAL_STORM"])
    assert code == 2 and "TRIAL_STORM" in line

    code, line, _, _ = run(["TRIAL_REJECT NEED_DISTRESS", "TRIAL_REJECT NEED_DISTRESS"])
    # D23: the stop names the need when the rows show it; none here.
    assert code == 2 and line == "the lab Sim needs care: a body need is in distress, then restart"

    case = tmp_path / "lineage"
    case.mkdir()
    db = case / "atlas.db"
    _import(db, "1.1", [_affordance(i, "sit") for i in range(1, 13)])
    tools = FakeTools(case)
    tools.replies = ["TRIAL_PUSHED exp interaction 1", "TRIAL_PUSHED exp2 interaction 2"]
    tools.rows = [_verdict("exp")]
    flipped = {"done": False}
    base_status = tools.checked_status

    def checked():
        reply = base_status()
        if tools.sent and not flipped["done"]:
            flipped["done"] = True
            tools.status["designated_sim_id"] = "8"
        return reply

    tools.checked_status = checked
    clock = Clock()
    code = _drive(tools, db, [_tuned(1, [1])], clock, max_trials=5)
    assert code == 2
    assert "designated_sim_id" in capsys.readouterr().out

    code, line, _, _ = run([], raise_on=("command", SafetyError("build mismatch: declared a, detected b")))
    assert code == 2 and "build mismatch" in line

    code, line, _, _ = run(["TRIAL_REJECT NO_OBJECT"] * 3, max_trials=2)
    assert code == 2 and "max-trials" in line


def test_dry_run_sends_nothing(tmp_path, capsys):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    tools = FakeTools(tmp_path)
    clock = Clock()
    code = _drive(tools, db, [_tuned(4, [1])], clock, dry_run=True)
    assert code == 0 and tools.sent == []
    assert "1 sit 4" in capsys.readouterr().out


def test_precondition_waits_once_per_reason(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    tools = FakeTools(tmp_path)
    tools.status["state"] = "IDLE"
    tools.replies = ["TRIAL_PUSHED exp interaction 1"]
    tools.rows = [_verdict("exp")]
    seen = {"n": 0}

    def checked():
        seen["n"] += 1
        if seen["n"] >= 2:
            tools.status["state"] = "SAMPLING"
        return Reply("s", "OK", None, dict(tools.status), "agent:test")

    tools.checked_status = checked
    clock = Clock()
    assert _drive(tools, db, [_tuned(1, [1])], clock, max_trials=1) == 2
    assert clock.slept.count(10) == 1
    log = (tools.paths.data_dir / "runs" / "crawl_sess.jsonl").read_text(encoding="utf-8")
    assert log.count("state") == 1


def test_mcp_tools_without_game(tmp_path, monkeypatch):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    atlas.record_trial(db, "1.1", "e", 1, "4", "PASS", "PASS", None, "sit", "s")
    tuned = tmp_path / "sims" / "AshleyE1Telemetry" / "atlas"
    tuned.mkdir(parents=True)
    (tuned / "tuned_1.1_1.jsonl").write_text(
        json.dumps({"kind": "tuned_header", "sims_build": "1.1"}) + "\n"
        + json.dumps(_tuned(4, [1])) + "\n", encoding="utf-8")
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(tmp_path / "sims"))
    (tmp_path / "data").mkdir()
    # Point the tool atlas at the imported database.
    monkeypatch.setattr(Paths, "atlas_db", property(lambda self: db))
    monkeypatch.setattr(mcp_server, "game_running", lambda: False)
    monkeypatch.setattr(
        mcp_server.fingerprint_reader, "detected_build",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("no build")))
    assert mcp_server.trials()[0]["outcome"] == "PASS"
    assert mcp_server.qualification()[0]["state"] == "IN_PROGRESS"
    plan = mcp_server.crawl_plan(limit=5)
    assert plan[0]["guid64"] == 1
    assert plan[0]["object_id"] == "4"


def test_helper_extra_deny_covers_the_reviewed_families():
    from domus_helper import crawl_protocol as cp
    for name in ("object_Bane_Sabotage_Stove", "Ghost_Possess_Break_Electrocution",
                 "object_Hire_Repair_Service", "door_SetFrontDoor",
                 "utilities_AddUtility_PowerProduction_Large", "sim_DeliverBaby",
                 "sim_CallOver", "infant_WhatsThat", "RabbitHole_Tree_Explore",
                 "object_ReplaceBrokenObject", "Mailbox_DisplayBillsDialog"):
        assert cp.name_blocked(name), name
    for name in ("object_Repair_Sink", "fridge_Grab_Snack", "shower_TakeShower",
                 "mailbox_PayBills", "fishing_ExamineWater"):
        assert not cp.name_blocked(name), name


def test_restart_in_same_session_does_not_reuse_reject_keys(tmp_path, capsys):
    # Live: a second crawl process in the same game session hit
    # "UNIQUE constraint failed: trials.experiment_id" on "<session>:0".
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit"), _affordance(2, "read")])
    tuned = [_tuned(1, [1]), _tuned(2, [2])]
    for _ in range(2):
        tools = FakeTools(tmp_path)
        tools.replies = ["TRIAL_REJECT NO_OBJECT"]
        assert _drive(tools, db, tuned, Clock(), max_trials=1) == 2
    assert "max-trials" in capsys.readouterr().out
    assert len(atlas.trials_for(db, "1.1")) == 2


def test_f7_stale_target_is_not_counted_and_replanned(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "cleanup_Dishes")])
    atlas.record_trial(db, "1.1", "stale", 1, "3", "STALE_TARGET", "NO_OBJECT",
                       None, "cleanup_Dishes", "s", probe_version="2.10.0")
    planned = crawl.plan("1.1", [_tuned(3, [1]), _tuned(20, [1])], db, limit=5)
    assert [(item["guid64"], item["object_id"]) for item in planned] == [(1, "20")]
    states = {row["guid64"]: row for row in atlas.qualification(db, "1.1")}
    assert states[1]["state"] == "UNTESTED"
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_REJECT NO_OBJECT", "TRIAL_REJECT NO_OBJECT",
                     "TRIAL_REJECT NO_OBJECT"]
    _import_rows = [_affordance(index, "dish%d" % index) for index in (11, 12, 13)]
    _import(db, "1.1", _import_rows)
    assert _drive(tools, db, [_tuned(index, [index]) for index in (11, 12, 13)],
                  Clock(), max_trials=3) == 2
    assert [name for name, _args in tools.sent].count("tuned_scan") == 1
    assert [name for name, _args in tools.sent].count("preflight") == 1


def test_f9_never_started_fails_only_after_three_on_two_objects(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "bed_sleep")])
    for index in range(2):
        atlas.record_trial(db, "1.1", "n%d" % index, 1, "9", "NEVER_STARTED",
                           "OUTCOME_UNKNOWN", None, "bed_sleep", "s", probe_version="2.10.0")
    assert atlas.qualification(db, "1.1")[0]["state"] == "IN_PROGRESS"
    atlas.record_trial(db, "1.1", "n2", 1, "8", "NEVER_STARTED", "OUTCOME_UNKNOWN",
                       None, "bed_sleep", "s", probe_version="2.10.0")
    assert atlas.qualification(db, "1.1")[0]["state"] == "FAILED"


def test_f10_old_unknown_rows_do_not_poison_qualification(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "tv_WatchKids")])
    for index in range(6):
        atlas.record_trial(db, "1.1", "old%d" % index, 1, "1", "OUTCOME_UNKNOWN",
                           "OUTCOME_UNKNOWN", None, "tv_WatchKids", "s", probe_version="2.9.3")
    assert atlas.qualification(db, "1.1")[0]["state"] == "UNTESTED"
    assert atlas.qualification(db, "1.1")[0]["unknown_n"] == 0
    kept = atlas.trials_for(db, "1.1")
    assert len(kept) == 6 and kept[0]["probe_version"] == "2.9.3"


def test_f11_reconcile_records_a_verdict_left_by_a_stopped_crawl(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "sit")])
    tools = FakeTools(tmp_path)
    log = tools.paths.data_dir / "runs" / "crawl_sess.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps({
        "kind": "send", "reply": "TRIAL_PUSHED", "experiment_id": "exp9",
        "guid64": 1, "object_id": "4", "name": "sit",
    }) + "\n", encoding="utf-8")
    tools.rows = [_verdict("exp9")]
    tools.replies = ["TRIAL_PUSHED exp1 interaction 1"]
    tools.rows.append(_verdict("exp1"))
    assert _drive(tools, db, [_tuned(4, [1])], Clock(), max_trials=1) == 2
    recorded = {row["experiment_id"]: row["outcome"] for row in atlas.trials_for(db, "1.1")}
    assert recorded["exp9"] == "PASS"


def test_f12_spacing_follows_a_push_not_a_refusal(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "upgrade"), _affordance(2, "sit")])
    tools = FakeTools(tmp_path)
    tools.replies = ["PUSH_REFUSED skill level not in desired range",
                     "TRIAL_PUSHED exp interaction 1"]
    tools.rows = [_verdict("exp", guid=2, name="sit")]
    clock = Clock()
    stamps = []
    original = tools.command

    def command(name, args=None):
        stamps.append(clock.monotonic())
        return original(name, args)

    tools.command = command
    _drive(tools, db, [_tuned(1, [1]), _tuned(2, [2])], clock, max_trials=2)
    assert stamps[1] - stamps[0] == 2
    assert 60 not in clock.slept[:1]


def test_f13_preflight_and_default_name_skips(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [
        _affordance(1, "bed_Nap"),
        _affordance(2, "bed_Nap_Resume"),
        _affordance(3, "upgrade_CompletedDisplay"),
        _affordance(4, "sit"),
    ])
    atlas.record_trial(db, "1.1", "one", 4, "1", "PASS", "PASS", None, "sit", "s",
                       probe_version="2.10.0")
    tuned = [_tuned(5, [1, 2, 3, 4])]
    preflight = [
        {"kind": "preflight", "object_id": "5", "guid64": 1, "name": "bed_Nap", "ok": True, "reason": None},
        {"kind": "preflight", "object_id": "5", "guid64": 4, "name": "sit", "ok": False, "reason": "no"},
    ]
    planned = crawl.plan("1.1", tuned, db, limit=10, preflight_rows=preflight)
    assert [item["guid64"] for item in planned] == [1]
    unfiltered = crawl.plan("1.1", tuned, db, limit=10)
    assert [item["guid64"] for item in unfiltered] == [1, 4]


def test_f14_outcome_log_records_needs(tmp_path):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "bed_Nap")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_PUSHED exp interaction 1"]
    tools.rows = [
        {"event_kind": "experiment_event", "written_sequence": 5,
         "e2": {"phase": "PUSHED", "experiment_id": "exp"}},
        {"event_kind": "presence_snapshot", "written_sequence": 4,
         "motives": [{"id": "energy", "value": 98, "band": "ok", "age_ticks": 1}]},
        {"event_kind": "presence_snapshot", "written_sequence": 12,
         "motives": [{"id": "energy", "value": 40, "band": "ok", "age_ticks": 1}]},
        {"event_kind": "experiment_event", "written_sequence": 11,
         "e2": {"phase": "VERDICT", "code": "PASS", "experiment_id": "exp",
                "guid64": "1", "tuning_name": "bed_Nap", "ambiguous": []}},
    ]
    assert _drive(tools, db, [_tuned(4, [1])], Clock(), max_trials=1) == 2
    log = (tools.paths.data_dir / "runs" / "crawl_sess.jsonl").read_text(encoding="utf-8")
    outcome = [json.loads(line) for line in log.splitlines() if '"kind": "outcome"' in line][-1]
    assert outcome["needs_before"] == [{"id": "energy", "value": 98}]
    assert outcome["needs_after"] == [{"id": "energy", "value": 40}]


def test_f8_environment_report_is_one_line(tmp_path, capsys):
    db = tmp_path / "atlas.db"
    _import(db, "1.1", [_affordance(1, "cook"), _affordance(2, "sit")])
    tools = FakeTools(tmp_path)
    tools.replies = ["TRIAL_PUSHED exp interaction 1"]
    tools.rows = [_verdict("exp", guid=2, name="sit")]
    preflight = [
        {"kind": "preflight", "object_id": "7", "guid64": 1, "ok": False,
         "reason": "Object failed state check"},
        {"kind": "preflight", "object_id": "7", "guid64": 9, "ok": False,
         "reason": "Object failed state check"},
        {"kind": "preflight", "object_id": "8", "guid64": 2, "ok": True, "reason": None},
    ]
    _drive(tools, db, [_tuned(8, [2])], Clock(), max_trials=1, preflight_rows=preflight)
    line = [item for item in capsys.readouterr().out.splitlines() if item.startswith("environment ")]
    assert len(line) == 1
    assert "7" in line[0] and "Object failed state check" in line[0]
