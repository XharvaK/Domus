"""E4: the proof kit. Private, append-only records in `proof/` under the data folder.

- trace-YYYYMMDD.jsonl: every pass of hers the overlay showed, once, as it was shown (a held line
  stays held), with what produced it (agent build, model, provider, provider request id, tokens,
  helper and probe versions, the game-only switch). Each line carries the previous line's hash and
  its own (sha256 of the line's canonical JSON without `sha256`), so the chain runs across days.
- ledger.jsonl: every arranged opportunity, unarranged tip, viewer-chosen change or flagged line,
  chained the same way.
- roots.jsonl: a day's root (the last hash of its trace), for timestamping.
- trace-YYYYMMDD.jsonl.ots: once a day is over, its trace file is timestamped with OpenTimestamps:
  only the file's sha256 goes to public calendar servers, and the standard `.ots` proof written
  beside it lets anyone check later, with the official client, that the file existed then and has
  not changed since.

Run: python -m domus_helper.proof root [YYYYMMDD] | verify FILE | ledger KIND NOTE [--link URL] | stamp [YYYYMMDD]
"""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .paths import Paths
from .spool import Spool

DIR = "proof"
GENESIS = "0" * 64
LEDGER_KINDS = ("arranged", "unarranged", "viewer_change", "flagged", "note")
_TRACED_LIMIT = 256


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def seal(record, prev_hash):
    body = dict(record, prev_hash=prev_hash)
    body["sha256"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    return body


def verify_lines(lines, prev_hash=None):
    """Checks every line's hash and the chain. Returns (ok, count, last_hash, first_bad_index)."""
    last = prev_hash
    count = 0
    for index, line in enumerate(lines):
        try:
            item = json.loads(line)
        except ValueError:
            return False, count, last, index
        claimed = item.pop("sha256", None)
        if claimed != hashlib.sha256(_canonical(item).encode("utf-8")).hexdigest():
            return False, count, last, index
        if last is not None and item.get("prev_hash") != last:
            return False, count, last, index
        last = claimed
        count += 1
    return True, count, last, None


class Chain:
    """One append-only chained file family; the last hash is kept in the spool."""

    def __init__(self, spool, folder, key):
        self._spool, self._folder, self._key = spool, folder, key

    def append(self, path, record):
        self._folder.mkdir(parents=True, exist_ok=True)
        line = seal(record, self._spool.get_kv(self._key) or GENESIS)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(_canonical(line) + "\n")
        self._spool.put_kv(self._key, line["sha256"])
        return line


class Trace:
    def __init__(self, spool, data_dir):
        self._folder = Path(data_dir) / DIR
        self._chain = Chain(spool, self._folder, "proof_trace_last")
        self._spool = spool
        raw = spool.get_kv("proof_traced")
        self._traced = json.loads(raw) if raw else []

    def shown(self, pass_id, shown, regime, now_ms):
        """Record a pass the first time it is on screen. Returns the sealed line, or None if known."""
        if not isinstance(pass_id, str) or pass_id in self._traced:
            return None
        day = datetime.fromtimestamp(now_ms / 1000).strftime("%Y%m%d")
        line = self._chain.append(self._folder / ("trace-%s.jsonl" % day), {
            "v": 1, "ts_ms": now_ms, "pass": pass_id, "shown": shown, "regime": regime})
        self._traced = (self._traced + [pass_id])[-_TRACED_LIMIT:]
        self._spool.put_kv("proof_traced", json.dumps(self._traced))
        return line


# OpenTimestamps: public calendar servers, and the detached-proof header (magic, version 1, sha256).
CALENDARS = ("https://a.pool.opentimestamps.org", "https://b.pool.opentimestamps.org")
OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
OTS_VERSION = b"\x01"
OTS_SHA256 = b"\x08"
_CALENDAR_LIMIT = 10_000


def _submit(calendar, digest):
    """POST the 32-byte digest to a calendar; its pending timestamp (serialized ops) or None."""
    request = urllib.request.Request(calendar + "/digest", data=digest, method="POST", headers={
        "Accept": "application/vnd.opentimestamps.v1", "User-Agent": "domus-helper"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(_CALENDAR_LIMIT + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    return body if 0 < len(body) <= _CALENDAR_LIMIT else None


def stamp(data_dir, day, submit=None):
    """Timestamp a finished day's trace: one `.ots` proof per answering calendar, written beside it
    (`trace-DAY.jsonl.ots`, then `.ots2` for the second calendar). Returns what was written."""
    folder = Path(data_dir) / DIR
    path = folder / ("trace-%s.jsonl" % day)
    if not path.is_file():
        return {"day": day, "stamped": [], "reason": "no_trace"}
    digest = hashlib.sha256(path.read_bytes()).digest()
    written = []
    for index, calendar in enumerate(CALENDARS):
        target = path.with_name(path.name + (".ots" if index == 0 else ".ots%d" % (index + 1)))
        if target.exists():
            written.append(target.name)
            continue
        pending = (submit or _submit)(calendar, digest)
        if pending is None:
            continue
        target.write_bytes(OTS_MAGIC + OTS_VERSION + OTS_SHA256 + digest + pending)
        written.append(target.name)
    return {"day": day, "sha256": digest.hex(), "stamped": written}


def stamp_finished_days(data_dir, today, submit=None):
    """Every past day with a trace and no proof yet (today is still being written)."""
    folder = Path(data_dir) / DIR
    results = []
    for path in sorted(folder.glob("trace-*.jsonl")) if folder.is_dir() else []:
        day = path.stem.split("-", 1)[1]
        if day < today and not path.with_name(path.name + ".ots").exists():
            results.append(stamp(data_dir, day, submit))
    return results


def ledger(spool, data_dir, kind, note, link=None, now_ms=None):
    if kind not in LEDGER_KINDS:
        raise ValueError("kind must be one of %s" % ", ".join(LEDGER_KINDS))
    folder = Path(data_dir) / DIR
    record = {"v": 1, "at_ms": int(now_ms if now_ms is not None else time.time() * 1000), "kind": kind,
              "note": str(note)[:500]}
    if link:
        record["link"] = str(link)[:300]
    return Chain(spool, folder, "proof_ledger_last").append(folder / "ledger.jsonl", record)


def root(data_dir, day, now_ms=None):
    """The day's root: the last hash of its trace, appended to roots.jsonl (once per day and hash)."""
    folder = Path(data_dir) / DIR
    path = folder / ("trace-%s.jsonl" % day)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    ok, count, last, bad = verify_lines(lines)
    result = {"day": day, "lines": count, "root": last, "ok": ok}
    if bad is not None:
        result["first_bad_line"] = bad + 1
    if ok and last is not None:
        roots = folder / "roots.jsonl"
        known = roots.read_text(encoding="utf-8") if roots.is_file() else ""
        if '"root":"%s"' % last not in known:
            with open(roots, "a", encoding="utf-8") as handle:
                handle.write(_canonical({"day": day, "lines": count, "root": last,
                                         "at_ms": int(now_ms if now_ms is not None else time.time() * 1000)}) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.proof")
    sub = parser.add_subparsers(dest="command", required=True)
    root_cmd = sub.add_parser("root")
    root_cmd.add_argument("day", nargs="?")
    verify_cmd = sub.add_parser("verify")
    verify_cmd.add_argument("file")
    ledger_cmd = sub.add_parser("ledger")
    ledger_cmd.add_argument("kind", choices=LEDGER_KINDS)
    ledger_cmd.add_argument("note")
    ledger_cmd.add_argument("--link")
    stamp_cmd = sub.add_parser("stamp")
    stamp_cmd.add_argument("day", nargs="?")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    if args.command == "stamp":
        if args.day:
            results = [stamp(paths.data_dir, args.day)]
        else:
            results = stamp_finished_days(paths.data_dir, datetime.now().strftime("%Y%m%d"))
        print(json.dumps(results))
        return 0
    if args.command == "verify":
        ok, count, last, bad = verify_lines(Path(args.file).read_text(encoding="utf-8").splitlines())
        print(json.dumps({"ok": ok, "lines": count, "last": last,
                          **({"first_bad_line": bad + 1} if bad is not None else {})}))
        return 0 if ok else 1
    if args.command == "root":
        result = root(paths.data_dir, args.day or datetime.now().strftime("%Y%m%d"))
        print(json.dumps(result))
        return 0 if result["ok"] else 1
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    spool = Spool(paths.data_dir / "spool.db")
    try:
        line = ledger(spool, paths.data_dir, args.kind, args.note, args.link)
        print(json.dumps({"kind": line["kind"], "sha256": line["sha256"]}))
        return 0
    finally:
        spool.close()


if __name__ == "__main__":
    raise SystemExit(main())
