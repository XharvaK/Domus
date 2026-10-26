"""Recompute the R-AUT snapshot numbers. Stdlib plus calibration.analyze and e2_cards.validate_card.

Usage:
  python analyze.py --session session_snapshot.jsonl --decisions decisions_snapshot.jsonl --atlas PATH --tuned PATH --cards proposed_need_cards.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import types
from collections import Counter, defaultdict
from pathlib import Path

HELPER = Path(r"C:\Users\Xharv\Projects\Domus\helper")
PROBE = Path(r"C:\Users\Xharv\Projects\Domus\sims-e1\src")
for _p in (str(HELPER), str(PROBE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ashley_e1/__init__.py imports the live probe, which needs the game `services`
# module. Load the card module as a submodule of a stub package so validate_card
# is the real function and the game is not imported.
if "ashley_e1" not in sys.modules:
    _pkg = types.ModuleType("ashley_e1")
    _pkg.__path__ = [str(PROBE / "ashley_e1")]
    _pkg.__package__ = "ashley_e1"
    sys.modules["ashley_e1"] = _pkg

from ashley_e1.e2_cards import (  # noqa: E402
    MOTIVES,
    NEED_FRESH_TICKS,
    NEED_MIN_NET_DELTA,
    validate_card,
)
from domus_helper.calibration import analyze as calibration_analyze  # noqa: E402

RUNNING = ("RUNNING", "QUEUED_AND_RUNNING")
AUTONOMY = "InteractionSource.AUTONOMY"
POSTURE_SRC = "InteractionSource.POSTURE_GRAPH"
CANCEL_SRC = ("InteractionSource.BODY_CANCEL_AOP", "InteractionSource.CARRY_CANCEL_AOP")
SESSION_WALL_MIN = 1791105000000
CAL_RE = re.compile(
    r"(\d+):(\d+):(\d+)\.(\d+)\s+day:(\d+)\s+week:(\d+)"
)
LEXICON = (
    ("energy", ("sleep", "nap")),
    ("bladder", ("toilet", "pee")),
    ("hygiene", ("shower", "bath", "brush", "wash")),
    ("hunger", ("consume_food", "food", "cook", "fridge", "grab_serving", "eat")),
    ("fun", ("tv", "watch", "book", "read", "stereo", "dance", "computer", "browse", "game")),
    ("social", ("chat", "talk", "socialize")),
)
ACTIONABLE = ("hunger", "energy", "bladder", "hygiene", "fun")
EXCESS_BAR = 5.0  # motive points per game-hour above control; also the card min_net_delta


def nearest_rank(values, percent):
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return None
    rank = int(math.ceil((percent / 100.0) * count))
    rank = min(count, max(1, rank))
    return ordered[rank - 1]


def median(values):
    return nearest_rank(values, 50)


def iqr(values):
    if not values:
        return None
    return [nearest_rank(values, 25), nearest_rank(values, 75)]


def rnd(value, places=4):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return round(float(value), places)
    return value


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_calendar(text):
    if not isinstance(text, str):
        return None
    match = CAL_RE.search(text)
    if not match:
        return None
    hour, minute, second, frac, day, week = match.groups()
    frac_s = float("0." + frac)
    sod = int(hour) * 3600 + int(minute) * 60 + int(second) + frac_s
    return sod, int(day), int(week)


def unwrap_sim_seconds(presence):
    """Walk the clock. A backward jump of the time-of-day is one midnight."""
    out = {}
    prev = None
    offset = 0.0
    wraps = 0
    weeks = []
    for row in presence:
        parsed = parse_calendar((row.get("game") or {}).get("calendar"))
        if parsed is None:
            continue
        sod, day, week = parsed
        if prev is not None and sod + 1.0 < prev:
            offset += 86400.0
            wraps += 1
        prev = sod
        out[row.get("written_sequence")] = offset + sod
        weeks.append(week)
    return out, wraps, weeks


def observed(row):
    return ((row.get("interactions") or {}).get("observed")) or []


def entry_id(entry):
    return entry.get("interaction_id") or entry.get("entry_key")


def is_gap_row(row):
    return row.get("event_kind") in ("lineage_event", "session_close")


def motives_of(row):
    found = {}
    for item in row.get("motives") or []:
        if isinstance(item, dict) and item.get("id"):
            found[item["id"]] = item
    return found


def guid_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def atlas_name(text):
    if not isinstance(text, str):
        return None
    marker = "sims4.tuning.instances."
    if marker in text and text.endswith("'>"):
        return text.split(marker, 1)[1][:-2]
    if text.startswith("<class '") and text.endswith("'>"):
        return text[8:-2].split(".")[-1]
    return text


def lexicon_serves(name):
    if not name:
        return set()
    folded = name.lower().replace("-", "_")
    if "cry" in folded:
        return set()
    found = set()
    for motive, keys in LEXICON:
        for key in keys:
            if key in folded:
                found.add(motive)
                break
    return found


def load_atlas(path):
    uri = "file:" + str(Path(path).resolve()).replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        builds = conn.execute(
            "select build, count(*) from affordances group by build"
        ).fetchall()
        columns = [row[1] for row in conn.execute("pragma table_info(affordances)")]
        wanted = [
            "build", "guid64", "name", "is_super", "is_social", "target_type",
            "allow_autonomous", "allow_user_directed", "require_current_posture",
            "posture_preferences", "static_commodities_json", "ladder",
        ]
        present = [c for c in wanted if c in columns]
        rows = conn.execute(
            "select " + ", ".join(present) + " from affordances"
        ).fetchall()
    finally:
        conn.close()
    by_guid = {}
    for raw in rows:
        rec = dict(zip(present, raw))
        guid = guid_int(rec.get("guid64"))
        if guid is None:
            continue
        by_guid[guid] = rec
    return by_guid, builds, columns


def load_offered(path):
    guids = set()
    rows = 0
    keys = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows += 1
            rec = json.loads(line)
            if keys is None:
                keys = sorted(rec.keys())
            values = rec.get("affordance_guid64s")
            if values is None:
                values = rec.get("guids") or []
            for item in values or []:
                guid = guid_int(item)
                if guid is not None:
                    guids.add(guid)
    return guids, rows, keys


def truthy(value):
    return value in (1, True, "1")


def falsy(value):
    return value in (0, False, "0")


def is_picker(rec):
    name = (rec.get("name") or "")
    target = rec.get("target_type") or ""
    return ("picker" in name.lower()) or ("picker" in str(target).lower())


def is_debug_name(rec):
    name = (rec.get("name") or "").lower()
    return any(tok in name for tok in ("cheat", "debug", "testing"))


def is_posture_row(rec):
    # posture_preferences is the constant "ImmutableSlots" on every atlas row
    # in this build, so it does not mark a posture-only affordance.
    return truthy(rec.get("require_current_posture"))


def span_table(rows):
    """Same barrier rules as calibration.analyze, but keep each span."""
    gaps = 0
    previous_seq = None
    barrier = 0
    open_spans = {}
    closed = []
    presence = []
    for row in rows:
        seq = row.get("written_sequence")
        if previous_seq is not None and seq is not None and seq != previous_seq + 1:
            gaps += 1
            barrier += 1
        if is_gap_row(row):
            gaps += 1
            barrier += 1
        if isinstance(seq, int):
            previous_seq = seq
        if row.get("event_kind") != "presence_snapshot":
            continue
        presence.append((row, barrier))
        running = {}
        for entry in observed(row):
            iid = entry_id(entry)
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
                "entry": entry,
                "start": row,
                "start_barrier": barrier,
                "end": None,
                "end_barrier": None,
            }
    for span in open_spans.values():
        span["ambiguous_open"] = True
        closed.append(span)
    for span in closed:
        ambiguous = span.get("ambiguous_open") or span["start_barrier"] != span["end_barrier"]
        crossed = False
        if not ambiguous and span["end"] is not None:
            started = False
            for row, _ in presence:
                if row is span["start"]:
                    started = True
                    continue
                if not started:
                    continue
                if (row.get("game") or {}).get("paused") is True:
                    crossed = True
                if row is span["end"]:
                    break
            ambiguous = crossed
        span["ambiguous"] = bool(ambiguous)
        span["crossed_pause"] = crossed
    return presence, closed, gaps


def sim_delta(start, end, sim_seconds):
    a = sim_seconds.get(start.get("written_sequence"))
    b = sim_seconds.get(end.get("written_sequence")) if end is not None else None
    if a is None or b is None:
        return None
    return b - a


def tick_delta(start, end):
    if end is None:
        return None
    a = (start.get("game") or {}).get("ticks")
    b = (end.get("game") or {}).get("ticks")
    if not isinstance(a, int) or not isinstance(b, int):
        return None
    return b - a


def lowest_ids(motive_map, ids):
    best = None
    chosen = []
    for motive_id in ids:
        item = motive_map.get(motive_id)
        if item is None or not isinstance(item.get("value"), (int, float)):
            continue
        value = float(item["value"])
        if best is None or value < best - 1e-9:
            best = value
            chosen = [motive_id]
        elif abs(value - best) <= 1e-9:
            chosen.append(motive_id)
    return chosen, best


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--tuned", required=True)
    parser.add_argument("--cards", required=True)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.session)
    decisions = load_jsonl(args.decisions)
    atlas, builds, atlas_columns = load_atlas(args.atlas)
    offered, tuned_rows, tuned_keys = load_offered(args.tuned)
    cal = calibration_analyze(rows)

    presence, spans, gaps = span_table(rows)
    sim_seconds, wraps, weeks = unwrap_sim_seconds([row for row, _ in presence])

    session_id = None
    probe_version = None
    for row in rows:
        if session_id is None and row.get("telemetry_session_id"):
            session_id = row["telemetry_session_id"]
        if probe_version is None and row.get("probe_version"):
            probe_version = row["probe_version"]

    # --- clock coverage and speed ---
    speed_ticks = Counter()
    speed_wall_ms = Counter()
    speed_sim_s = Counter()
    speed_pairs = Counter()
    drops = []
    total_sim = None
    if presence:
        first_s = sim_seconds.get(presence[0][0].get("written_sequence"))
        last_s = sim_seconds.get(presence[-1][0].get("written_sequence"))
        if first_s is not None and last_s is not None:
            total_sim = last_s - first_s
    prev_speed = None
    for index in range(len(presence) - 1):
        left, left_b = presence[index]
        right, right_b = presence[index + 1]
        if left_b != right_b:
            continue
        lg = left.get("game") or {}
        rg = right.get("game") or {}
        if lg.get("paused") is True or rg.get("paused") is True:
            continue
        lt = lg.get("ticks")
        rt = rg.get("ticks")
        if not isinstance(lt, int) or not isinstance(rt, int):
            continue
        dt = rt - lt
        dw = right.get("wall_timestamp_ms") - left.get("wall_timestamp_ms")
        ds = None
        a = sim_seconds.get(left.get("written_sequence"))
        b = sim_seconds.get(right.get("written_sequence"))
        if a is not None and b is not None:
            ds = b - a
        speed = lg.get("clock_speed")
        if isinstance(speed, str) and dt >= 0 and isinstance(dw, int) and dw >= 0:
            speed_ticks[speed] += dt
            speed_wall_ms[speed] += dw
            speed_pairs[speed] += 1
            if ds is not None and ds >= 0:
                speed_sim_s[speed] += ds
        right_speed = rg.get("clock_speed")
        if prev_speed is None:
            prev_speed = speed
        if speed in ("SPEED3", "SUPER_SPEED3") and right_speed == "NORMAL":
            running_names = []
            for entry in observed(left):
                if entry.get("membership") in RUNNING:
                    running_names.append(atlas_name(entry.get("affordance_text")) or str(entry.get("affordance_id")))
            motive_bits = {}
            for item in left.get("motives") or []:
                motive_bits[item.get("id")] = [item.get("value"), item.get("band")]
            drops.append({
                "seq": right.get("written_sequence"),
                "from": speed,
                "to": right_speed,
                "calendar": lg.get("calendar"),
                "posture": ((left.get("body") or {}).get("posture") or {}).get("posture_name"),
                "running": sorted(set(running_names)),
                "motives": motive_bits,
            })
        prev_speed = right_speed

    ticks_per_wall_s = {}
    sim_s_per_wall_s = {}
    ticks_per_sim_s = {}
    for speed, ticks in sorted(speed_ticks.items()):
        wall_s = speed_wall_ms[speed] / 1000.0
        ticks_per_wall_s[speed] = rnd(ticks / wall_s, 3) if wall_s else None
        sim_s = speed_sim_s[speed]
        sim_s_per_wall_s[speed] = rnd(sim_s / wall_s, 3) if wall_s else None
        ticks_per_sim_s[speed] = rnd(ticks / sim_s, 4) if sim_s else None

    # --- autonomy spans ---
    by_aff = defaultdict(lambda: {
        "sim_s": [], "ticks": [], "ambiguous": 0, "open": 0,
        "targets": Counter(), "pre_motives": defaultdict(list),
        "lowest": Counter(), "lowest_actionable": Counter(),
        "match_effect": [0, 0], "match_lex": [0, 0],
        "match_actionable_effect": [0, 0], "match_actionable_lex": [0, 0],
        "replaced": 0, "short_replaced": 0, "short_idle": 0,
        "sources": Counter(), "start_seqs": [],
    })
    poor = []
    closed_auto = 0
    open_auto = 0
    ambiguous_auto = 0
    for span in spans:
        entry = span["entry"]
        if entry.get("source_raw") != AUTONOMY:
            continue
        if entry.get("membership") not in RUNNING:
            continue
        guid = guid_int(entry.get("affordance_id"))
        bucket = by_aff[guid]
        bucket["sources"][entry.get("source_raw")] += 1
        if span.get("ambiguous_open"):
            bucket["open"] += 1
            open_auto += 1
        if span["ambiguous"]:
            bucket["ambiguous"] += 1
            ambiguous_auto += 1
            continue
        closed_auto += 1
        start = span["start"]
        end = span["end"]
        ds = sim_delta(start, end, sim_seconds)
        dt = tick_delta(start, end)
        if ds is not None:
            bucket["sim_s"].append(ds)
        if dt is not None:
            bucket["ticks"].append(dt)
        bucket["targets"][entry.get("target_id")] += 1
        bucket["start_seqs"].append(start.get("written_sequence"))
        # motives on the previous presence row when it is the immediate predecessor
        pre = None
        start_index = None
        for index, (row, _) in enumerate(presence):
            if row is start:
                start_index = index
                break
        if start_index is not None and start_index > 0:
            pre = presence[start_index - 1][0]
        motive_row = pre if pre is not None else start
        mmap = motives_of(motive_row)
        for motive_id, item in mmap.items():
            if isinstance(item.get("value"), (int, float)):
                bucket["pre_motives"][motive_id].append(float(item["value"]))
        low, _low_v = lowest_ids(mmap, MOTIVES)
        low_a, _ = lowest_ids(mmap, ACTIONABLE)
        for motive_id in low:
            bucket["lowest"][motive_id] += 1
        for motive_id in low_a:
            bucket["lowest_actionable"][motive_id] += 1
        # replacement on the end row
        end_ids = set()
        for other in observed(end):
            if other.get("source_raw") == AUTONOMY and other.get("membership") in RUNNING:
                oid = entry_id(other)
                if oid is not None and oid != entry_id(entry):
                    end_ids.add(oid)
        short = ds is not None and ds < 60.0
        if end_ids:
            bucket["replaced"] += 1
        if short and end_ids:
            bucket["short_replaced"] += 1
        if short and not end_ids:
            bucket["short_idle"] += 1
        name = atlas.get(guid, {}).get("name") or atlas_name(entry.get("affordance_text"))
        # poor-choice candidates: actionable distress and this name does not serve it
        distress = []
        for motive_id in ACTIONABLE:
            item = mmap.get(motive_id)
            if item and item.get("band") == "distress":
                distress.append(motive_id)
        lex = lexicon_serves(name)
        if distress and not (set(distress) & lex) and len(poor) < 12:
            poor.append({
                "seq": start.get("written_sequence"),
                "name": name,
                "guid": guid,
                "distress": distress,
                "lexicon_serves": sorted(lex),
                "lowest_actionable": low_a,
                "values": {m: (mmap.get(m) or {}).get("value") for m in MOTIVES},
                "sim_s": rnd(ds, 1),
            })

    # --- interval rates ---
    # Activity = autonomy/script running affordances (not posture-graph, not cancel AOP).
    # Control = no such affordance on the left row.
    interval_values = defaultdict(lambda: defaultdict(lambda: {"dv": 0.0, "hours": 0.0, "n": 0, "stale": 0}))
    control = {m: {"dv": 0.0, "hours": 0.0, "n": 0, "stale": 0} for m in MOTIVES}
    overlap_hours = 0.0
    single_hours = 0.0
    control_hours = 0.0
    idle_posture = Counter()
    urgent_rows = 0
    calm_rows = 0
    calm_autonomy = 0
    calm_posture_only = 0
    calm_postures = Counter()
    band_time = {m: {"ok": 0.0, "low": 0.0, "distress": 0.0, "other": 0.0} for m in MOTIVES}
    age_all = []
    age_by = {m: [] for m in MOTIVES}
    age_over = {m: 0 for m in MOTIVES}
    age_n = {m: 0 for m in MOTIVES}
    value_range = {m: [None, None] for m in MOTIVES}
    value_changed_age = []
    value_same_age = []
    first_distress = {m: None for m in MOTIVES}
    first_low = {m: None for m in MOTIVES}
    social_values = Counter()
    running_social_affordances = set()
    used_autonomy = set()
    used_any_running = set()
    queued_only = set()

    for row, _barrier in presence:
        for entry in observed(row):
            guid = guid_int(entry.get("affordance_id"))
            if guid is None:
                continue
            if entry.get("membership") in RUNNING:
                used_any_running.add(guid)
            if entry.get("source_raw") == AUTONOMY and entry.get("membership") in RUNNING:
                used_autonomy.add(guid)
            if entry.get("source_raw") == AUTONOMY and entry.get("membership") == "QUEUED":
                queued_only.add(guid)
            rec = atlas.get(guid)
            if rec and truthy(rec.get("is_social")) and entry.get("membership") in RUNNING:
                running_social_affordances.add(guid)
        mmap = motives_of(row)
        for motive_id in MOTIVES:
            item = mmap.get(motive_id)
            if item is None:
                continue
            age_n[motive_id] += 1
            age = item.get("age_ticks")
            if isinstance(age, int):
                age_all.append(age)
                age_by[motive_id].append(age)
                if age > NEED_FRESH_TICKS:
                    age_over[motive_id] += 1
            if isinstance(item.get("value"), (int, float)):
                value = float(item["value"])
                lo, hi = value_range[motive_id]
                value_range[motive_id] = [value if lo is None else min(lo, value),
                                           value if hi is None else max(hi, value)]
            if motive_id == "social" and item.get("value") is not None:
                social_values[item.get("value")] += 1

    for index in range(len(presence) - 1):
        left, left_b = presence[index]
        right, right_b = presence[index + 1]
        if left_b != right_b:
            continue
        lg = left.get("game") or {}
        rg = right.get("game") or {}
        if lg.get("paused") is True or rg.get("paused") is True:
            continue
        a = sim_seconds.get(left.get("written_sequence"))
        b = sim_seconds.get(right.get("written_sequence"))
        if a is None or b is None or b <= a:
            continue
        hours = (b - a) / 3600.0
        actives = []
        for entry in observed(left):
            if entry.get("membership") not in RUNNING:
                continue
            if entry.get("source_raw") in (POSTURE_SRC,) + CANCEL_SRC:
                continue
            guid = guid_int(entry.get("affordance_id"))
            if guid is None:
                continue
            rec = atlas.get(guid)
            if rec is not None and falsy(rec.get("is_super")):
                continue
            actives.append(guid)
        actives = sorted(set(actives))
        left_m = motives_of(left)
        right_m = motives_of(right)
        posture = ((left.get("body") or {}).get("posture") or {}).get("posture_name")
        actionable_urgent = False
        for motive_id in ACTIONABLE:
            item = left_m.get(motive_id)
            if item and item.get("band") in ("low", "distress"):
                actionable_urgent = True
        if actionable_urgent:
            urgent_rows += 1
        else:
            calm_rows += 1
            calm_postures[posture] += 1
            if actives:
                calm_autonomy += 1
            else:
                calm_posture_only += 1
                idle_posture[posture] += 1
        for motive_id in MOTIVES:
            item = left_m.get(motive_id)
            if item is None:
                continue
            band = item.get("band")
            if band in band_time[motive_id]:
                band_time[motive_id][band] += hours
            else:
                band_time[motive_id]["other"] += hours
            seq_s = sim_seconds.get(left.get("written_sequence"))
            if item.get("band") == "low" and first_low[motive_id] is None and seq_s is not None:
                first_low[motive_id] = seq_s - sim_seconds.get(presence[0][0].get("written_sequence"), seq_s)
            if item.get("band") == "distress" and first_distress[motive_id] is None and seq_s is not None:
                origin = sim_seconds.get(presence[0][0].get("written_sequence"))
                if origin is not None:
                    first_distress[motive_id] = seq_s - origin
        if len(actives) == 0:
            control_hours += hours
            bucket_target = None
        elif len(actives) == 1:
            single_hours += hours
            bucket_target = actives[0]
        else:
            overlap_hours += hours
            bucket_target = None
        for motive_id in MOTIVES:
            before = left_m.get(motive_id)
            after = right_m.get(motive_id)
            if before is None or after is None:
                continue
            bv = before.get("value")
            av = after.get("value")
            if not isinstance(bv, (int, float)) or not isinstance(av, (int, float)):
                continue
            stale = (
                isinstance(before.get("age_ticks"), int) and before["age_ticks"] > NEED_FRESH_TICKS
            ) or (
                isinstance(after.get("age_ticks"), int) and after["age_ticks"] > NEED_FRESH_TICKS
            )
            if bv != av:
                if isinstance(after.get("age_ticks"), int):
                    value_changed_age.append(after["age_ticks"])
            else:
                if isinstance(after.get("age_ticks"), int):
                    value_same_age.append(after["age_ticks"])
            if bucket_target is None and len(actives) == 0:
                slot = control[motive_id]
            elif bucket_target is not None:
                slot = interval_values[bucket_target][motive_id]
            else:
                continue
            slot["dv"] += float(av) - float(bv)
            slot["hours"] += hours
            slot["n"] += 1
            if stale:
                slot["stale"] += 1

    def rate_of(slot):
        if slot["hours"] <= 0:
            return None
        return slot["dv"] / slot["hours"]

    control_rate = {m: rate_of(control[m]) for m in MOTIVES}

    # spans per guid (closed, non-ambiguous, any source) for the >=2 gate
    span_n = Counter()
    for span in spans:
        if span["ambiguous"]:
            continue
        guid = guid_int(span["entry"].get("affordance_id"))
        if guid is None:
            continue
        if span["entry"].get("membership") not in RUNNING:
            continue
        span_n[guid] += 1

    effect_rows = []
    proposals = []
    for guid, per_motive in sorted(interval_values.items(), key=lambda item: -sum(s["n"] for s in item[1].values())):
        if span_n[guid] < 2:
            continue
        rec = atlas.get(guid) or {}
        name = rec.get("name")
        motive_rates = {}
        for motive_id in MOTIVES:
            slot = per_motive[motive_id]
            active = rate_of(slot)
            base = control_rate[motive_id]
            excess = None if active is None or base is None else active - base
            motive_rates[motive_id] = {
                "per_game_hour": rnd(active, 3),
                "control_per_game_hour": rnd(base, 3),
                "excess_per_game_hour": rnd(excess, 3),
                "n": slot["n"],
                "hours": rnd(slot["hours"], 4),
                "stale_skipped": slot["stale"],
            }
            # Tiny windows explode per-hour rates. Require a quarter sim-hour
            # and several intervals before proposing a card.
            if excess is None or slot["n"] < 4 or slot["hours"] < 0.25:
                continue
            if abs(excess) < EXCESS_BAR:
                continue
            if motive_id not in MOTIVES:
                continue
            direction = 1 if excess > 0 else -1
            card = {
                "card_class": "need",
                "affordance_guid64": guid,
                "object_id": None,
                "signature": None,
                "motive": motive_id,
                "direction": direction,
                "min_net_delta": NEED_MIN_NET_DELTA,
            }
            validate_card(card)
            proposals.append({
                "card": card,
                "observed_net_delta_per_game_hour": rnd(active, 3),
                "control_per_game_hour": rnd(base, 3),
                "excess_per_game_hour": rnd(excess, 3),
                "n_intervals": slot["n"],
                "n_spans": span_n[guid],
                "sim_hours": rnd(slot["hours"], 4),
                "affordance_name": name,
            })
        effect_rows.append({
            "guid": guid,
            "name": name,
            "n_spans_running": span_n[guid],
            "allow_autonomous": rec.get("allow_autonomous"),
            "is_super": rec.get("is_super"),
            "motives": motive_rates,
        })

    # choice match, now that effects exist
    serves_effect = defaultdict(set)
    for item in proposals:
        if item["card"]["direction"] == 1:
            serves_effect[item["card"]["affordance_guid64"]].add(item["card"]["motive"])

    match_totals = {
        "effect_any": [0, 0],
        "lex_any": [0, 0],
        "effect_actionable": [0, 0],
        "lex_actionable": [0, 0],
        "lowest_includes_social": 0,
        "closed": 0,
    }
    for guid, bucket in by_aff.items():
        name = (atlas.get(guid) or {}).get("name")
        lex = lexicon_serves(name)
        effect = serves_effect.get(guid, set())
        # recompute from stored counters is not enough; walk was already counted into lists.
        # The per-span match was deferred. Fill from pre_motives? We did not store per-span lows
        # beyond counters. Re-walk spans for the match rates only.
        del bucket
    # second walk for match rates (uses proposal serves)
    for span in spans:
        entry = span["entry"]
        if span["ambiguous"] or entry.get("source_raw") != AUTONOMY:
            continue
        if entry.get("membership") not in RUNNING:
            continue
        match_totals["closed"] += 1
        guid = guid_int(entry.get("affordance_id"))
        name = (atlas.get(guid) or {}).get("name") or atlas_name(entry.get("affordance_text"))
        start = span["start"]
        start_index = None
        for index, (row, _) in enumerate(presence):
            if row is start:
                start_index = index
                break
        pre = presence[start_index - 1][0] if start_index else start
        mmap = motives_of(pre)
        low, _ = lowest_ids(mmap, MOTIVES)
        low_a, _ = lowest_ids(mmap, ACTIONABLE)
        if "social" in low:
            match_totals["lowest_includes_social"] += 1
        lex = lexicon_serves(name)
        effect = serves_effect.get(guid, set())
        if effect:
            match_totals["effect_any"][1] += 1
            if set(low) & effect:
                match_totals["effect_any"][0] += 1
            match_totals["effect_actionable"][1] += 1
            if set(low_a) & effect:
                match_totals["effect_actionable"][0] += 1
        if lex:
            match_totals["lex_any"][1] += 1
            if set(low) & lex:
                match_totals["lex_any"][0] += 1
            match_totals["lex_actionable"][1] += 1
            if set(low_a) & lex:
                match_totals["lex_actionable"][0] += 1

    autonomy_table = []
    for guid, bucket in sorted(by_aff.items(), key=lambda item: -len(item[1]["sim_s"])):
        rec = atlas.get(guid) or {}
        name = rec.get("name") or None
        pre = {m: rnd(median(vs), 2) for m, vs in sorted(bucket["pre_motives"].items())}
        autonomy_table.append({
            "guid": guid,
            "name": name,
            "n_closed": len(bucket["sim_s"]),
            "ambiguous": bucket["ambiguous"],
            "still_open": bucket["open"],
            "median_sim_min": rnd((median(bucket["sim_s"]) or 0) / 60.0, 3) if bucket["sim_s"] else None,
            "iqr_sim_min": (
                [rnd(bucket and (iqr(bucket["sim_s"])[0] or 0) / 60.0, 3),
                 rnd((iqr(bucket["sim_s"])[1] or 0) / 60.0, 3)]
                if bucket["sim_s"] else None
            ),
            "median_ticks": median(bucket["ticks"]),
            "iqr_ticks": iqr(bucket["ticks"]),
            "targets": bucket["targets"].most_common(3),
            "pre_motive_median": pre,
            "lowest_mode": bucket["lowest"].most_common(3),
            "lowest_actionable_mode": bucket["lowest_actionable"].most_common(3),
            "replaced": bucket["replaced"],
            "short_replaced_lt_60sim_s": bucket["short_replaced"],
            "short_then_idle_lt_60sim_s": bucket["short_idle"],
            "is_super": rec.get("is_super"),
            "allow_autonomous": rec.get("allow_autonomous"),
            "is_social": rec.get("is_social"),
        })

    # fix iqr expression — the comprehension above is messy if sim_s empty; already guarded.
    # Recompute iqr cleanly to avoid the bug with `bucket and`.
    for row_out, (guid, bucket) in zip(
        autonomy_table,
        sorted(by_aff.items(), key=lambda item: -len(item[1]["sim_s"])),
    ):
        pair = iqr(bucket["sim_s"])
        row_out["iqr_sim_min"] = None if not pair else [rnd(pair[0] / 60.0, 3), rnd(pair[1] / 60.0, 3)]

    # sleep energy
    sleep_spans = []
    for span in spans:
        if span["ambiguous"]:
            continue
        guid = guid_int(span["entry"].get("affordance_id"))
        name = (atlas.get(guid) or {}).get("name") or atlas_name(span["entry"].get("affordance_text")) or ""
        folded = name.lower()
        if "sleep" not in folded and "nap" not in folded:
            continue
        if "cry" in folded:
            continue
        start = span["start"]
        end = span["end"]
        start_index = None
        for index, (row, _) in enumerate(presence):
            if row is start:
                start_index = index
                break
        pre = presence[start_index - 1][0] if start_index else start
        e0 = (motives_of(pre).get("energy") or {}).get("value")
        e1 = (motives_of(end).get("energy") or {}).get("value")
        ds = sim_delta(start, end, sim_seconds)
        sleep_spans.append({
            "seq": start.get("written_sequence"),
            "end_seq": end.get("written_sequence"),
            "name": name,
            "source": span["entry"].get("source_raw"),
            "sim_min": rnd((ds or 0) / 60.0, 2),
            "energy_before": e0,
            "energy_after": e1,
            "speed_at_start": (start.get("game") or {}).get("clock_speed"),
            "posture": ((start.get("body") or {}).get("posture") or {}).get("posture_name"),
        })

    # coverage
    def partition(guid):
        rec = atlas.get(guid)
        if rec is None:
            return "missing_from_atlas"
        if not truthy(rec.get("allow_autonomous")):
            return "not_allow_autonomous"
        if truthy(rec.get("is_social")):
            return "social"
        if is_picker(rec):
            return "picker"
        if is_debug_name(rec):
            return "debug_or_cheat"
        if is_posture_row(rec):
            return "posture_field"
        return "other_autonomous_unused"

    never = []
    used_offered = used_autonomy & offered
    for guid in sorted(offered - used_autonomy):
        never.append(guid)
    never_counts = Counter(partition(g) for g in never)
    field_counts = Counter()
    for guid in never:
        rec = atlas.get(guid) or {}
        if not truthy(rec.get("allow_autonomous")):
            field_counts["allow_autonomous_false_or_null"] += 1
        if truthy(rec.get("is_social")):
            field_counts["is_social"] += 1
        if is_picker(rec):
            field_counts["picker"] += 1
        if is_debug_name(rec):
            field_counts["debug_or_cheat"] += 1
        if is_posture_row(rec):
            field_counts["posture_field"] += 1
        if truthy(rec.get("allow_autonomous")) and not truthy(rec.get("is_social")) and not is_picker(rec) and not is_debug_name(rec) and not is_posture_row(rec):
            field_counts["other_autonomous"] += 1

    atlas_counts = Counter()
    for rec in atlas.values():
        atlas_counts["rows"] += 1
        if truthy(rec.get("allow_autonomous")):
            atlas_counts["allow_autonomous"] += 1
        else:
            atlas_counts["not_allow_autonomous"] += 1
        if truthy(rec.get("allow_user_directed")) and not truthy(rec.get("allow_autonomous")):
            atlas_counts["user_directed_only"] += 1
        if truthy(rec.get("allow_autonomous")) and not truthy(rec.get("allow_user_directed")):
            atlas_counts["autonomous_only"] += 1
        if truthy(rec.get("allow_autonomous")) and truthy(rec.get("allow_user_directed")):
            atlas_counts["both_flags"] += 1
        if not truthy(rec.get("allow_autonomous")) and not truthy(rec.get("allow_user_directed")):
            atlas_counts["neither_flag"] += 1
        if truthy(rec.get("is_social")):
            atlas_counts["social"] += 1
        else:
            atlas_counts["not_social"] += 1
        if truthy(rec.get("is_super")):
            atlas_counts["super"] += 1

    offered_auto = 0
    offered_super = 0
    offered_social = 0
    for guid in offered:
        rec = atlas.get(guid) or {}
        if truthy(rec.get("allow_autonomous")):
            offered_auto += 1
        if truthy(rec.get("is_super")):
            offered_super += 1
        if truthy(rec.get("is_social")):
            offered_social += 1

    unused_auto_names = []
    for guid in never:
        if partition(guid) == "other_autonomous_unused":
            rec = atlas.get(guid) or {}
            unused_auto_names.append(rec.get("name"))
    unused_auto_names = sorted(n for n in unused_auto_names if n)[:40]

    # thalamus
    kept = [d for d in decisions if isinstance(d.get("wall_ms"), (int, float)) and d["wall_ms"] >= SESSION_WALL_MIN]
    dropped_dec = len(decisions) - len(kept)
    reasons = Counter((bool(d.get("fired")), d.get("reason")) for d in kept)
    theta_values = Counter(d.get("theta") for d in kept)
    key_sal = Counter()
    family_sal = Counter()
    match = mismatch = no_traces = 0
    arousals = []
    fire_walls = []
    trace_keys_on_through = Counter()
    session_trace_hits = Counter()
    for d in kept:
        traces = d.get("traces") or []
        if not traces:
            no_traces += 1
        else:
            total = 0.0
            for trace in traces:
                sal = trace.get("salience") or 0.0
                total += sal
                key = trace.get("key") or ""
                key_sal[key] += sal
                family_sal[key.split(":", 1)[0]] += sal
                if session_id and session_id in key:
                    session_trace_hits["live_session_id"] += 1
                if "b4ad0449" in key:
                    session_trace_hits["dt2b_fixture_id"] += 1
            pred = total >= d.get("theta")
            if pred == bool(d.get("fired")):
                match += 1
            else:
                mismatch += 1
        if isinstance(d.get("arousal"), (int, float)):
            arousals.append(d["arousal"])
        if d.get("fired"):
            fire_walls.append(d.get("wall_ms"))
            if d.get("reason") == "always_through":
                for trace in traces:
                    trace_keys_on_through[trace.get("key")] += 1
    # unpaused wall minutes inside telemetry
    wall0 = presence[0][0].get("wall_timestamp_ms") if presence else None
    wall1 = presence[-1][0].get("wall_timestamp_ms") if presence else None
    unpaused_ms = sum(speed_wall_ms.values())
    fires_in_window = 0
    reason_in_window = Counter()
    if wall0 is not None and wall1 is not None:
        for d in kept:
            if wall0 <= d.get("wall_ms") <= wall1 and d.get("fired"):
                fires_in_window += 1
                reason_in_window[d.get("reason")] += 1
    per_min = None
    if unpaused_ms:
        per_min = fires_in_window / (unpaused_ms / 60000.0)
    # diagnostic only: fraction of logged rows whose post-decision arousal >= candidate
    arousal_curve = {}
    sal_curve = {}
    theta = 1.0
    while theta <= 3.0001:
        label = f"{theta:.2f}"
        if arousals:
            arousal_curve[label] = rnd(sum(1 for a in arousals if a >= theta) / len(arousals), 4)
        ge_sal = 0
        sal_n = 0
        for d in kept:
            traces = d.get("traces") or []
            if not traces:
                continue
            sal_n += 1
            if sum((t.get("salience") or 0) for t in traces) >= theta:
                ge_sal += 1
        sal_curve[label] = rnd(ge_sal / sal_n, 4) if sal_n else None
        theta = round(theta + 0.25, 2)

    # events
    kinds = Counter(r.get("event_kind") for r in rows)
    commands = Counter()
    phases = Counter()
    for row in rows:
        payload = row.get("e2") or {}
        if row.get("event_kind") == "command_event":
            commands[payload.get("command")] += 1
        if row.get("event_kind") == "experiment_event":
            phases[payload.get("phase")] += 1

    speeds = Counter((r.get("game") or {}).get("clock_speed") for r in rows if r.get("event_kind") == "presence_snapshot")
    postures = Counter(
        ((r.get("body") or {}).get("posture") or {}).get("posture_name")
        for r, _ in presence
    )
    cancel_ids = set()
    for row, _ in presence:
        for entry in observed(row):
            if entry.get("source_raw") in CANCEL_SRC:
                cancel_ids.add((entry.get("source_raw"), entry_id(entry)))

    age_summary = {}
    for motive_id in MOTIVES:
        vals = age_by[motive_id]
        age_summary[motive_id] = {
            "n": age_n[motive_id],
            "median": median(vals),
            "iqr": iqr(vals),
            "p90": nearest_rank(vals, 90),
            "max": max(vals) if vals else None,
            "frac_over_2000": rnd(age_over[motive_id] / age_n[motive_id], 4) if age_n[motive_id] else None,
            "value_min": value_range[motive_id][0],
            "value_max": value_range[motive_id][1],
            "flat": (
                value_range[motive_id][0] is not None
                and abs(value_range[motive_id][1] - value_range[motive_id][0]) < 1.0
            ),
            "hours_by_band": {k: rnd(v, 3) for k, v in band_time[motive_id].items()},
            "first_low_sim_min": rnd(first_low[motive_id] / 60.0, 2) if first_low[motive_id] is not None else None,
            "first_distress_sim_min": rnd(first_distress[motive_id] / 60.0, 2) if first_distress[motive_id] is not None else None,
        }

    cal_auto = [
        item for item in cal["durations"]
        if item.get("source_raw") == AUTONOMY and (item.get("n") or item.get("ambiguous"))
    ]

    cards_out = {
        "note": "Proposals only. Not written to the atlas. min_net_delta is NEED_MIN_NET_DELTA (5 motive points above control), not the per-hour excess.",
        "control_definition": "Intervals with no RUNNING affordance whose source is outside POSTURE_GRAPH and cancel-AOP, and whose atlas is_super is not false. Rates are sum(delta value)/sum(sim hours) on every such interval. age_ticks is counted, not used as a drop filter.",
        "excess_bar_per_game_hour": EXCESS_BAR,
        "cards": proposals,
    }
    Path(args.cards).write_text(json.dumps(cards_out, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "rows": len(rows),
        "session": session_id,
        "probe_version": probe_version,
        "kinds": dict(kinds),
        "commands": dict(commands),
        "experiment_phases": dict(phases),
        "presence_rows": len(presence),
        "social_entries": sum(len(r.get("social") or []) for r in rows),
        "presence_entries": sum(len(r.get("presence") or []) for r in rows),
        "calendar_wraps": wraps,
        "week_min": min(weeks) if weeks else None,
        "week_max": max(weeks) if weeks else None,
        "sim_hours": rnd((total_sim or 0) / 3600.0, 3),
        "sim_minutes": rnd((total_sim or 0) / 60.0, 2),
        "ticks_first": (presence[0][0].get("game") or {}).get("ticks") if presence else None,
        "ticks_last": (presence[-1][0].get("game") or {}).get("ticks") if presence else None,
        "calendar_first": (presence[0][0].get("game") or {}).get("calendar") if presence else None,
        "calendar_last": (presence[-1][0].get("game") or {}).get("calendar") if presence else None,
        "wall_first": wall0,
        "wall_last": wall1,
        "unpaused_wall_min": rnd(unpaused_ms / 60000.0, 3),
        "speeds_presence": dict(speeds),
        "ticks_per_wall_s": ticks_per_wall_s,
        "sim_s_per_wall_s": sim_s_per_wall_s,
        "ticks_per_sim_s": ticks_per_sim_s,
        "speed_pairs": dict(speed_pairs),
        "drops_to_normal": drops,
        "calibration_coverage": cal["coverage"],
        "calibration_autonomy_durations": cal_auto,
        "gaps_span_walk": gaps,
        "autonomy_closed": closed_auto,
        "autonomy_ambiguous_or_open_flag": ambiguous_auto,
        "autonomy_still_open": open_auto,
        "autonomy_table": autonomy_table,
        "choice_match": match_totals,
        "poor_examples": poor,
        "cancel_interaction_ids": len(cancel_ids),
        "cancel_by_source": dict(Counter(src for src, _iid in cancel_ids)),
        "postures": postures.most_common(),
        "urgent_rows_actionable_low_or_distress": urgent_rows,
        "calm_rows": calm_rows,
        "calm_with_autonomy_si": calm_autonomy,
        "calm_posture_only": calm_posture_only,
        "calm_postures": calm_postures.most_common(),
        "idle_postures_when_no_si": idle_posture.most_common(),
        "control_hours": rnd(control_hours, 4),
        "single_si_hours": rnd(single_hours, 4),
        "overlap_si_hours": rnd(overlap_hours, 4),
        "control_rate_per_game_hour": {m: rnd(control_rate[m], 3) for m in MOTIVES},
        "control_n": {m: control[m]["n"] for m in MOTIVES},
        "control_stale_skipped": {m: control[m]["stale"] for m in MOTIVES},
        "effects": effect_rows,
        "proposal_count": len(proposals),
        "sleep_spans": sleep_spans,
        "age": age_summary,
        "age_all_median": median(age_all),
        "age_all_p90": nearest_rank(age_all, 90),
        "age_all_max": max(age_all) if age_all else None,
        "age_frac_over_2000": rnd(sum(age_over.values()) / sum(age_n.values()), 4) if sum(age_n.values()) else None,
        "age_when_value_changed_median": median(value_changed_age),
        "age_when_value_same_median": median(value_same_age),
        "social_value_counts": social_values.most_common(6),
        "running_social_affordance_guids": sorted(running_social_affordances),
        "tuned_rows": tuned_rows,
        "tuned_keys": tuned_keys,
        "offered_unique": len(offered),
        "offered_autonomous": offered_auto,
        "offered_super": offered_super,
        "offered_social": offered_social,
        "autonomy_used_guids": len(used_autonomy),
        "autonomy_used_and_offered": len(used_offered),
        "autonomy_used_not_offered": sorted(used_autonomy - offered),
        "any_running_guids": len(used_any_running),
        "queued_autonomy_guids": len(queued_only),
        "never_used_offered": len(never),
        "never_partition": dict(never_counts),
        "never_field_overlap": dict(field_counts),
        "unused_other_autonomous_names": unused_auto_names,
        "atlas_builds": builds,
        "atlas_columns": atlas_columns,
        "atlas_counts": dict(atlas_counts),
        "decisions_rows": len(decisions),
        "decisions_kept": len(kept),
        "decisions_dropped_by_wall_filter": dropped_dec,
        "decision_reasons": {str(k): v for k, v in reasons.items()},
        "decision_theta_values": {str(k): v for k, v in theta_values.items()},
        "fires_in_telemetry_window": fires_in_window,
        "fire_reasons_in_window": dict(reason_in_window),
        "fires_per_unpaused_wall_min": rnd(per_min, 4),
        "salience_sum_ge_theta_matches_fired": {"match": match, "mismatch": mismatch, "no_traces": no_traces},
        "top_trace_keys": key_sal.most_common(15),
        "trace_family_salience": family_sal.most_common(),
        "always_through_trace_keys": trace_keys_on_through.most_common(10),
        "session_id_in_traces": dict(session_trace_hits),
        "arousal_median": rnd(median(arousals), 4),
        "counterfactual": "NOT_HONEST",
        "arousal_ge_theta_row_fraction_NOT_a_fire_rate": arousal_curve,
        "salience_sum_ge_theta_row_fraction_NOT_a_fire_rate": sal_curve,
        "need_fresh_ticks": NEED_FRESH_TICKS,
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
