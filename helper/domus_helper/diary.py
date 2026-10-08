"""User ruling: a daily Sims diary, written while she sleeps. The helper already turns telemetry into S6 outcome records
(`domus_helper/outcomes.py`: `acts`, `sleep_onsets`, `day_frames`, `sessions`, `read_rows`). When her body starts a
night's sleep, the helper sends Ashley the day it recorded, once, as a compact `day` object on one observation with a
`sleep_onset` percept. The helper never writes what the day meant; it only lists what happened.
Covers the current play session up to the onset (v1); earlier sessions of the same day are not re-read.
"""
import json

from . import outcomes
from .thalamus.observation import _affordance_name

CHECK_EVERY_MS = 120_000
DAY_LIMIT = 12_288
NEED_MIN = 5
KV_LAST = "diary_last_onset"
KV_PENDING = "diary_pending"


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def asleep(row):
    """True when a presence row shows a night sleep that is not only queued."""
    if not isinstance(row, dict):
        return False
    interactions = row.get("interactions")
    observed = interactions.get("observed") if isinstance(interactions, dict) else None
    if not isinstance(observed, list):
        return False
    for entry in observed:
        if not isinstance(entry, dict) or entry.get("membership") == "QUEUED":
            continue
        name = _affordance_name(entry.get("affordance_text"))
        if outcomes.is_night_sleep({"interaction": {"name": name}}):
            return True
    return False


def _gained_names(record):
    moodlets = record.get("moodlets") or {}
    gained = moodlets.get("gained") if isinstance(moodlets, dict) else None
    names = []
    for item in gained or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(item["name"])
        elif isinstance(item, str) and item:
            names.append(item)
    return names


def _reaction_names(record):
    names = []
    for item in record.get("reactions") or []:
        if isinstance(item, dict):
            name = item.get("reaction") or item.get("name")
        elif isinstance(item, str):
            name = item
        else:
            name = None
        if name and name not in names:
            names.append(name)
    return names


def _people(record):
    people = []
    for change in record.get("relationships") or []:
        if not isinstance(change, dict):
            continue
        role = change.get("role")
        if role not in ("target", "reactor"):
            continue
        who = change.get("sim") or change.get("with") or change.get("name")
        if not who:
            continue
        person = {"who": who, "role": role}
        tracks = change.get("tracks")
        if tracks:
            person["tracks"] = tracks
        people.append(person)
    return people


def _kept(record, seen):
    name = (record.get("interaction") or {}).get("name")
    if _gained_names(record) or _reaction_names(record) or _people(record):
        return True
    return name not in seen


def _act_line(record):
    span = record.get("span") or {}
    interaction = record.get("interaction") or {}
    line = {"act_id": record.get("act_id"), "at": span.get("start"),
            "minutes": span.get("game_minutes"), "what": interaction.get("name"),
            "by": record.get("origin")}
    delta = (record.get("needs") or {}).get("delta") if isinstance(record.get("needs"), dict) else None
    needs = {}
    if isinstance(delta, dict):
        for stat, value in delta.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) >= NEED_MIN:
                needs[stat] = value
    if needs:
        line["needs"] = needs
    moodlets = _gained_names(record)
    if moodlets:
        line["moodlets"] = moodlets
    reactions = _reaction_names(record)
    if reactions:
        line["reactions"] = reactions
    people = _people(record)
    if people:
        line["people"] = people
    return {key: value for key, value in line.items() if value not in (None, "", [], {})}


def day_digest(records, from_minute, to_minute):
    """Facts for one window: frames, kept acts, and counts of the rest."""
    chosen = []
    for record in records or []:
        span = record.get("span") if isinstance(record, dict) else None
        start = span.get("start_minute") if isinstance(span, dict) else None
        if start is None or start > to_minute:
            continue
        if from_minute is not None and not from_minute < start:
            continue
        chosen.append(record)
    chosen.sort(key=lambda record: (record["span"]["start_minute"], record.get("act_id") or ""))
    acts = []
    also = {}
    seen = set()
    for record in chosen:
        name = (record.get("interaction") or {}).get("name")
        if _kept(record, seen):
            acts.append(_act_line(record))
        else:
            also[name] = also.get(name, 0) + 1
        if name is not None:
            seen.add(name)
    omitted = 0
    digest = {"v": 1, "from_minute": from_minute, "to_minute": to_minute,
              "frames": outcomes.day_frames(chosen), "acts": acts, "also": also, "omitted": omitted}
    while len(_compact(digest)) > DAY_LIMIT and digest["acts"]:
        dropped = digest["acts"].pop(0)
        name = dropped.get("what")
        digest["also"][name] = digest["also"].get(name, 0) + 1
        omitted += 1
        digest["omitted"] = omitted
    return digest


class DiaryWatch:
    def __init__(self, spool, paths, read_records=None):
        self.spool = spool
        self.paths = paths
        self.read_records = read_records or (
            lambda session: outcomes.acts(
                outcomes.read_rows(outcomes.sessions(paths).get(session, [])), session))
        self._checked_ms = None
        self._sleeping = False

    def _json_kv(self, key):
        raw = self.spool.get_kv(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def tick(self, now_ms, row, world):
        if not isinstance(row, dict) or row.get("event_kind") != "presence_snapshot":
            return None
        if asleep(row):
            # HE9: the onset is confirmed only once the sleep has run 30 game minutes, and the game can
            # reach that between two rows of one wall-clock throttle window; the check stays open.
            self._sleeping = True
            if self._checked_ms is not None and now_ms - self._checked_ms < CHECK_EVERY_MS:
                return None
        elif self._sleeping:
            # HE9: the first row after the sleep checks at once, not on the throttle.
            self._sleeping = False
        else:
            return None
        self._checked_ms = now_ms
        session = row.get("telemetry_session_id")
        try:
            records = self.read_records(session)
        except (OSError, ValueError, KeyError):
            return None
        last_map = self._json_kv(KV_LAST)
        if not isinstance(last_map, dict):
            last_map = {}
        last = last_map.get(world)
        onsets = outcomes.sleep_onsets(records, last)
        if not onsets:
            return None
        onset = onsets[-1]
        start = onset["span"]["start_minute"]
        pending = {"world": world, "onset_minute": start,
                   "day": day_digest(records, last, start)}
        last_map[world] = start
        self.spool.put_kv(KV_PENDING, json.dumps(pending, ensure_ascii=False, separators=(",", ":")))
        self.spool.put_kv(KV_LAST, json.dumps(last_map, ensure_ascii=False, separators=(",", ":")))
        return pending

    def pending(self):
        value = self._json_kv(KV_PENDING)
        return value if isinstance(value, dict) else None

    def clear(self):
        self.spool.put_kv(KV_PENDING, "")
