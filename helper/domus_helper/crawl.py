"""Unattended one-at-a-time probe trials against the lab save."""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from . import atlas, pace, relief_survey, telemetry
from .crawl_protocol import PROTOCOL_SKIP, RETRY_CODES, name_blocked

# Dialog-free food guids run only through `python -m domus_helper.food` (DA6D).
FOOD_GUIDS = (13388, 13397)
# A sleep at normal speed is about 8 real minutes; a slow-speed sleep is longer.
# W3h: a game-time wait; drive() stretches it by slow_time (pace.game_budget).
LEFT_RUNNING_MAX_S = 45 * 60
from .vendor.schema import PROBE_VERSION
from .mcp_server import CommandFailed, DomusTools, SafetyError
from .paths import Paths


class CrawlStop(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _flag(row, key):
    value = row[key]
    if value is True:
        return 1
    if value is False or value is None:
        return 0
    return int(value)


def _object_key(value):
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def load_tuned(path):
    rows = []
    build = None
    with Path(path).open("rb") as handle:
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            row = json.loads(raw)
            if row.get("kind") == "tuned_header":
                build = row.get("sims_build")
            rows.append(row)
    return build, rows


def latest_tuned(atlas_dir):
    folder = Path(atlas_dir)
    files = [path for path in folder.glob("tuned_*.jsonl")
             if path.is_file() and not path.name.endswith(".partial")]
    if not files:
        raise FileNotFoundError("no tuned scan")
    return max(files, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _skipped(name, skip):
    text = str(name).lower()
    return any(part.lower() in text for part in skip)


def plan(build, tuned_rows, atlas_db, limit, *, readonly=False, skip=(),
         preflight_rows=None):
    if type(limit) is not int or limit < 1:
        raise ValueError("limit")
    connection = atlas._open(atlas_db, readonly=readonly)
    try:
        if not atlas._has(connection, "affordances"):
            return []
        affordances = {}
        for row in connection.execute(
                "SELECT guid64, name, is_super, is_social, allow_user_directed "
                "FROM affordances WHERE build = ?", (build,)):
            affordances[int(row["guid64"])] = row
        counts = {}
        blocked = set()
        if atlas._has(connection, "trials"):
            try:
                trial_rows = connection.execute(
                    "SELECT guid64, outcome, object_id FROM trials WHERE build = ?",
                    (build,)).fetchall()
            except sqlite3.OperationalError:
                trial_rows = []
            for row in trial_rows:
                counts.setdefault(int(row["guid64"]), []).append(row)
                if row["outcome"] in ("STALE_TARGET", "PUSH_REFUSED"):
                    blocked.add((int(row["guid64"]), str(row["object_id"])))
    finally:
        connection.close()
    states = {item["guid64"]: item["state"] for item in atlas.qualification(
        atlas_db, build, readonly=readonly)}
    allowed = None
    if preflight_rows is not None:
        allowed = set()
        for item in preflight_rows:
            if item.get("kind") != "preflight" or item.get("ok") is not True:
                continue
            try:
                allowed.add((str(item.get("object_id")), int(item.get("guid64"))))
            except (TypeError, ValueError):
                continue
    chosen = {}
    for row in tuned_rows:
        if row.get("kind") != "tuned_on_class":
            continue
        object_id = row.get("object_id")
        if object_id is None:
            continue
        for guid in row.get("affordance_guid64s") or ():
            try:
                guid = int(guid)
            except (TypeError, ValueError):
                continue
            affordance = affordances.get(guid)
            if affordance is None:
                continue
            if _flag(affordance, "is_super") != 1 or _flag(affordance, "allow_user_directed") != 1:
                continue
            if _flag(affordance, "is_social") != 0 or name_blocked(affordance["name"]):
                continue
            if guid in FOOD_GUIDS or _skipped(affordance["name"], skip):
                continue
            if any(part in affordance["name"] for part in PROTOCOL_SKIP):
                continue
            if (guid, str(object_id)) in blocked:
                continue
            if allowed is not None and (str(object_id), guid) not in allowed:
                continue
            state = states.get(guid, "UNTESTED")
            if state not in ("UNTESTED", "IN_PROGRESS"):
                continue
            current = chosen.get(guid)
            if current is None or _object_key(object_id) < _object_key(current["object_id"]):
                chosen[guid] = {
                    "guid64": guid, "object_id": str(object_id),
                    "name": affordance["name"],
                    "trials": len(counts.get(guid, ())),
                }
    ordered = sorted(chosen.values(), key=lambda item: (
        item["trials"], item["guid64"], _object_key(item["object_id"])))
    return ordered[:limit]


def _classify(lines):
    for line in lines or ():
        if not isinstance(line, str):
            continue
        if line == "PUSH_FAILED" or line.startswith("PUSH_FAILED "):
            return "PUSH_FAILED", None, None
        if line.startswith("PUSH_REFUSED"):
            reason = line[len("PUSH_REFUSED"):].strip()
            return "PUSH_REFUSED", None, reason
        if line.startswith("TRIAL_PUSHED "):
            parts = line.split()
            if len(parts) >= 2:
                return "TRIAL_PUSHED", parts[1], None
        if line.startswith("TRIAL_REJECT "):
            code = line[len("TRIAL_REJECT "):]
            if code == "NO_OBJECT":
                return "STALE_TARGET", None, "NO_OBJECT"
            return "TRIAL_REJECT", None, code
        if line == "E2_UNAVAILABLE":
            return "TRIAL_REJECT", None, "E2_UNAVAILABLE"
    return "TRIAL_REJECT", None, "BAD_REPLY"


def _append(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _verdict_row(rows, experiment_id):
    for row in rows:
        if row.get("event_kind") != "experiment_event":
            continue
        e2 = row.get("e2") or {}
        if e2.get("phase") == "VERDICT" and e2.get("experiment_id") == experiment_id:
            return row
    return None


BODY_MOTIVES = ("bladder", "hunger", "energy", "hygiene")
DISTRESS_AT = 20


def distress_text(rows):
    """D23: name the body needs in distress (probe band: value <= 20), or None."""
    found = []
    for item in (_latest_presence(rows) or {}).get("motives") or ():
        if not isinstance(item, dict) or item.get("id") not in BODY_MOTIVES:
            continue
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if item.get("band") == "distress" or value <= DISTRESS_AT:
            found.append("%s %d" % (item.get("id"), value))
    return ", ".join(found) or None


def matching_preflight(atlas_dir, tuned_path):
    """Rows from the newest preflight file that is newer than the tuned scan."""
    folder = Path(atlas_dir)
    files = [path for path in folder.glob("preflight_*.jsonl")
             if path.is_file() and not path.name.endswith(".partial")]
    if not files:
        return None
    newest = max(files, key=lambda path: (path.stat().st_mtime_ns, path.name))
    tuned = Path(tuned_path)
    if tuned.exists() and newest.stat().st_mtime_ns < tuned.stat().st_mtime_ns:
        return None
    _build, rows = load_tuned(newest)
    return rows


# D22 (live 2026-10-04): a fixed 600 s wait met a 600 s preflight. Wait while the
# partial file grows; give up after this long without growth, or at the hard cap.
# W3h: real time on the probe's own scan (real-time alarm), not game time: unchanged at slow_time.
PREFLIGHT_STALL_S = 120.0


def _partial_size(folder, since):
    size = 0
    for path in folder.glob("preflight_*.jsonl.partial"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime >= since:
            size += stat.st_size
    return size


def wait_preflight(atlas_dir, since, timeout, sleep=time.sleep, monotonic=time.monotonic,
                   stall=PREFLIGHT_STALL_S):
    """Rows of the first preflight file finished after `since` (D9)."""
    deadline = monotonic() + timeout
    last_size = -1
    grew_at = monotonic()
    while True:
        folder = Path(atlas_dir)
        files = [path for path in folder.glob("preflight_*.jsonl")
                 if path.is_file() and not path.name.endswith(".partial")
                 and path.stat().st_mtime >= since]
        files.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
        for path in reversed(files):
            _build, rows = load_tuned(path)
            if rows and rows[-1].get("kind") == "preflight_footer":
                return rows
        now = monotonic()
        size = _partial_size(folder, since)
        if size != last_size:
            last_size = size
            grew_at = now
        if now >= deadline:
            raise TimeoutError("preflight footer")
        if now - grew_at >= stall:
            raise TimeoutError("preflight stalled for %d s" % int(now - grew_at))
        sleep(1.0)


def fresh_preflight(client, timeout=1800, sleep=time.sleep, monotonic=time.monotonic):
    """D9 (live 2026-10-04): the crawl used only an older preflight file, and none
    existed, so nothing was filtered. Ask for one and wait for its footer."""
    since = time.time() - 1
    client.command("preflight", {})
    return wait_preflight(client.paths.atlas_dir, since, timeout, sleep, monotonic)


def _cleanup_detail(rows, experiment_id):
    for row in rows or ():
        e2 = row.get("e2") or {}
        if e2.get("phase") == "TRIAL_CLEANUP" and e2.get("experiment_id") == experiment_id:
            return e2.get("detail") or ""
    return None


def _needs_of(row):
    found = []
    for item in (row or {}).get("motives") or []:
        if isinstance(item, dict):
            found.append({"id": item.get("id"), "value": item.get("value")})
    return found


def wait_left_running(read_rows, experiment_id, sleep, monotonic, timeout=None):
    """D13: a relief (sleep, toilet, a meal) is left running past its verdict. Wait
    until she is idle again and return the needs then: the relief telemetry."""
    if timeout is None:
        timeout = LEFT_RUNNING_MAX_S
    # W3h (C9): the cleanup detail and the idle debounce are real seconds on the probe's real-time rows,
    # so they mean the same at slow_time 0.5; only the game-time budget above is stretched.
    deadline = monotonic() + 5.0
    detail = None
    for _ in range(20):
        detail = _cleanup_detail(read_rows(), experiment_id)
        if detail is not None or monotonic() >= deadline:
            break
        sleep(0.25)
    if not detail or not detail.endswith("_left_running"):
        return None
    deadline = monotonic() + timeout
    idle_since = None
    for _ in range(int(timeout) + 1):
        if monotonic() >= deadline:
            break
        latest = _latest_presence(read_rows())
        if _body_idle(latest):
            if idle_since is None:
                idle_since = monotonic()
            elif monotonic() - idle_since >= 5.0:
                return {"needs_finish": _needs_of(latest), "detail": detail}
        else:
            idle_since = None
        sleep(1.0)
    return {"needs_finish": [], "detail": detail, "timeout": True}


IDLE_SOURCES = ("InteractionSource.POSTURE_GRAPH", "InteractionSource.BODY_CANCEL_AOP",
                "InteractionSource.CARRY_CANCEL_AOP")


def _latest_presence(rows):
    found = None
    for row in rows or ():
        if row.get("event_kind") == "presence_snapshot":
            found = row
    return found


def _body_idle(row):
    """No running action except posture: she has finished what she was doing."""
    entries = ((row or {}).get("interactions") or {}).get("observed") or []
    for entry in entries:
        if (entry.get("membership") in ("RUNNING", "QUEUED_AND_RUNNING") and
                entry.get("source_raw") not in IDLE_SOURCES):
            return False
    return True


def environment_line(rows):
    """One line for objects whose every tested affordance failed for the same reason."""
    grouped = {}
    for row in rows or ():
        if row.get("kind") != "preflight":
            continue
        if row.get("reason") in ("picker", "social", "deny_name"):
            continue
        grouped.setdefault(str(row.get("object_id")), []).append(row)
    parts = []
    for object_id in sorted(grouped, key=_object_key):
        items = grouped[object_id]
        if not items or any(item.get("ok") is True for item in items):
            continue
        reasons = {item.get("reason") for item in items}
        if len(reasons) == 1:
            parts.append("%s=%s" % (object_id, next(iter(reasons))))
    if not parts:
        return None
    return "environment " + "; ".join(parts)


def _from_verdict(found, fallback_name):
    e2 = found.get("e2") or {}
    code = e2.get("code") or "OUTCOME_UNKNOWN"
    detail = e2.get("detail") or ""
    if code == "INTERRUPTED":
        outcome = "INTERRUPTED"
    elif code == "OUTCOME_UNKNOWN" and "never_started=1" in detail:
        outcome = "NEVER_STARTED"
    elif code in ("PASS", "OUTCOME_UNKNOWN"):
        outcome = code
    else:
        outcome = "OUTCOME_UNKNOWN"
    ambiguous = json.dumps(e2.get("ambiguous")) if e2.get("ambiguous") is not None else None
    tuning = e2.get("tuning_name") or fallback_name
    return outcome, code, ambiguous, tuning


def _phase_sequence(rows, experiment_id, phase):
    for row in rows:
        e2 = row.get("e2") or {}
        if e2.get("phase") == phase and e2.get("experiment_id") == experiment_id:
            return row.get("written_sequence")
    return None


def _needs_near(rows, sequence):
    if type(sequence) is not int:
        return []
    best = None
    best_dist = None
    for row in rows:
        if row.get("event_kind") != "presence_snapshot":
            continue
        seq = row.get("written_sequence")
        if type(seq) is not int:
            continue
        dist = abs(seq - sequence)
        if best is None or dist < best_dist:
            best = row
            best_dist = dist
    found = []
    for item in (best or {}).get("motives") or []:
        if isinstance(item, dict):
            found.append({"id": item.get("id"), "value": item.get("value")})
    return found


def _rescan(client, tuned_rows, preflight_rows, use_preflight):
    try:
        client.command("tuned_scan", {})
        client.command("preflight", {})
    except Exception:
        return tuned_rows, preflight_rows
    try:
        folder = client.paths.atlas_dir
        tuned_path = latest_tuned(folder)
        _build, tuned_rows = load_tuned(tuned_path)
        if use_preflight:
            fresh = matching_preflight(folder, tuned_path)
            if fresh is not None:
                preflight_rows = fresh
    except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError):
        return tuned_rows, preflight_rows
    return tuned_rows, preflight_rows


def reconcile(log_path, telemetry_rows, atlas_db, build, session):
    """Record a verdict that landed after the crawl that pushed it had stopped."""
    if not log_path.exists():
        return
    pending = []
    done = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("kind") == "send" and row.get("reply") == "TRIAL_PUSHED"
                and row.get("experiment_id")):
            pending.append(row)
        elif row.get("kind") == "outcome":
            experiment_id = row.get("experiment_id")
            if experiment_id:
                done.add(experiment_id)
            elif pending:
                done.add(pending.pop(0)["experiment_id"])
    source = list(telemetry_rows or ())
    for row in pending:
        experiment_id = row["experiment_id"]
        if experiment_id in done:
            continue
        found = _verdict_row(source, experiment_id)
        if found is None:
            outcome, code, ambiguous, tuning = "TIMEOUT", "TIMEOUT", None, row.get("name")
        else:
            outcome, code, ambiguous, tuning = _from_verdict(found, row.get("name"))
        atlas.record_trial(
            atlas_db, build, experiment_id, row.get("guid64"), row.get("object_id"),
            outcome, code, ambiguous, tuning, session, probe_version=PROBE_VERSION)
        _append(log_path, {
            "kind": "outcome", "guid64": row.get("guid64"), "object_id": row.get("object_id"),
            "outcome": outcome, "code": code, "experiment_id": experiment_id,
            "reconciled": True,
        })
        done.add(experiment_id)


def drive(*, client, build, tuned_rows, atlas_db, per_hour=30, max_trials=200,
          dry_run=False, verdict_timeout_s=600, limit=10**9, readonly=False,
          sleep=time.sleep, monotonic=time.monotonic, telemetry_rows=None,
          session="none", skip=(), preflight_rows=None, use_preflight=True,
          survey=False, slow_time=1.0):
    if not 1 <= per_hour <= 60:
        raise ValueError("per-hour")
    if max_trials < 1 or verdict_timeout_s <= 0:
        raise ValueError("bounds")
    active = preflight_rows if use_preflight else None
    tuned_rows = list(tuned_rows)
    candidates = plan(build, tuned_rows, atlas_db, limit, readonly=readonly or dry_run,
                      skip=skip, preflight_rows=active)
    if dry_run:
        for item in candidates:
            print("%s %s %s" % (item["guid64"], item["name"], item["object_id"]))
        print("candidates %d" % len(candidates))
        return 0
    log_path = client.paths.data_dir / "runs" / ("crawl_%s.jsonl" % session)
    report = environment_line(active)
    if report:
        print(report)
    source = telemetry_rows() if telemetry_rows else []
    reconcile(log_path, source, atlas_db, build, session)
    interval = 3600.0 / per_hour
    origin = None
    logged_reasons = set()
    last_send = None
    recorded = 0
    outcomes = []
    distress = 0
    number = 0
    stale_run = 0
    # A restarted crawl in the same game session must not reuse "<session>:0".
    run_tag = "%x" % time.time_ns()
    while recorded < max_trials:
        try:
            status = client.checked_status().result
        except SafetyError as error:
            raise CrawlStop(str(error))
        reason = None
        if status.get("state") != "SAMPLING":
            reason = "state=%s" % status.get("state")
        elif status.get("armed_name") != "LAB_E1_FORK":
            reason = "armed_name=%s" % status.get("armed_name")
        elif status.get("calibrate"):
            reason = "calibrate"
        if reason:
            if reason not in logged_reasons:
                logged_reasons.add(reason)
                _append(log_path, {"kind": "wait", "reason": reason})
            sleep(10)
            continue
        if origin is None:
            origin = (status.get("lineage_class"), status.get("designated_sim_id"))
        elif (status.get("lineage_class"), status.get("designated_sim_id")) != origin:
            changed = "lineage_class" if status.get("lineage_class") != origin[0] else "designated_sim_id"
            raise CrawlStop("%s changed" % changed)
        item = None
        now_rows = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
        if survey:
            need = relief_survey.low_need(relief_survey.motives_of(_latest_presence(now_rows)))
            if need is not None:
                item = relief_survey.cure_for(need, active)
                # D24 (live): no cure found fell back to an unfiltered plan and pushed
                # a shower upgrade into bladder distress.
                if item is None:
                    raise CrawlStop("relief survey: %s is low and no preflight-approved "
                                    "cure for it is on the lot" % need)
        if item is None:
            # D23 (live): two trials were pushed into a distress the rows already showed.
            distressed = distress_text(now_rows)
            if distressed is not None:
                raise CrawlStop("the lab Sim needs care: %s (distress); no trial pushed"
                                % distressed)
            candidates = plan(build, tuned_rows, atlas_db, limit, readonly=False, skip=skip,
                              preflight_rows=active)
            if not candidates:
                return 0
            item = candidates[0]
        if last_send is not None:
            gap = interval - (monotonic() - last_send)
            if gap > 0:
                sleep(gap)
        try:
            reply = client.command("trial", {
                "object_id": item["object_id"], "guid64": str(item["guid64"])})
        except SafetyError as error:
            raise CrawlStop(str(error))
        except CommandFailed as error:
            # A probe refusal comes back as inbox status REJECTED; its lines still
            # carry TRIAL_REJECT <CODE> / PUSH_FAILED, so classify them the same way.
            reply = error.reply
        kind, experiment_id, code = _classify((reply.result or {}).get("lines"))
        if kind == "TRIAL_PUSHED":
            last_send = monotonic()
        _append(log_path, {
            "kind": "send", "guid64": item["guid64"], "name": item["name"],
            "object_id": item["object_id"], "reply": kind, "code": code,
            "experiment_id": experiment_id,
        })
        if kind == "TRIAL_REJECT" and code == "TRIAL_STORM":
            raise CrawlStop("TRIAL_STORM")
        if kind == "TRIAL_REJECT" and code in RETRY_CODES:
            sleep(15)
            continue
        if kind == "TRIAL_PUSHED":
            # W3h: the verdict comes when the game finishes the trial, so the budget is game time.
            deadline = monotonic() + pace.game_budget(verdict_timeout_s, slow_time)
            found = None
            while monotonic() < deadline:
                source = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
                found = _verdict_row(source, experiment_id)
                if found:
                    break
                sleep(0.25)
            source = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
            if found is None:
                outcome, code = "TIMEOUT", "TIMEOUT"
                ambiguous = None
                tuning = item["name"]
                needs_before, needs_after = [], []
            else:
                outcome, code, ambiguous, tuning = _from_verdict(found, item["name"])
                needs_before = _needs_near(source, _phase_sequence(source, experiment_id, "PUSHED"))
                needs_after = _needs_near(source, _phase_sequence(source, experiment_id, "VERDICT"))
            experiment_key = experiment_id
        else:
            if kind in ("PUSH_FAILED", "TRIAL_REJECT", "STALE_TARGET", "PUSH_REFUSED"):
                outcome = kind
            else:
                outcome = "TRIAL_REJECT"
            experiment_key = "%s:%s:%d" % (session, run_tag, number)
            number += 1
            ambiguous = None
            tuning = item["name"]
            needs_before, needs_after = [], []
            source = []
        recorded += 1
        atlas.record_trial(
            atlas_db, build, experiment_key, item["guid64"], item["object_id"],
            outcome, code, ambiguous, tuning, session, probe_version=PROBE_VERSION)
        relief = None
        if kind == "TRIAL_PUSHED" and found is not None:
            relief = wait_left_running(
                (lambda: telemetry_rows() if telemetry_rows else _live_rows(client.paths)),
                experiment_id, sleep, monotonic, timeout=pace.game_budget(LEFT_RUNNING_MAX_S, slow_time))
        payload = {
            "kind": "outcome", "n": recorded, "guid64": item["guid64"],
            "object_id": item["object_id"], "outcome": outcome, "code": code,
            "experiment_id": experiment_id, "needs_before": needs_before,
            "needs_after": needs_after, "relief": item.get("relief"),
        }
        if relief is not None:
            payload["needs_finish"] = relief["needs_finish"]
            payload["cleanup"] = relief["detail"]
        _append(log_path, payload)
        print("trial %d %s %s %s -> %s (%s)%s" % (
            recorded, item["guid64"], item["name"], item["object_id"], outcome, code,
            (" relief=%s" % item["relief"]) if item.get("relief") else ""))
        outcomes.append(outcome)
        if code == "NEED_DISTRESS":
            distress += 1
            if distress >= 2:
                distressed = distress_text(
                    telemetry_rows() if telemetry_rows else _live_rows(client.paths))
                raise CrawlStop("the lab Sim needs care: %s, then restart"
                                % (distressed or "a body need is in distress"))
        else:
            distress = 0
        if len(outcomes) >= 5 and all(item == "PUSH_FAILED" for item in outcomes[-5:]):
            raise CrawlStop("5 consecutive PUSH_FAILED")
        if len(outcomes) >= 10 and outcomes[-10:].count("PUSH_FAILED") >= 8:
            raise CrawlStop("8 of the last 10 were PUSH_FAILED")
        if outcome == "STALE_TARGET":
            stale_run += 1
            if stale_run == 3:
                tuned_rows, active = _rescan(client, tuned_rows, active, use_preflight)
        if recorded >= max_trials:
            raise CrawlStop("max-trials %d" % max_trials)
        if kind != "TRIAL_PUSHED":
            sleep(2)
    return 0


def _live_rows(paths):
    """JSONL rows, not the vendored validator.

    DA6A adds verdict fields the current schema rejects. A partial last line
    is ignored, same as telemetry.raw_rows.
    """
    try:
        session = telemetry.latest_session(paths=paths)
    except FileNotFoundError:
        return []
    found = []
    for segment in telemetry.segments(session):
        found.extend(telemetry.raw_rows(segment))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-hour", type=int, default=30)
    parser.add_argument("--max-trials", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verdict-timeout-s", type=float, default=600)
    parser.add_argument("--tuned-file", type=Path)
    parser.add_argument("--limit", type=int, default=10**9)
    # Session-only exclusion by name part (case-insensitive), e.g. Upgrade: upgrades
    # need parts she does not carry, so each push fails and five latch TRIAL_STORM.
    parser.add_argument("--skip", action="append", default=[])
    parser.add_argument("--no-preflight", action="store_true")
    # Telemetry, not her policy: measure a low need's cure before the next trial.
    parser.add_argument("--relief-survey", action="store_true")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    try:
        if args.tuned_file:
            tuned_path = args.tuned_file
            build, rows = load_tuned(tuned_path)
        else:
            tuned_path = latest_tuned(paths.atlas_dir)
            build, rows = load_tuned(tuned_path)
        if not build:
            raise ValueError("tuned scan has no sims_build")
        preflight_rows = None
        client = DomusTools(paths=paths)
        if args.no_preflight or args.dry_run:
            # D24 (live): --no-preflight dropped all filtering instead of reusing the
            # preflight that had just finished. It now means "do not run a new one".
            preflight_rows = matching_preflight(tuned_path.parent, tuned_path)
            print("preflight: %s" % ("reusing the newest file" if preflight_rows
                                     else "none newer than the tuned scan; unfiltered"))
        else:
            preflight_rows = fresh_preflight(client)
        session = "none"
        if not args.dry_run:
            try:
                session = telemetry.latest_session(paths=paths).stem
            except FileNotFoundError:
                session = "none"
        return drive(
            client=client, build=build, tuned_rows=rows,
            atlas_db=paths.atlas_db, per_hour=args.per_hour, max_trials=args.max_trials,
            dry_run=args.dry_run, verdict_timeout_s=args.verdict_timeout_s,
            limit=args.limit, session=session, skip=tuple(args.skip),
            preflight_rows=preflight_rows, use_preflight=preflight_rows is not None,
            survey=args.relief_survey, slow_time=pace.configured_slow_time(paths.data_dir))
    except CrawlStop as error:
        print(str(error))
        return 2
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
