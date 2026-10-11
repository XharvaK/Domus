"""D7b: the world's memory, hers to ask.

Natalis hands an owed question on the act round trip (`memory: [{ask_id, about}]`). The helper reads the outcome
records of the attached world (every session of that world, as the diary reads them) and answers once with what the
game recorded: the acts it matched with their times, needs, moodlets, reactions and people, and the people in them
with how often and when. Nothing here says whether an act was good or bad. The search runs on its own thread, off the
bridge tick, as the pictures do.

    POST /domus/memory  {v: 1, helper_session, ask_id, facts: {matched, acts, people}}
"""
import json
import logging
import re
import threading
import time

from . import acts
from .diary import _act_line

log = logging.getLogger(__name__)

ACT_LINES_SHOWN = 12
PEOPLE_SHOWN = 6
BODY_LIMIT = 16 * 1024  # the most the answer may weigh, in bytes of its compact JSON (Natalis refuses more)
DAY_MINUTES = 1440
MAX_ID_LENGTH = 64
MAX_ABOUT_LENGTH = 80
# A send that did not reach Natalis is tried once more after this long.
RETRY_WAIT_S = 5
_WORDS = re.compile(r"[\W_]+")
# Ask ids this process has already answered. Process-local, as the pictures' ids are.
_HANDLED = set()
_LOCK = threading.Lock()


def _words(text):
    """Lower case, the words only: "Mara  Quill" and "mara-quill" are the same words."""
    return " ".join(_WORDS.split(text.casefold())).strip()


def _changes(record):
    """The relationship changes of a record that name a person."""
    changes = record.get("relationships")
    if not isinstance(changes, list):
        return []
    return [change for change in changes
            if isinstance(change, dict) and isinstance(change.get("with"), str) and change["with"]]


def _object_names(record, target):
    """The class of the act's target object, for each change to it the game recorded (none when it recorded none)."""
    objects = record.get("objects")
    if target is None or not isinstance(objects, dict):
        return []
    names = []
    for key in ("created", "destroyed", "changed"):
        events = objects.get(key)
        for event in events if isinstance(events, list) else []:
            if isinstance(event, dict) and str(event.get("object_id")) == str(target) \
                    and isinstance(event.get("class"), str):
                names.append(event["class"])
    return names


def _names(record):
    """What a record can be asked about: its tuning name and that name in words, the people in its relationship
    changes, and the class of its target object when a change to that object was recorded."""
    interaction = record.get("interaction") if isinstance(record.get("interaction"), dict) else {}
    found = []
    name = interaction.get("name")
    if isinstance(name, str) and name:
        found.extend([name, acts.humanize(name)])
    found.extend(change["with"] for change in _changes(record))
    found.extend(_object_names(record, interaction.get("target_id")))
    return found


def _matches(words, record):
    """Whole words: "cook" finds "stove_Cook" and "Cook Dinner", and "Mara Quill" finds "Mara Quill"."""
    if not words:
        return False
    for text in _names(record):
        found = _words(text)
        if found and (" %s " % words) in (" %s " % found):
            return True
    return False


def _minute(record):
    span = record.get("span")
    minute = span.get("start_minute") if isinstance(span, dict) else None
    return minute if type(minute) is int else -1


def _line(record):
    """The diary's act line, with the game day it fell on and the wall time it was recorded."""
    line = _act_line(record)
    minute = _minute(record)
    if minute >= 0:
        line["day"] = minute // DAY_MINUTES
    wall = record.get("wall_ms")
    if type(wall) is int:
        line["at_ms"] = wall
    return line


def _people(matched):
    """Each person in the matched acts: how many of them, when last, and her tracks summed over them."""
    found = {}
    for record in matched:
        wall = record.get("wall_ms") if type(record.get("wall_ms")) is int else None
        seen = set()
        for change in _changes(record):
            who = change["with"]
            person = found.setdefault(who, {"who": who, "acts": 0, "tracks": {}})
            if who not in seen:
                seen.add(who)
                person["acts"] += 1
            if wall is not None and (person.get("last_at_ms") is None or wall > person["last_at_ms"]):
                person["last_at_ms"] = wall
            tracks = change.get("tracks")
            for track, delta in (tracks.items() if isinstance(tracks, dict) else []):
                if isinstance(delta, (int, float)) and not isinstance(delta, bool):
                    person["tracks"][track] = round(person["tracks"].get(track, 0) + delta, 1)
    people = []
    for person in found.values():
        if not person["tracks"]:
            del person["tracks"]
        people.append(person)
    people.sort(key=lambda person: person.get("last_at_ms", -1), reverse=True)
    return people


def facts_for(records, about):
    """What the game recorded about `about`: the matched count, the newest acts (at most 12) and the people in the
    matched acts (at most 6). Newest first. Facts only: nothing is judged."""
    words = _words(about) if isinstance(about, str) else ""
    matched = [record for record in sorted(records, key=_minute, reverse=True) if _matches(words, record)]
    return {"matched": len(matched), "acts": [_line(record) for record in matched[:ACT_LINES_SHOWN]],
            "people": _people(matched)[:PEOPLE_SHOWN]}


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def body_for(helper_session, ask_id, facts):
    """The answer on the wire, at most BODY_LIMIT bytes. When it is too large the oldest acts go first (they are
    last, the list being newest first), then people; the matched count stays the true one."""
    body = {"v": 1, "helper_session": helper_session, "ask_id": ask_id,
            "facts": {"matched": facts["matched"], "acts": list(facts["acts"]), "people": list(facts["people"])}}
    shown = body["facts"]
    while _size(body) > BODY_LIMIT and shown["acts"]:
        shown["acts"].pop()
    while _size(body) > BODY_LIMIT and shown["people"]:
        shown["people"].pop()
    return body


def _ask(item):
    """(ask_id, about) when the item is a well-formed ask, else None."""
    if not isinstance(item, dict):
        return None
    ask_id, about = item.get("ask_id"), item.get("about")
    if not isinstance(ask_id, str) or not 0 < len(ask_id) <= MAX_ID_LENGTH:
        return None
    if not isinstance(about, str) or not 0 < len(about.strip()) <= MAX_ABOUT_LENGTH:
        return None
    return ask_id, about


def _claim_new(asks):
    if not isinstance(asks, list):
        return []
    fresh = []
    with _LOCK:
        for item in asks:
            ask = _ask(item)
            if ask is None or ask[0] in _HANDLED:
                continue
            _HANDLED.add(ask[0])
            fresh.append(ask)
    return fresh


def _answer(helper_session, ask_id, about, world, read_records):
    """The body for one ask. A read that fails answers nothing found, with no error text."""
    try:
        facts = facts_for(read_records(world), about)
    except Exception as error:
        log.warning("memory search for ask %s failed: %s", ask_id, type(error).__name__)
        facts = {"matched": 0, "acts": [], "people": []}
    return body_for(helper_session, ask_id, facts)


def _send(client, ask_id, body):
    try:
        if client.post_memory(body) is not None:
            return True
    except Exception as error:
        log.warning("memory answer %s not sent: %s", ask_id, type(error).__name__)
        return False
    log.warning("memory answer %s not sent", ask_id)
    return False


def _answer_all(asks, client, helper_session, world, read_records):
    for ask_id, about in asks:
        body = _answer(helper_session, ask_id, about, world, read_records)
        if not _send(client, ask_id, body):
            time.sleep(RETRY_WAIT_S)
            if not _send(client, ask_id, body):
                log.warning("memory answer %s not sent after a retry", ask_id)


def handle_asks_in_background(asks, client, *, helper_session, world, read_records, start=None):
    """Search and answer each new ask off the acts loop. The ids are claimed here, so a repeated sync never answers
    one twice; the search and the post run on a daemon thread, so a slow read never holds up her acts. Never raises."""
    fresh = _claim_new(asks)
    if not fresh:
        return
    run = lambda: _answer_all(fresh, client, helper_session, world, read_records)
    if start is not None:
        start(run)
        return
    threading.Thread(target=run, name="domus-memory", daemon=True).start()
