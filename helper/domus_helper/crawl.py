"""Unattended one-at-a-time probe trials against the lab save."""
import argparse
import json
import sys
import time
from pathlib import Path

from . import atlas, telemetry
from .crawl_protocol import RETRY_CODES, name_blocked
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


def plan(build, tuned_rows, atlas_db, limit, *, readonly=False, skip=()):
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
        if atlas._has(connection, "trials"):
            for row in connection.execute(
                    "SELECT guid64, outcome, code FROM trials WHERE build = ?", (build,)):
                counts.setdefault(int(row["guid64"]), []).append(row)
    finally:
        connection.close()
    states = {item["guid64"]: item["state"] for item in atlas.qualification(
        atlas_db, build, readonly=readonly)}
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
            if _skipped(affordance["name"], skip):
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
        if line.startswith("TRIAL_PUSHED "):
            parts = line.split()
            if len(parts) >= 2:
                return "TRIAL_PUSHED", parts[1], None
        if line.startswith("TRIAL_REJECT "):
            return "TRIAL_REJECT", None, line[len("TRIAL_REJECT "):]
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


def drive(*, client, build, tuned_rows, atlas_db, per_hour=30, max_trials=200,
          dry_run=False, verdict_timeout_s=600, limit=10**9, readonly=False,
          sleep=time.sleep, monotonic=time.monotonic, telemetry_rows=None,
          session="none", skip=()):
    if not 1 <= per_hour <= 60:
        raise ValueError("per-hour")
    if max_trials < 1 or verdict_timeout_s <= 0:
        raise ValueError("bounds")
    candidates = plan(build, tuned_rows, atlas_db, limit, readonly=readonly or dry_run, skip=skip)
    if dry_run:
        for item in candidates:
            print("%s %s %s" % (item["guid64"], item["name"], item["object_id"]))
        print("candidates %d" % len(candidates))
        return 0
    log_path = client.paths.data_dir / "runs" / ("crawl_%s.jsonl" % session)
    interval = 3600.0 / per_hour
    origin = None
    logged_reasons = set()
    last_send = None
    recorded = 0
    outcomes = []
    distress = 0
    number = 0
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
        candidates = plan(build, tuned_rows, atlas_db, limit, readonly=False, skip=skip)
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
        last_send = monotonic()
        kind, experiment_id, code = _classify((reply.result or {}).get("lines"))
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
            deadline = monotonic() + verdict_timeout_s
            found = None
            while monotonic() < deadline:
                source = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
                found = _verdict_row(source, experiment_id)
                if found:
                    break
                sleep(0.25)
            if found is None:
                outcome, code = "TIMEOUT", "TIMEOUT"
                ambiguous = None
                tuning = item["name"]
            else:
                e2 = found.get("e2") or {}
                code = e2.get("code") or "OUTCOME_UNKNOWN"
                outcome = code if code in ("PASS", "OUTCOME_UNKNOWN") else "OUTCOME_UNKNOWN"
                ambiguous = json.dumps(e2.get("ambiguous")) if e2.get("ambiguous") is not None else None
                tuning = e2.get("tuning_name") or item["name"]
            experiment_key = experiment_id
        else:
            outcome = kind if kind in ("PUSH_FAILED", "TRIAL_REJECT") else "TRIAL_REJECT"
            experiment_key = "%s:%s:%d" % (session, run_tag, number)
            number += 1
            ambiguous = None
            tuning = item["name"]
        recorded += 1
        atlas.record_trial(
            atlas_db, build, experiment_key, item["guid64"], item["object_id"],
            outcome, code, ambiguous, tuning, session)
        _append(log_path, {
            "kind": "outcome", "n": recorded, "guid64": item["guid64"],
            "object_id": item["object_id"], "outcome": outcome, "code": code,
        })
        print("trial %d %s %s %s -> %s (%s)" % (
            recorded, item["guid64"], item["name"], item["object_id"], outcome, code))
        outcomes.append(outcome)
        if code == "NEED_DISTRESS":
            distress += 1
            if distress >= 2:
                raise CrawlStop("the lab Sim needs care: feed/rest her, then restart")
        else:
            distress = 0
        if len(outcomes) >= 5 and all(item == "PUSH_FAILED" for item in outcomes[-5:]):
            raise CrawlStop("5 consecutive PUSH_FAILED")
        if len(outcomes) >= 10 and outcomes[-10:].count("PUSH_FAILED") >= 8:
            raise CrawlStop("8 of the last 10 were PUSH_FAILED")
        if recorded >= max_trials:
            raise CrawlStop("max-trials %d" % max_trials)
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
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    try:
        if args.tuned_file:
            build, rows = load_tuned(args.tuned_file)
        else:
            path = latest_tuned(paths.atlas_dir)
            build, rows = load_tuned(path)
        if not build:
            raise ValueError("tuned scan has no sims_build")
        session = "none"
        if not args.dry_run:
            try:
                session = telemetry.latest_session(paths=paths).stem
            except FileNotFoundError:
                session = "none"
        return drive(
            client=DomusTools(paths=paths), build=build, tuned_rows=rows,
            atlas_db=paths.atlas_db, per_hour=args.per_hour, max_trials=args.max_trials,
            dry_run=args.dry_run, verdict_timeout_s=args.verdict_timeout_s,
            limit=args.limit, session=session, skip=tuple(args.skip))
    except CrawlStop as error:
        print(str(error))
        return 2
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
