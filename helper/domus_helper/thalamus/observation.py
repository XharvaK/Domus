"""She knows who is in her room or close by; others on the lot are someone she hears."""
import json
import re

from .. import lang
from ..acts import body_id, dialog_is_hers
from ..scene import NEAR_METERS as SEEN_DISTANCE_M
from ..windows import PORTRAIT_LIMIT as WINDOWS_SHOWN

_LINEAGE = re.compile(r"[A-Z_]{1,32}")
_FACTS_LIMIT = 2048
_PORTRAIT_LIMIT = 8192
_WINDOW_MS = 600_000
# The game's Days enum (tunable_time.Days, bytecode 1.128): SUNDAY = 0 ... SATURDAY = 6,
# the same index DateAndTime.day() prints as "day:N".
_WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
_CLASS_REPR = re.compile(r"<class '([^']+)'>$")
_CALENDAR = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})(?:\.\d+)? day:(\d+) week:(\d+)")


def game_time(calendar):
    """DS3: the game clock from DateAndTime.__str__ ("HH:MM:SS.mmm day:D week:W"), or None."""
    if not isinstance(calendar, str):
        return None
    match = _CALENDAR.fullmatch(calendar.strip())
    if match is None:
        return None
    hour, minute, _, day, week = (int(part) for part in match.groups())
    if hour > 23 or minute > 59 or day > 6:
        return None
    return {"hour": hour, "minute": minute, "weekday": _WEEKDAYS[day], "day_index": day,
            "week": week}


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _text(value, fallback, limit=64):
    if value is None:
        return fallback
    text = str(value)
    if not 1 <= len(text) <= limit:
        return fallback
    return text


def _fit_strings(facts):
    fitted = dict(facts)
    while _bytes(fitted) > _FACTS_LIMIT:
        key = None
        longest = 0
        for name, value in fitted.items():
            if isinstance(value, str) and len(value) > longest:
                key = name
                longest = len(value)
        if key is None or longest == 0:
            break
        excess = _bytes(fitted) - _FACTS_LIMIT
        fitted[key] = fitted[key][:-excess] if excess < longest else ""
    return fitted


def _resolve(resolve, key):
    if resolve is None or key is None:
        return None
    try:
        text = resolve(key)
    except Exception:
        return None
    return text[:80] if isinstance(text, str) else None


def _affordance_name(text):
    """The tuning name from the probe's class repr: "<class 'sims4.tuning.instances.sim-stand'>"
    reads "sim-stand". Anything else passes through, capped."""
    if text is None:
        return None
    text = str(text)
    match = _CLASS_REPR.match(text)
    if match:
        text = match.group(1).rsplit(".", 1)[-1]
    return text[:80]


def _sim_names(row, seen_ids=None):
    """Presence id -> display name for Sims she can see, plus her own body.
    Anyone else is left out, so a sentence calls them someone. Unknown -> someone."""
    names = {}
    her = None
    for item in row.get("presence") or []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        if seen_ids is not None and not item.get("is_body") and str(item["id"]) not in seen_ids:
            continue
        raw = item.get("name")
        shown = raw if isinstance(raw, str) and raw else "someone"
        names[str(item["id"])] = shown
        if item.get("is_body") and her is None:
            her = shown
    return names, her or "someone"


def _meters(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _addressing_ids(row):
    found = set()
    for item in row.get("social") or []:
        if isinstance(item, dict) and item.get("actor_id") is not None:
            found.add(str(item["actor_id"]))
    return found


def _seen(item, zone_room, addressing):
    """Same room as her body, within the near radius, or addressing her right now."""
    room = item.get("room")
    if room is not None and zone_room is not None and room == zone_room:
        return True
    distance = _meters(item.get("distance_m"))
    if distance is not None and distance <= SEEN_DISTANCE_M:
        return True
    return str(item.get("id")) in addressing


def _named(who, names):
    if who is None:
        return "someone"
    return names.get(str(who), "someone")


def _action_actors(entry, names, her, unseen=()):
    target = entry.get("target_id")
    if target is None:
        return [her]
    key = str(target)
    if key in names:
        return [her, names[key]]
    # A Sim on the row she cannot see. An object id is not in `unseen`, so it stays out.
    if key in unseen:
        return [her, "someone"]
    return [her]


def _sentence(tuning, actors):
    """A dictionary sentence, or None. A failed lookup never fails the portrait."""
    try:
        text = lang.phrases().sentence(tuning, actors)
    except Exception:
        return None
    if not isinstance(text, str) or not text:
        return None
    return text


def _with_sentence(value, tuning, actors):
    """An addressed_by item. A sentence is added only when the dictionary has one."""
    text = _sentence(tuning, actors)
    if text is None:
        return value
    value["sentence"] = text
    return value


def _company_seen(item, resolve):
    """A Sim she can see: the same entry the portrait has always carried."""
    doing = item.get("doing")
    entry = {"id": str(item["id"]), "name": item.get("name"),
             "room": item.get("room"), "distance_m": item.get("distance_m"),
             "doing": _affordance_name(doing)}
    if item.get("on_lot") is not None:
        entry["on_lot"] = item["on_lot"]
    if item.get("situations"):
        # 2.15.2: the game situations they are in (a visit, a party) and their role.
        entry["situations"] = [dict(situation) for situation in item["situations"]
                               if isinstance(situation, dict)]
    relationship = item.get("relationship")
    if isinstance(relationship, dict):
        # S5: what the game holds between them; labels in the game's words.
        entry["relationship"] = {
            "met": relationship.get("known"),
            "tracks": {track.get("track"): track.get("value")
                       for track in relationship.get("tracks") or []
                       if isinstance(track, dict)},
            "labels": [_resolve(resolve, label.get("text_key")) or label.get("label")
                       for label in relationship.get("labels") or []
                       if isinstance(label, dict)]}
        knows = relationship.get("knows")
        if isinstance(knows, dict):
            # 2.15.0: what she has learned about them, in the game's words.
            entry["relationship"]["knows"] = {
                "traits": [_resolve(resolve, trait.get("text_key")) or trait.get("trait")
                           for trait in knows.get("traits") or []
                           if isinstance(trait, dict)],
                "careers": knows.get("careers"),
                "relationship_status": knows.get("relationship_status"),
                "romantic_preference": knows.get("romantic_preference"),
                "net_worth": knows.get("net_worth")}
        if relationship.get("sentiments"):
            entry["relationship"]["feels"] = [
                _resolve(resolve, item.get("text_key")) or item.get("sentiment")
                for item in relationship["sentiments"] if isinstance(item, dict)]
    return entry


def _company_heard(item):
    """On the lot, but not seen: a sound, not a person she can name."""
    entry = {"heard": True, "room": item.get("room"), "distance_m": item.get("distance_m")}
    if item.get("on_lot") is not None:
        entry["on_lot"] = item["on_lot"]
    return entry


def _shed_sentence(portrait):
    """Drop one sentence: her own (last first), then one addressed to her."""
    said = portrait.get("doing_said")
    if isinstance(said, list) and said:
        said.pop()
        if not said:
            del portrait["doing_said"]
        return True
    items = portrait.get("addressed_by")
    if isinstance(items, list):
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            if isinstance(item, dict) and "sentence" in item:
                del item["sentence"]
                return True
    return False


def _drop_one(items, key):
    """Company sheds a heard entry before any Sim she can see. Windows shed the oldest first.
    Other lists lose the last item."""
    if key == "company":
        for index in range(len(items) - 1, -1, -1):
            item = items[index]
            if isinstance(item, dict) and item.get("heard") is True:
                del items[index]
                return
    if key == "windows":
        del items[0]
        return
    items.pop()


def _asked_answer_rules(item, resolve):
    """W2h: the rules a question puts on her answer, under answer_rules (the shape her options
    carry, with the restricted-character flag added). Nothing when the game gave no rules."""
    rules = {}
    select = item.get("select")
    if isinstance(select, dict):
        rules["select"] = {"min": select.get("min"), "max": select.get("max")}
    counts = item.get("counts")
    if isinstance(counts, dict):
        rules["counts"] = {"max_in_row": counts.get("max_in_row"), "max_rows": counts.get("max_rows")}
    fields = item.get("text_inputs")
    if isinstance(fields, list):
        rules["text"] = [
            {"name": field["name"],
             "label": _resolve(resolve, field.get("default_key")) or field["name"],
             "min_length": field.get("min_length"), "max_length": field.get("max_length"),
             "numeric": field.get("numeric") is True,
             "min_value": field.get("min_value"), "max_value": field.get("max_value"),
             "profanity_checked": field.get("profanity_checked") is True,
             "restricted": field.get("restricted") is True}
            for field in fields if isinstance(field, dict) and isinstance(field.get("name"), str)]
    return {"answer_rules": rules} if rules else {}


def _portrait(row, resolve=None, notebook=None, windows=None):
    """resolve: string key -> the game's own text (S0), or None when unknown.
    windows: W2h, the window facts of her session (windows.WindowLog.recent)."""
    row = row or {}
    zone = row.get("zone") or {}
    addressing = _addressing_ids(row)
    zone_room = zone.get("room")
    seen_ids = set()
    unseen_ids = set()
    for item in row.get("presence") or []:
        if not isinstance(item, dict) or item.get("is_body") or item.get("id") is None:
            continue
        key = str(item["id"])
        if _seen(item, zone_room, addressing):
            seen_ids.add(key)
        else:
            unseen_ids.add(key)
    names, her = _sim_names(row, seen_ids)
    needs = {}
    for item in row.get("motives") or []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        needs[str(item["id"])] = {"value": item.get("value"), "band": item.get("band")}
    posture = ((row.get("body") or {}).get("posture") or {}).get("posture_name")
    running = []
    queued = []
    doing_said = []
    for entry in ((row.get("interactions") or {}).get("observed")) or []:
        if not isinstance(entry, dict) or entry.get("affordance_text") is None:
            continue
        tuning = _affordance_name(entry["affordance_text"])
        actors = _action_actors(entry, names, her, unseen_ids)
        if entry.get("membership") in ("RUNNING", "QUEUED_AND_RUNNING"):
            bucket, state = running, "running"
        elif entry.get("membership") == "QUEUED":
            # Live 2026-10-06: her answered recipe sat queued behind a piano song she could not see.
            bucket, state = queued, "queued"
        else:
            continue
        if len(bucket) >= 8:
            continue
        bucket.append(tuning)
        text = _sentence(tuning, actors)
        if text is not None:
            doing_said.append({"interaction": tuning, "sentence": text, "state": state})
    game = row.get("game") or {}
    # DS3 (schema 6): who else is here, how she feels in game terms, who addresses her.
    # Seen first, in row order. Heard after that, nearest first. Off the lot and unseen: gone.
    seen, heard = [], []
    for item in row.get("presence") or []:
        if not isinstance(item, dict) or item.get("is_body") or item.get("id") is None:
            continue
        if str(item["id"]) in seen_ids:
            seen.append(_company_seen(item, resolve))
        elif item.get("on_lot") is False:
            continue
        else:
            heard.append(_company_heard(item))
    heard.sort(key=lambda entry: (_meters(entry.get("distance_m")) is None,
                                  _meters(entry.get("distance_m")) or 0))
    company = (seen + heard)[:7]
    moodlets = []
    for item in row.get("sim_signals") or []:
        if not isinstance(item, dict) or item.get("kind") != "MOODLET" or item.get("visible") is False:
            continue
        moodlet = {"id": item.get("tuning_id"), "name": item.get("tuning_name"),
                   "text": _resolve(resolve, item.get("text_key")),
                   "weight": item.get("magnitude"), "mood": item.get("mood_type")}
        # S5: the game's reason ("From Eating Spoiled Food") and game minutes left.
        if item.get("reason_key") is not None:
            moodlet["reason"] = _resolve(resolve, item.get("reason_key"))
        if item.get("minutes_left") is not None:
            moodlet["minutes_left"] = item.get("minutes_left")
        moodlets.append(moodlet)
    addressed = []
    for item in row.get("social") or []:
        if isinstance(item, dict):
            text = item.get("affordance_text")
            tuning = _affordance_name(text)
            addressed.append(_with_sentence(
                {"by": item.get("actor_id"), "interaction": tuning},
                tuning, [_named(item.get("actor_id"), names), her]))
    mood = row.get("mood") or {}
    portrait = {
        "needs": needs,
        "posture": posture,
        "running": running[:8],
        "queued": queued[:8],
        **({"doing_said": doing_said} if doing_said else {}),
        "zone": {"zone_id": zone.get("zone_id"), "lot_id": zone.get("lot_id"),
                 "room": zone.get("room")},
        "time": game_time(game.get("calendar")),
        "clock_speed": game.get("clock_speed"),
        "paused": game.get("paused") is True,
        "mood": mood.get("name") if isinstance(mood, dict) else None,
        "moodlets": moodlets[:8],
        "company": company[:7],
        "addressed_by": addressed[:4],
        # W2h: what happened to windows that were or became not hers (newest last, 4 at most).
        "windows": [dict(item) for item in windows or [] if isinstance(item, dict)][-WINDOWS_SHOWN:],
    }
    if "presence" in (row.get("missingness") or {}):
        # D40: the company list missed someone this sample.
        portrait["company_complete"] = False
    if "presence_nearby" in (row.get("missingness") or {}):
        # D45: more Sims off the lot than the list holds; the lot itself is whole.
        portrait["more_nearby"] = True
    place = row.get("place")
    if isinstance(place, dict):
        # 2.15.2: whose home this is (live 2026-10-05: a guest cooking on a host's stove
        # drew reaction_Inappropriate), and who here belongs to it.
        owner = place.get("owner_household_id")
        members = [item for item in row.get("presence") or []
                   if isinstance(item, dict) and not item.get("is_body")
                   and item.get("household_id") == owner and item.get("id") is not None]
        portrait["place"] = {
            "her_home": place.get("her_home"), "venue": place.get("venue"),
            # SS4: only the members she can see are named; the others are counted.
            "household_here": None if owner is None else sorted(
                str(item.get("name")) for item in members if str(item["id"]) in seen_ids)}
        unseen_members = sum(1 for item in members if str(item["id"]) not in seen_ids)
        if owner is not None and unseen_members:
            portrait["place"]["household_heard"] = unseen_members
    for item in row.get("presence") or []:
        if isinstance(item, dict) and item.get("is_body") and item.get("situations"):
            portrait["situations"] = [dict(situation) for situation in item["situations"]
                                      if isinstance(situation, dict)]
    dialogs = row.get("dialogs")
    if isinstance(dialogs, dict) and dialogs.get("open"):
        # 2.15.2: the game's pop-ups, in its words, with the choices it offers. Hers to
        # answer (the User's ruling 2026-10-05); the probe does not answer them.
        # W2h: whether it is held for her, whose it is, and the rules her answer must meet.
        body = body_id(row)
        portrait["asked"] = [
            {"dialog_id": item.get("dialog_id"),
             "title": _resolve(resolve, item.get("title_key")),
             "text": _resolve(resolve, item.get("text_key")),
             "choices": [{"choice": choice.get("response"),
                          "text": _resolve(resolve, choice.get("text_key"))}
                         for choice in item.get("responses") or []
                         if isinstance(choice, dict)],
             "answers_itself": item.get("auto_respond") is True,
             "held": item.get("held") is True,
             "whose": "hers" if dialog_is_hers(item, body) else "the User's",
             **_asked_answer_rules(item, resolve)}
            for item in dialogs["open"] if isinstance(item, dict)]
    own = row.get("self")
    if isinstance(own, dict):
        # 2.15.0: what she is like and has, in the game's words.
        portrait["self"] = {
            "traits": None if own.get("traits") is None else
            [_resolve(resolve, item.get("text_key")) or item.get("trait")
             for item in own["traits"] if isinstance(item, dict)],
            "skills": None if own.get("skills") is None else
            [{"skill": _resolve(resolve, item.get("text_key")) or item.get("skill"),
              "level": item.get("level")} for item in own["skills"] if isinstance(item, dict)],
            "funds": own.get("funds")}
        if isinstance(own.get("careers"), list):
            # 2.19.0: her jobs, in the game's words; at_work while her shift runs.
            portrait["self"]["jobs"] = [
                {"job": _resolve(resolve, item.get("text_key")) or item.get("career"),
                 "title": _resolve(resolve, item.get("title_key")),
                 "level": item.get("level"), "at_work": item.get("at_work") is True}
                for item in own["careers"] if isinstance(item, dict)]
        if isinstance(own.get("wants"), list):
            # 2.30.0: what she wants and fears now, in the game's words.
            wants = []
            for item in own["wants"]:
                if not isinstance(item, dict):
                    continue
                want = {"want": _resolve(resolve, item.get("text_key")) or item.get("want"),
                        "fear": item.get("fear") is True}
                how = _resolve(resolve, item.get("tip_key"))
                if how:
                    want["how"] = how
                if item.get("locked") is True:
                    want["locked"] = True
                if type(item.get("of")) is int and item["of"] > 1 and type(item.get("done")) is int:
                    want["progress"] = "%d/%d" % (item["done"], item["of"])
                until = item.get("until")
                if isinstance(until, list) and len(until) == 2 and all(type(part) is int for part in until):
                    want["until"] = "%02d:%02d" % (until[0], until[1])
                wants.append(want)
            portrait["self"]["wants"] = wants
    if notebook:
        portrait["notebook"] = notebook
    # Sentences are extra: her own (doing_said, last first), then addressed_by,
    # before anything that was already in the portrait.
    # Then the least essential: the notebook, then queued, the window facts, running lists,
    # then moodlets, then company.
    while _bytes(portrait) > _PORTRAIT_LIMIT and _shed_sentence(portrait):
        pass
    if "notebook" in portrait and _bytes(portrait) > _PORTRAIT_LIMIT:
        del portrait["notebook"]
    for key in ("queued", "windows", "running", "moodlets", "company"):
        while portrait[key] and _bytes(portrait) > _PORTRAIT_LIMIT:
            _drop_one(portrait[key], key)
    return portrait


def build(decision, ctx):
    # row draws the portrait. event_row, when present, is the row this decision is about.
    row = ctx.get("row") or {}
    event = ctx.get("event_row") or row
    source = event.get("wall_timestamp_ms")
    if type(source) is not int or source < 0:
        source = 0
    lineage = ctx.get("lineage_class")
    if not isinstance(lineage, str) or _LINEAGE.fullmatch(lineage) is None:
        lineage = "PENDING"
    percepts = []
    for percept, salience in decision.percepts[:32]:
        try:
            score = float(salience)
        except (TypeError, ValueError):
            score = 0.0
        if score < 0:
            score = 0.0
        if score > 1:
            score = 1.0
        facts = dict(percept.facts)
        facts.update({
            "subject": percept.subject,
            "object": percept.object,
            "bucket": percept.bucket,
            "urgency": percept.urgency,
            "reason": decision.reason,
        })
        percepts.append({"kind": percept.kind, "salience": score, "facts": _fit_strings(facts)})
    seq = ctx["obs_seq"]
    return {
        "v": 1,
        "observation_id": "%s.%s" % (ctx["helper_session"], seq),
        "world": _text(None if ctx.get("slot_id") is None else "slot%s" % ctx.get("slot_id"), "unknown"),
        "branch": _text(ctx.get("guid"), "unknown"),
        "session": _text(event.get("telemetry_session_id"), "unknown"),
        "attachment": _text(ctx["helper_session"], "unknown"),
        "body": _text((row.get("body") or {}).get("sim_id"), "unknown"),
        "snapshot": _text(None if event.get("written_sequence") is None else str(event.get("written_sequence")), "unknown"),
        "seq": seq,
        "source_time_ms": source,
        "expires_at_ms": source + _WINDOW_MS,
        "lineage_class": lineage,
        "percepts": percepts,
        "portrait": _portrait(row, ctx.get("resolve_text"), notebook=ctx.get("notebook"),
                              windows=ctx.get("windows")),
        **({"options": ctx["options"]} if ctx.get("options") else {}),
    }
