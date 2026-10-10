"""S6: outcome records, one per act, rebuilt from recorded telemetry.

An act is one running super interaction (posture plumbing left out), from the first
sample it runs in to the last. A social (a mixer: Chat About Property Values, Flirt) is
an act of its own with its own origin, even though the game only shows it queued inside
the chat that holds it; the chat lists the socials it held (`socials`), each social
names its chat (`part_of`). Each record carries its game time span, its origin
(the Owner at the controls, the body on its own, a game reaction, an experiment),
needs before and after, moodlets gained and lost, the acts that followed it, and an
experiment verdict when one is attributable. Objects, relationships and her self (skills,
money, traits) stay UNKNOWN in rows that did not sense them. A relationship change says
whether that Sim was the act's target, reacted to her during it, or was a bystander
(whose drift the act did not cause). `reactions` names who reacted while the act ran and
how, in the game's words (2.15.1, live: cooking on a host's stove drew
reaction_Inappropriate and then a send-away). The records are facts for her diary;
nothing here judges an act.

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
import contextlib
import gzip
import json
import re
import zipfile
from pathlib import Path

from .paths import Paths
from .scene import seen_here
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
# Standing idle is the absence of an act, not one ("nothing followed" is a fact).
IDLE = frozenset(("sim-stand", "stand_Passive"))
MIXER = re.compile(r"^mixer_", re.I)
# A Sim's own reaction, as the game names it: reaction_Inappropriate,
# nonTouching_Reaction_InappropriateBehavior_SendAway.
REACTION = re.compile(r"(^|_)reaction_", re.I)
MAX_SELF_SKILLS = 12
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


def company_names(row):
    """PR19 / SS4-v2: the Sims she can see (never her body), by name. Heard and off-lot Sims are not kept."""
    presence = [item for item in (row or {}).get("presence") or [] if isinstance(item, dict)]
    body = next((item for item in presence if item.get("is_body")), None)
    return sorted({str(item.get("name") or item.get("id")) for item in presence
                   if not item.get("is_body") and seen_here(item, body)})


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
    relationships = None
    if (row.get("schema_version") or 0) >= 6 and isinstance(row.get("presence"), list):
        company = company_names(row)
    if (row.get("schema_version") or 0) >= 7 and isinstance(row.get("presence"), list):
        relationships = {}
        for item in row["presence"]:
            relationship = item.get("relationship") if isinstance(item, dict) else None
            if isinstance(relationship, dict):
                knows = relationship.get("knows")
                knows = knows if isinstance(knows, dict) else None
                relationships[str(item.get("id"))] = {
                    "name": str(item.get("name") or item.get("id")),
                    "tracks": {t.get("track"): t.get("value")
                               for t in relationship.get("tracks") or []},
                    "labels": sorted(l.get("label") for l in relationship.get("labels") or []),
                    # 2.15.0 (schema 8): what she knows about them, how she feels.
                    "known_traits": None if knows is None else
                    sorted(t.get("trait") for t in knows.get("traits") or []),
                    "careers": None if knows is None else knows.get("careers"),
                    "sentiments": None if "sentiments" not in relationship else
                    sorted(s.get("sentiment") for s in relationship.get("sentiments") or [])}
    reacting = None
    if (row.get("schema_version") or 0) >= 6 and isinstance(row.get("presence"), list):
        reacting = {}
        for item in row["presence"]:
            if not isinstance(item, dict) or item.get("is_body"):
                continue
            doing = _affordance_name(item.get("doing"))
            if doing and REACTION.search(doing):
                reacting[str(item.get("id"))] = {
                    "by": str(item.get("name") or item.get("id")), "reaction": doing}
    objects = row.get("objects") if (row.get("schema_version") or 0) >= 7 else None
    own = None
    if (row.get("schema_version") or 0) >= 8 and isinstance(row.get("self"), dict):
        value = row["self"]
        own = {"funds": value.get("funds"),
               "skills": None if value.get("skills") is None else
               {item["skill"]: item["level"] for item in value["skills"]},
               "traits": None if value.get("traits") is None else
               sorted(item["trait"] for item in value["traits"])}
    return {"wall_ms": row.get("wall_timestamp_ms"),
            "calendar": (row.get("game") or {}).get("calendar"),
            "minute": game_minute((row.get("game") or {}).get("calendar")),
            "motives": motives, "moodlets": moodlets, "company": company,
            "relationships": relationships, "reacting": reacting,
            "objects": objects if isinstance(objects, dict) else None,
            "self": own}


def _live_acts(row):
    found = {}
    for entry in (row.get("interactions") or {}).get("observed") or []:
        if not isinstance(entry, dict):
            continue
        # Socials (mixers) show only queued inside the chat that runs them. A reaction
        # the game queues on her (2.15.1, live: a host's send-away) may never run
        # before she is moved on, and still happened to her.
        name = _affordance_name(entry.get("affordance_text")) or ""
        if entry.get("membership") not in LIVE and \
                not MIXER.match(name) and not REACTION.search(name):
            continue
        source = entry.get("source_raw")
        if source == "InteractionSource.POSTURE_GRAPH" or entry.get("interaction_id") is None:
            continue
        if _affordance_name(entry.get("affordance_text")) in IDLE:
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


def _added(before, after):
    if before is None or after is None:
        return []
    return sorted(set(after) - set(before))


def _reactions(samples):
    """2.15.1: each Sim that reacted while the act ran, and how, in first-seen order."""
    found = []
    for sample in samples:
        for key, item in sorted((sample.get("reacting") or {}).items()):
            entry = dict(item, id=key)
            if entry not in found:
                found.append(entry)
    return found


def _relationship_changes(before, after, target_id=None, reactors=()):
    """S5: track changes and labels gained or lost with each Sim seen at both ends.
    role: "target" when the act was aimed at that Sim, "reactor" when that Sim reacted
    to her while it ran (2.15.1, live: cooking at a host's home is aimed at the stove,
    and the host's reaction cost her 12 points), else "bystander" (live 2026-10-05: a
    Sim playing on the computer drifted +0.1 during her chat, and a passer-by's
    conversation track faded, and both read as the chat's doing).
    2.15.0: traits and a career she learned, sentiments gained or lost."""
    if before is None or after is None:
        return None
    changes = []
    for key in sorted(set(before) & set(after), key=lambda k: (after[k]["name"], k)):
        a, b = before[key], after[key]
        deltas = {track: round(b["tracks"][track] - a["tracks"][track], 1)
                  for track in sorted(set(a["tracks"]) & set(b["tracks"]))
                  if a["tracks"][track] is not None and b["tracks"][track] is not None
                  and round(b["tracks"][track] - a["tracks"][track], 1) != 0}
        gained = sorted(set(b["labels"]) - set(a["labels"]))
        lost = sorted(set(a["labels"]) - set(b["labels"]))
        learned = _added(a.get("known_traits"), b.get("known_traits"))
        career = a.get("careers") is None and b.get("careers") is not None
        felt = _added(a.get("sentiments"), b.get("sentiments"))
        faded = _added(b.get("sentiments"), a.get("sentiments"))
        if deltas or gained or lost or learned or career or felt or faded:
            change = {"with": b["name"],
                      "role": "target" if target_id is not None and key == str(target_id)
                      else "reactor" if key in reactors else "bystander",
                      "tracks": deltas, "labels_gained": gained, "labels_lost": lost}
            if learned:
                change["learned_traits"] = learned
            if career:
                change["learned_career"] = b["careers"]
            if felt or faded:
                change["sentiments_gained"], change["sentiments_lost"] = felt, faded
            changes.append(change)
    return changes


def _self_changes(before, after):
    """2.15.0: what the act did to her: money, skill levels, traits. None unsensed."""
    if before is None or after is None:
        return None
    found = {}
    if type(before["funds"]) is int and type(after["funds"]) is int and \
            after["funds"] != before["funds"]:
        found["funds"] = after["funds"] - before["funds"]
    a, b = before["skills"], after["skills"]
    if a is not None and b is not None:
        ups = {skill: b[skill] - a[skill] for skill in sorted(set(a) & set(b))
               if b[skill] != a[skill]}
        if ups:
            found["skills"] = ups
        # A skill new to a full list may only have climbed into it.
        if len(a) < MAX_SELF_SKILLS:
            new = sorted(set(b) - set(a))
            if new:
                found["skills_new"] = {skill: b[skill] for skill in new}
    gained = _added(before["traits"], after["traits"])
    lost = _added(after["traits"], before["traits"])
    if gained:
        found["traits_gained"] = gained
    if lost:
        found["traits_lost"] = lost
    return found


def _object_changes(samples):
    """S5: object events reported by the samples of an act (after its first one).
    None when any sample is unsensed or starts a new baseline."""
    found = {"created": [], "destroyed": [], "changed": [], "truncated": False}
    for sample in samples:
        events = sample["objects"]
        if events is None or events.get("baseline"):
            return None
        for key in ("created", "destroyed", "changed"):
            found[key].extend(events.get(key) or [])
        found["truncated"] = found["truncated"] or bool(events.get("truncated"))
    return found


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
        after_index = last + 1 if last + 1 < len(samples) and \
            not _gap(samples[last], samples[last + 1]) else last
        key = str(entry["interaction_id"])
        # When the next sample already holds an act that began as this one ended
        # (Grab a Serving -> eating), that sample's change belongs to the next act:
        # this act is measured to its own last sample.
        shared = any(other not in live[last]
                     for other in (live[last + 1] if last + 1 < len(live) else {}))
        if shared:
            after_index = last
        after = samples[after_index]
        reactions = _reactions(samples[first:after_index + 1])
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
            "needs": dict(_needs(before["motives"], after["motives"]),
                          measured_to="own_last_sample" if shared else "next_sample"),
            "moodlets": _moodlet_diff(before["moodlets"], after["moodlets"]),
            "company": samples[first]["company"],
            "relationships": _relationship_changes(before["relationships"],
                                                   after["relationships"],
                                                   entry.get("target_id"),
                                                   {item["id"] for item in reactions}),
            "reactions": reactions,
            "self": _self_changes(before["self"], after["self"]),
            # Events each sample reports happened since the one before it.
            "objects": None if samples[first]["objects"] is None else
            _object_changes(samples[first + 1:after_index + 1]),
            "experiment": experiments.get(key),
            "followed_by": [],
            "_order": (first, last),
        }
        # Anything not sensed in these rows (schema 6 and older) stays UNKNOWN.
        record["unknown"] = [name for name in ("objects", "relationships", "self")
                             if record[name] is None]
        if MIXER.match(record["interaction"]["name"] or ""):
            record["social"] = True
        records.append(record)
    records.sort(key=lambda item: (item["_order"][0], item["act_id"]))
    _nest_socials(records)
    _link_followers(records)
    _resolve_continuations(records)
    for record in records:
        del record["_order"]
    return records


def _answered_by(answer, auto_respond):
    """Who closed a pop-up. Until she can answer herself (E4), a chosen answer on a
    dialog the game would not answer by itself came from the User at the controls
    (the User's ruling 2026-10-05: hers to answer, the User only as a fallback)."""
    if answer in (None, "closed", "no_response"):
        return "none"
    return "owner_or_game" if auto_respond else "owner"


def questions(rows, session=None, after_samples=5):
    """2.15.2: one record per pop-up the game showed (schema 9 `dialogs`): what it
    asked (string keys), the choices it offered, when it was asked and closed, the
    answer the game stored, who answered, and what changed for her in the samples
    after (traits gained or lost, skills, money, moodlets)."""
    samples, opened, records = [], {}, []
    for row in rows:
        if row.get("event_kind") != "presence_snapshot":
            continue
        samples.append(_sample(row))
        index = len(samples) - 1
        dialogs = row.get("dialogs") if (row.get("schema_version") or 0) >= 9 else None
        if not isinstance(dialogs, dict):
            continue
        for item in dialogs.get("open") or []:
            if not isinstance(item, dict) or item.get("dialog_id") is None:
                continue
            seen = opened.setdefault(item["dialog_id"], {"first": index, "entry": item})
            seen["last"], seen["entry"] = index, item
        for item in dialogs.get("closed") or []:
            if not isinstance(item, dict):
                continue
            seen = opened.pop(item.get("dialog_id"), None)
            entry = (seen or {}).get("entry") or item
            records.append({"_first": (seen or {}).get("first", index), "_closed": index,
                            "entry": entry, "answer": item.get("response")})
    for key, seen in opened.items():
        records.append({"_first": seen["first"], "_closed": None, "entry": seen["entry"],
                        "answer": None})
    built = []
    for item in records:
        entry, closed = item["entry"], item["_closed"]
        record = {
            "kind": "question", "v": OUTCOME_VERSION,
            "question_id": "%s:dialog:%s" % ((session or "session")[:8], entry["dialog_id"]),
            "session": session,
            "dialog": {"kind": entry.get("kind"), "title_key": entry.get("title_key"),
                       "text_key": entry.get("text_key"), "owner_id": entry.get("owner_id")},
            "choices": entry.get("responses") or [],
            "asked": samples[item["_first"]]["calendar"],
            "closed": None if closed is None else samples[closed]["calendar"],
            "answer": item["answer"],
            "answered_by": None if closed is None else
            _answered_by(item["answer"], entry.get("auto_respond") is True)}
        if closed is not None:
            before = samples[max(closed - 1, 0)]
            after = samples[min(closed + after_samples, len(samples) - 1)]
            record["changed"] = {"self": _self_changes(before["self"], after["self"]),
                                 "moodlets": _moodlet_diff(before["moodlets"],
                                                           after["moodlets"])}
        built.append(record)
    built.sort(key=lambda record: record["question_id"])
    return built


def _nest_socials(records):
    """A social runs inside the chat aimed at the same Sim that is running then."""
    for social in records:
        if not social.get("social"):
            continue
        first = social["_order"][0]
        for chat in records:
            if chat.get("social") or chat is social:
                continue
            if chat["_order"][0] <= first <= chat["_order"][1] and \
                    chat["interaction"]["target_id"] == social["interaction"]["target_id"]:
                social["part_of"] = chat["act_id"]
                chat.setdefault("socials", []).append(
                    {"act_id": social["act_id"], "name": social["interaction"]["name"],
                     "origin": social["origin"]})
                break


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
            if other.get("part_of") == record["act_id"]:
                continue  # its own socials are listed under socials
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


class _ZipMember(object):
    """A session segment kept in a weekly zip (telemetry_archive.weekly)."""

    def __init__(self, bundle, member):
        self.bundle, self.member = Path(bundle), member
        self.name = member.rsplit("/", 1)[-1]

    def stat(self):
        return self.bundle.stat()

    @contextlib.contextmanager
    def open(self):
        with zipfile.ZipFile(self.bundle) as archive, archive.open(self.member) as raw, \
                gzip.GzipFile(fileobj=raw) as handle:
            yield handle


def _open(path):
    if isinstance(path, _ZipMember):
        return path.open()
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
    """session id -> ordered segment files: live, archived, and in weekly zips."""
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
    weekly = paths.data_dir / "telemetry-archive" / "weekly"
    for bundle in sorted(weekly.glob("*.zip")) if weekly.is_dir() else ():
        with zipfile.ZipFile(bundle) as archive:
            members = archive.namelist()
        for member in members:
            match = _SESSION.match(member.rsplit("/", 1)[-1])
            if match is not None:
                found.setdefault(match.group(1), {}).setdefault(
                    int(match.group(2) or 0), _ZipMember(bundle, member))
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
        asked = questions(read_rows(chosen[session]), session)
        onsets = sleep_onsets(records)
        total += len(records)
        sleeps += len(onsets)
        if args.write:
            target = paths.data_dir / "outcomes" / ("%s.jsonl" % session)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as handle:
                for record in records + asked:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        print("%s acts=%d sleep_onsets=%s" % (session[:8], len(records),
                                              [record["span"]["start"] for record in onsets]))
    print("total acts=%d sleep onsets=%d sessions=%d" % (total, sleeps, len(chosen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
