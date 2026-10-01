"""Sequential LAB trials with read-only evidence collection."""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .. import telemetry
from ..mcp_server import DomusTools
from ..vendor import cmdbox


def outside_sims(out, paths):
    out = Path(out).resolve()
    if out == paths.sims_root.resolve() or paths.sims_root.resolve() in out.parents:
        raise ValueError("evidence output must be outside the Sims root")
    return out


def wait_session(paths, timeout, previous=()):
    deadline = time.monotonic() + timeout
    while True:
        try:
            session = telemetry.latest_session(paths=paths)
            records = list(telemetry.rows(session))
            if session not in previous and any(r["event_kind"] == "session_open" for r in records):
                return session
        except FileNotFoundError:
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError("session telemetry did not appear")
        time.sleep(0.25)


def wait_verdict(session, experiment_id, timeout):
    deadline = time.monotonic() + timeout
    while True:
        for row in telemetry.rows(session):
            if (row["event_kind"] == "experiment_event"
                    and row["e2"]["phase"] == "VERDICT"
                    and row["e2"]["experiment_id"] == experiment_id):
                return row
        if time.monotonic() >= deadline:
            raise TimeoutError(f"no VERDICT for {experiment_id}")
        time.sleep(0.25)


def inventory(paths):
    result = []
    for path in sorted((paths.sims_root / "saves").rglob("*")):
        if path.is_file():
            stat = path.stat()
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            result.append(dict(path=str(path), size=stat.st_size,
                               mtime_ns=stat.st_mtime_ns, sha256=digest.hexdigest(),
                               read_only=True))
    return result


def write_evidence(out, session, paths):
    outside_sims(out, paths)  # Resolve again immediately before writing.
    out.mkdir(parents=True, exist_ok=True)
    for segment in telemetry.segments(session):
        (out / segment.name).write_bytes(segment.read_bytes())
    (out / paths.ledger.name).write_bytes(paths.ledger.read_bytes())
    (out / "save_inventory.json").write_text(
        json.dumps(inventory(paths), indent=2) + "\n", encoding="utf-8")
    # Every report line is a literal validated telemetry row: no commentary,
    # inferred verdicts, reply output, or hand-authored session narrative.
    records = list(telemetry.rows(out / session.name))
    (out / "session.md").write_text(
        "```jsonl\n" + "\n".join(json.dumps(r, sort_keys=True) for r in records)
        + "\n```\n", encoding="utf-8")


def run(save, objects, repeat, out, *, client=None, verdict_timeout=60):
    client = client or DomusTools()
    out = outside_sims(out, client.paths)
    if save not in ("lab_e1", "lab_e1_fork") or type(repeat) is not int or repeat < 1 or not objects:
        raise ValueError("require a LAB save, objects, and positive repeat")
    for object_id in objects:
        _, error = cmdbox.parse(json.dumps(dict(v=1, id="a" * 32,
            issued_at_ms=0, expires_at_ms=30000, issuer=client.issuer,
            command="sit_trial", args={"object_id": object_id})).encode(), 0, ())
        if error:
            raise ValueError(error)
    # Do not overwrite an earlier evidence folder, even outside Sims.
    if out.exists():
        raise ValueError("evidence output must be a new directory")
    failure = None
    session = None
    try:
        previous = set(client.paths.telemetry.glob("ashley_e1_*.jsonl"))
        client.command("status")
        client.command("arm", {"name": save})
        client.command("start")
        session = wait_session(client.paths, verdict_timeout, previous)
        for object_id in objects:
            for _ in range(repeat):
                reply = client.command("sit_trial", {"object_id": object_id})
                ids = [match.group(1) for line in reply.result.get("lines", [])
                       if (match := re.fullmatch(r"PUSHED ([0-9a-f]{8}-[0-9]+) interaction .+", line))]
                if len(ids) != 1:
                    raise ValueError("sit_trial reply lacks a unique PUSHED experiment id")
                wait_verdict(session, ids[0], verdict_timeout)
    except Exception as error:
        failure = error
    finally:
        # Attempt both in order even if either fails; bypass preflight so an
        # earlier status rejection cannot prevent best-effort cleanup.
        for name in ("stop", "disarm"):
            try:
                client.send(name, {})
            except Exception as error:
                print(f"cleanup {name}: {error}", file=sys.stderr)
                if failure is None:
                    failure = error
        if session is not None:
            try:
                write_evidence(out, session, client.paths)
            except Exception as error:
                if failure is None:
                    failure = error
    if failure is not None:
        raise failure
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", required=True, choices=("lab_e1", "lab_e1_fork"))
    parser.add_argument("--objects", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        run(args.save, args.objects.split(","), args.repeat, args.out)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
