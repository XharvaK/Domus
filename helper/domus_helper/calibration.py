"""Deterministic calibration tables from recorded telemetry. No game imports."""
import argparse
import json
import math
from pathlib import Path

from . import telemetry
from .paths import Paths

RUNNING = ("RUNNING", "QUEUED_AND_RUNNING")
AUTONOMY = "InteractionSource.AUTONOMY"


def _nearest_rank(values, percent):
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return None
    rank = int(math.ceil((percent / 100.0) * count))
    if rank < 1:
        rank = 1
    if rank > count:
        rank = count
    return ordered[rank - 1]


def _iqr(values):
    if not values:
        return None
    return [_nearest_rank(values, 25), _nearest_rank(values, 75)]


def _median(values):
    return _nearest_rank(values, 50)


def _observed(row):
    return ((row.get("interactions") or {}).get("observed")) or []


def _running_affordances(row):
    found = []
    for entry in _observed(row):
        if entry.get("membership") in RUNNING and entry.get("affordance_id") is not None:
            found.append(entry["affordance_id"])
    return tuple(sorted(set(found)))


def _entry_id(entry):
    return entry.get("interaction_id") or entry.get("entry_key")


def _is_gap_row(row):
    kind = row.get("event_kind")
    return kind in ("lineage_event", "session_close")


def _presence(row):
    return row.get("event_kind") == "presence_snapshot"


def analyze(rows):
    rows = list(rows)
    gaps = 0
    previous_seq = None
    barrier = 0
    affordances = set()
    open_spans = {}
    closed = []
    presence = []
    for row in rows:
        seq = row.get("written_sequence")
        if previous_seq is not None and seq is not None and seq != previous_seq + 1:
            gaps += 1
            barrier += 1
        if _is_gap_row(row):
            gaps += 1
            barrier += 1
        if type(seq) is int:
            previous_seq = seq
        for entry in _observed(row):
            if entry.get("affordance_id") is not None:
                affordances.add(entry["affordance_id"])
        if not _presence(row):
            continue
        presence.append((row, barrier))
        running = {}
        for entry in _observed(row):
            iid = _entry_id(entry)
            if iid is None or entry.get("membership") not in RUNNING:
                continue
            running[iid] = entry
        for iid, span in list(open_spans.items()):
            if iid not in running:
                span["end"] = row
                span["end_barrier"] = barrier
                closed.append(span)
                del open_spans[iid]
        for iid, entry in running.items():
            if iid in open_spans:
                continue
            open_spans[iid] = {
                "entry": entry, "start": row, "start_barrier": barrier,
                "end": None, "end_barrier": None,
            }
    for span in open_spans.values():
        span["ambiguous_open"] = True
        closed.append(span)

    groups = {}
    autonomy_spans = 0
    for span in closed:
        entry = span["entry"]
        source = entry.get("source_raw")
        key = (entry.get("affordance_id"), entry.get("source_norm"), source)
        bucket = groups.setdefault(key, {"ticks": [], "wall": [], "ambiguous": 0})
        ambiguous = span.get("ambiguous_open") or span["start_barrier"] != span["end_barrier"]
        if not ambiguous and span["end"] is not None:
            crossed_pause = False
            started = False
            for row, _ in presence:
                if row is span["start"]:
                    started = True
                    continue
                if not started:
                    continue
                game = row.get("game") or {}
                if game.get("paused") is True:
                    crossed_pause = True
                if row is span["end"]:
                    break
            ambiguous = crossed_pause
        if ambiguous:
            bucket["ambiguous"] += 1
            continue
        start_g = span["start"].get("game") or {}
        end_g = span["end"].get("game") or {}
        bucket["ticks"].append(end_g.get("ticks") - start_g.get("ticks"))
        bucket["wall"].append(span["end"].get("wall_timestamp_ms") - span["start"].get("wall_timestamp_ms"))
        if source == AUTONOMY:
            autonomy_spans += 1

    durations = []
    for (aff, norm, source), bucket in sorted(groups.items(), key=lambda item: tuple("" if part is None else str(part) for part in item[0])):
        durations.append({
            "affordance_id": aff,
            "source_norm": norm,
            "source_raw": source,
            "control": "AUTONOMY" if source == AUTONOMY else None,
            "n": len(bucket["ticks"]),
            "median_ticks": _median(bucket["ticks"]),
            "iqr_ticks": _iqr(bucket["ticks"]),
            "median_wall_ms": _median(bucket["wall"]),
            "ambiguous": bucket["ambiguous"],
        })

    rates_raw = {}
    ticks_by_speed = {}
    wall_by_speed = {}
    for index in range(len(presence) - 1):
        left, left_barrier = presence[index]
        right, right_barrier = presence[index + 1]
        if left_barrier != right_barrier:
            continue
        left_game = left.get("game") or {}
        right_game = right.get("game") or {}
        left_ticks = left_game.get("ticks")
        right_ticks = right_game.get("ticks")
        if type(left_ticks) is not int or type(right_ticks) is not int:
            continue
        delta = right_ticks - left_ticks
        speed = left_game.get("clock_speed")
        if type(speed) is str and delta >= 0:
            ticks_by_speed[speed] = ticks_by_speed.get(speed, 0) + delta
            wall_delta = right.get("wall_timestamp_ms") - left.get("wall_timestamp_ms")
            if type(wall_delta) is int:
                wall_by_speed[speed] = wall_by_speed.get(speed, 0) + wall_delta
        if left_game.get("paused") is True or right_game.get("paused") is True:
            continue
        if delta <= 0:
            continue
        if (left.get("body") or {}).get("sim_id") != (right.get("body") or {}).get("sim_id"):
            continue
        activity = _running_affordances(left)
        motives_now = dict((item.get("id"), item.get("value")) for item in (right.get("motives") or []))
        for motive in left.get("motives") or []:
            motive_id = motive.get("id")
            if motive_id not in motives_now:
                continue
            before = motive.get("value")
            after = motives_now[motive_id]
            if type(before) not in (int, float) or type(after) not in (int, float):
                continue
            rate = (after - before) / float(delta)
            rates_raw.setdefault((motive_id, activity), []).append(rate)

    rates = []
    for (motive_id, activity), values in sorted(rates_raw.items(), key=lambda item: (str(item[0][0]), item[0][1])):
        rates.append({
            "motive": motive_id,
            "activity": list(activity),
            "n": len(values),
            "median_rate": _median(values),
            "iqr_rate": _iqr(values),
        })
    session = None
    for row in rows:
        if row.get("telemetry_session_id"):
            session = row["telemetry_session_id"]
            break
    return {
        "session": session,
        "durations": durations,
        "rates": rates,
        "coverage": {
            "ticks_by_speed": ticks_by_speed,
            "wall_ms_by_speed": wall_by_speed,
            "gaps": gaps,
            "autonomy_spans": autonomy_spans,
            "affordances": len(affordances),
        },
    }


def resolve_session(token, paths=None):
    paths = paths or Paths.from_env()
    if token == "latest":
        return telemetry.latest_session(paths=paths)
    candidate = Path(token)
    if candidate.is_file():
        return candidate
    matches = [p for p in paths.telemetry.glob("ashley_e1_*.jsonl")
               if token in p.name and p.is_file()]
    if len(matches) != 1:
        raise FileNotFoundError("session not found: %s" % token)
    return matches[0]


def report_for(session, paths=None):
    path = resolve_session(session, paths)
    found = analyze(telemetry.rows(path))
    if found["session"] is None:
        found["session"] = path.stem
    return found


def write_report(session, out_dir=None, paths=None):
    paths = paths or Paths.from_env()
    found = report_for(session, paths)
    folder = Path(out_dir) if out_dir is not None else paths.data_dir / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("calibration_%s.json" % found["session"])
    payload = json.dumps(found, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    target.write_bytes(payload)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.calibration")
    parser.add_argument("--session", required=True)
    args = parser.parse_args(argv)
    found = report_for(args.session)
    print(json.dumps(found["coverage"], sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
