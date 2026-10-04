"""S6: outcome records, one per act, rebuilt from recorded telemetry.

An act is one running super interaction (posture plumbing left out), from the first
sample it runs in to the last. Each record carries its game time span, its origin
(the Owner at the controls, the body on its own, a game reaction, an experiment),
needs before and after, moodlets gained and lost, the acts that followed it, and an
experiment verdict when one is attributable. Objects and relationships stay UNKNOWN
until S5 senses them. The records are facts for her diary; nothing here judges an act.

Origins: a click is the Owner's; the game's autonomy and reactions are the body's or
the game's; an act the probe pushed is an experiment. A continuation the game runs with
user intent (SCRIPT_WITH_USER_INTENT, e.g. eating after Grab a Serving) takes the origin
of the act it continues, so an experiment's meal is never credited to the Owner.

Sleep onsets for the diary: a night's sleep on a bed (`bed_sleep`), never a nap, at
least 12 game hours after the previous onset, confirmed once it has lasted 30 game
minutes (a pushed sleep cancelled at once is not a night).
Design: _Internal/papers/DOMUS_LIVED_WORLD_DESIGN_v0.2.md §7.1-7.2.

    python -m domus_helper.outcomes             # the latest session, summarised
    python -m domus_helper.outcomes --all --write
"""
import argparse
import gzip
import json
import re
from pathlib import Path

from .paths import Paths
from .thalamus.observation import _affordance_name, game_time

OUTCOME_VERSION = 1
LIVE = ("RUNNING", "QUEUED_AND_RUNNING")
CONTINUATION = "InteractionSource.SCRIPT_WITH_USER_INTENT"
_ORIGINS = {
    "InteractionSource.PIE_MENU": "owner",
    CONTINUATION: "user_intent",
    "InteractionSource.AUTONOMY": "body",
    "InteractionSource.BODY_CANCEL_AOP": "body",
    "InteractionSource.SCRIPT": "game_reaction",
    "InteractionSource.REACTION": "game_reaction",
}
SLEEP = re.compile(r"^bed_sleep$", re.I)
NAP = re.compile(r"nap", re.I)
DIARY_SPACING_MIN = 12 * 60
SLEEP_CONFIRM_MIN = 30
FOLLOW_WINDOW_MIN = 30
MAX_FOLLOWED = 4
# Two samples further apart than this (real seconds) are a break in recording; acts
# open across it close at the last sample before it.
GAP_MS = 30_000
_SESSION = re.compile(r"ashley_e1_([0-9a-f-]{36})\.jsonl(?:\.(\d+))?(?:\.gz)?\Z")


def game_minute(calendar):
    """Absolute game minutes from the calendar string, or None."""
    time = game_time(calendar)
    if time is None:
        return None
    return (time["week"] * 7 + time["day_index"]) * 1440 + time["hour"] * 60 + time["minute"]


def _origin(source):
    return _ORIGINS.get(source, "game")


def _sample(row):
    motives = {}
    for item in row.get("motives") or []:
        if isinstance(item, dict) and isinstance(item.get("value"), (int, float)) \
                and not isinstance(item.get("value"), bool):
            motives[str(item.get("id"))] = item["value"]
    moodlets = None
    if (row.get("schema_version") or 0) >= 6 and isinstance(row.get("sim_signals"), list):
        moodlets = {}
        for item in row["sim_signals"]:
            if isinstance(item, dict) and item.get("kind") == "MOODLET" and item.get("tuning_id"):
                moodlets[str(item["tuning_id"])] = {
                    "id": str(item["tuning_id"]), "name": item.get("tuning_name"),
                    "text_key": item.get("text_key"), "visible": item.get("visible")}
    company = None
    if (row.get("schema_version") or 0) >= 6 and isinstance(row.get("presence"), list):
        company = sorted({str(item.get("name") or item.get("id")) for item in row["presence"]
                          if isinstance(item, dict) and not item.get("is_body")})
    return {"wall_ms": row.get("wall_timestamp_ms"),
            "calendar": (row.get("game") or {}).get("calendar"),
            "minute": game_minute((row.get("game") or {}).get("calendar")),
            "motives": motives, "moodlets": moodlets, "company": company}


def _live_acts(row):
    found = {}
    for entry in (row.get("interactions") or {}).get("observed") or []:
        if not isinstance(entry, dict) or entry.get("membership") not in LIVE:
            continue
        source = entry.get("source_raw")
        if source == "InteractionSource.POSTURE_GRAPH" or entry.get("interaction_id") is None:
            continue
        found[str(entry["interaction_id"])] = entry
    return found


def _moodlet_diff(before, after):
    if before is None or after is None:
        return None
    return {"gained": [after[key] for key in sorted(after) if key not in before],
            "lost": [before[key] for key in sorted(before) if key not in after]}


def _needs(before, after):
    keys = sorted(set(before) & set(after))
    return {"before": {key: before[key] for key in keys},
            "after": {key: after[key] for key in keys},
            "delta": {key: round(after[key] - before[key], 1) for key in keys
                      if round(after[key] - before[key], 1) != 0}}


def _experiments(rows):
    """interaction_id -> {experiment_id, verdict, code} from experiment events."""
    by_interaction, verdicts = {}, {}
    for row in rows:
        if row.get("event_kind") != "experiment_event":
            continue
        e2 = row.get("e2") or {}
        if e2.get("interaction_id") and e2.get("experiment_id"):
            by_interaction.setdefault(str(e2["interaction_id"]), e2["experiment_id"])
        if e2.get("phase") == "VERDICT" and e2.get("experiment_id"):
            verdicts[e2["experiment_id"]] = e2.get("code")
    return {interaction: {"experiment_id": experiment, "verdict": verdicts.get(experiment)}
            for interaction, experiment in by_interaction.items()}


def acts(rows, session=None):
    """Outcome records for one session's rows, in start order. Deterministic."""
    rows = list(rows)
    experiments = _experiments(rows)
    samples, live = [], []
    for row in rows:
        if row.get("event_kind") != "presence_snapshot":
            continue
        samples.append(_sample(row))
        live.append(_live_acts(row))
    spans = {}   # interaction_id -> [first index, last index, entry]
    closed = []
    for index, current in enumerate(live):
        gap = index > 0 and _gap(samples[index - 1], samples[index])
        for key in list(spans):
            if gap or key not in current:
                closed.append(spans.pop(key))
        for key, entry in current.items():
            if key in spans:
                spans[key][1] = index
            else:
                spans[key] = [index, index, entry]
    closed.extend(spans.values())
    records = []
    for first, last, entry in closed:
        before = samples[first - 1] if first > 0 and not _gap(samples[first - 1], samples[first]) \
            else samples[first]
        after = samples[last + 1] if last + 1 < len(samples) and \
            not _gap(samples[last], samples[last + 1]) else samples[last]
        key = str(entry["interaction_id"])
        start, end = samples[first]["minute"], samples[last]["minute"]
        record = {
            "kind": "outcome", "v": OUTCOME_VERSION,
            "act_id": "%s:%s:%d" % ((session or "session")[:8], key, first),
            "session": session,
            "interaction": {"name": _affordance_name(entry.get("affordance_text")),
                            "guid64": entry.get("affordance_id"),
                            "target_id": entry.get("target_id")},
            "origin": "experiment" if key in experiments else _origin(entry.get("source_raw")),
            "source_raw": entry.get("source_raw"),
            "span": {"start": samples[first]["calendar"], "end": samples[last]["calendar"],
                     "start_minute": start, "end_minute": end,
                     "game_minutes": None if start is None or end is None else end - start,
                     "samples": last - first + 1},
            "needs": _needs(before["motives"], after["motives"]),
            "moodlets": _moodlet_diff(before["moodlets"], after["moodlets"]),
            "company": samples[first]["company"],
            "experiment": experiments.get(key),
            "followed_by": [],
            "unknown": ["objects", "relationships"],  # S5
            "_order": (first, last),
        }
        records.append(record)
    records.sort(key=lambda item: (item["_order"][0], item["act_id"]))
    _link_followers(records)
    _resolve_continuations(records)
    for record in records:
        del record["_order"]
    return records


def _resolve_continuations(records):
    by_id = {record["act_id"]: record for record in records}
    for record in records:
        if record["source_raw"] != CONTINUATION or record["origin"] == "experiment":
            continue
        for earlier in reversed(records[:records.index(record)]):
            if earlier["origin"] not in ("owner", "experiment"):
                continue
            if any(item["act_id"] == record["act_id"] for item in earlier["followed_by"]):
                record["origin"] = earlier["origin"]
                record["continues"] = earlier["act_id"]
                break
    for record in records:
        for item in record["followed_by"]:
            item["origin"] = by_id[item["act_id"]]["origin"]


def _gap(a, b):
    if type(a["wall_ms"]) is not int or type(b["wall_ms"]) is not int:
        return False
    return b["wall_ms"] - a["wall_ms"] > GAP_MS


def _link_followers(records):
    """Acts that began while this one ran or within FOLLOW_WINDOW_MIN after it ended."""
    for record in records:
        first, last = record["_order"]
        end = record["span"]["end_minute"]
        for other in records:
            if other is record or other["_order"][0] <= first:
                continue
            start = other["span"]["start_minute"]
            if other["_order"][0] > last + 1 and (end is None or start is None or
                                                  start - end > FOLLOW_WINDOW_MIN):
                continue
            record["followed_by"].append({
                "act_id": other["act_id"], "name": other["interaction"]["name"],
                "origin": other["origin"],
                "after_minutes": None if end is None or start is None else start - end})
            if len(record["followed_by"]) >= MAX_FOLLOWED:
                break


def is_night_sleep(record):
    name = record["interaction"]["name"] or ""
    return bool(SLEEP.match(name)) and not NAP.search(name)


def sleep_onsets(records, last_onset_minute=None):
    """Records that start a night's sleep: a bed sleep, never a nap, at least
    DIARY_SPACING_MIN game minutes after the previous onset."""
    found = []
    previous = last_onset_minute
    for record in records:
        start = record["span"]["start_minute"]
        if not is_night_sleep(record) or start is None:
            continue
        if (record["span"]["game_minutes"] or 0) < SLEEP_CONFIRM_MIN:
            continue
        if previous is not None and start - previous < DIARY_SPACING_MIN:
            continue
        found.append(record)
        previous = start
    return found


def day_frames(records):
    """Per game day: when she slept and woke, who was around, and what the body did
    on its own (the game's autonomy or reactions)."""
    days = {}
    for record in records:
        start = record["span"]["start_minute"]
        if start is None:
            continue
        day = days.setdefault(start // 1440, {"day": start // 1440, "acts": 0, "slept": [],
                                               "woke": [], "company": set(), "body_on_its_own": {}})
        day["acts"] += 1
        if is_night_sleep(record):
            day["slept"].append(record["span"]["start"])
            day["woke"].append(record["span"]["end"])
        day["company"].update(record.get("company") or [])
        if record["origin"] in ("body", "game_reaction"):
            name = record["interaction"]["name"]
            day["body_on_its_own"][name] = day["body_on_its_own"].get(name, 0) + 1
    frames = []
    for key in sorted(days):
        frame = days[key]
        frame["company"] = sorted(frame["company"])
        frames.append(frame)
    return frames


def _open(path):
    path = Path(path)
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def read_rows(files):
    for path in files:
        with _open(path) as handle:
            for raw in handle:
                if not raw.endswith(b"\n"):
                    break
                try:
                    yield json.loads(raw)
                except ValueError:
                    continue


def sessions(paths):
    """session id -> ordered segment files, live and archived (S0 telemetry archive)."""
    found = {}
    places = [paths.telemetry, paths.data_dir / "telemetry-archive"]
    for place in places:
        if not place.is_dir():
            continue
        for path in place.rglob("ashley_e1_*"):
            match = _SESSION.match(path.name)
            if match is None or path.name.endswith(".partial"):
                continue
            found.setdefault(match.group(1), {})[int(match.group(2) or 0)] = path
    return {session: [segments[index] for index in sorted(segments)]
            for session, segments in found.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--session")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    found = sessions(paths)
    if args.session:
        chosen = {key: value for key, value in found.items() if key.startswith(args.session)}
    elif args.all:
        chosen = found
    else:
        latest = max(found, key=lambda key: found[key][-1].stat().st_mtime) if found else None
        chosen = {latest: found[latest]} if latest else {}
    total = sleeps = 0
    for session in sorted(chosen):
        records = acts(read_rows(chosen[session]), session)
        onsets = sleep_onsets(records)
        total += len(records)
        sleeps += len(onsets)
        if args.write:
            target = paths.data_dir / "outcomes" / ("%s.jsonl" % session)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        print("%s acts=%d sleep_onsets=%s" % (session[:8], len(records),
                                              [record["span"]["start"] for record in onsets]))
    print("total acts=%d sleep onsets=%d sessions=%d" % (total, sleeps, len(chosen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
