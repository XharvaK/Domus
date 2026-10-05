"""Pure v1 observation builder. No clock and no I/O."""
import json
import re

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


def _portrait(row, resolve=None):
    """resolve: string key -> the game's own text (S0), or None when unknown."""
    row = row or {}
    needs = {}
    for item in row.get("motives") or []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        needs[str(item["id"])] = {"value": item.get("value"), "band": item.get("band")}
    posture = ((row.get("body") or {}).get("posture") or {}).get("posture_name")
    running = []
    for entry in ((row.get("interactions") or {}).get("observed")) or []:
        if not isinstance(entry, dict) or entry.get("membership") not in ("RUNNING", "QUEUED_AND_RUNNING"):
            continue
        text = entry.get("affordance_text")
        if text is None:
            continue
        running.append(_affordance_name(text))
    zone = row.get("zone") or {}
    game = row.get("game") or {}
    # DS3 (schema 6): who else is here, how she feels in game terms, who addresses her.
    company = []
    for item in row.get("presence") or []:
        if not isinstance(item, dict) or item.get("is_body") or item.get("id") is None:
            continue
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
        company.append(entry)
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
            addressed.append({"by": item.get("actor_id"),
                              "interaction": _affordance_name(text)})
    mood = row.get("mood") or {}
    portrait = {
        "needs": needs,
        "posture": posture,
        "running": running[:8],
        "zone": {"zone_id": zone.get("zone_id"), "lot_id": zone.get("lot_id"),
                 "room": zone.get("room")},
        "time": game_time(game.get("calendar")),
        "clock_speed": game.get("clock_speed"),
        "paused": game.get("paused") is True,
        "mood": mood.get("name") if isinstance(mood, dict) else None,
        "moodlets": moodlets[:8],
        "company": company[:7],
        "addressed_by": addressed[:4],
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
        portrait["place"] = {
            "her_home": place.get("her_home"), "venue": place.get("venue"),
            "household_here": None if owner is None else sorted(
                str(item.get("name")) for item in row.get("presence") or []
                if isinstance(item, dict) and not item.get("is_body")
                and item.get("household_id") == owner)}
    for item in row.get("presence") or []:
        if isinstance(item, dict) and item.get("is_body") and item.get("situations"):
            portrait["situations"] = [dict(situation) for situation in item["situations"]
                                      if isinstance(situation, dict)]
    dialogs = row.get("dialogs")
    if isinstance(dialogs, dict) and dialogs.get("open"):
        # 2.15.2: the game's pop-ups, in its words, with the choices it offers. Hers to
        # answer (the User's ruling 2026-10-05); the probe does not answer them.
        portrait["asked"] = [
            {"dialog_id": item.get("dialog_id"),
             "title": _resolve(resolve, item.get("title_key")),
             "text": _resolve(resolve, item.get("text_key")),
             "choices": [{"choice": choice.get("response"),
                          "text": _resolve(resolve, choice.get("text_key"))}
                         for choice in item.get("responses") or []
                         if isinstance(choice, dict)],
             "answers_itself": item.get("auto_respond") is True}
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
    # Shed the least essential first: running list, then moodlets, then company.
    for key in ("running", "moodlets", "company"):
        while portrait[key] and _bytes(portrait) > _PORTRAIT_LIMIT:
            portrait[key].pop()
    return portrait


def build(decision, ctx):
    row = ctx.get("row") or {}
    source = row.get("wall_timestamp_ms")
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
        "session": _text(row.get("telemetry_session_id"), "unknown"),
        "attachment": _text(ctx["helper_session"], "unknown"),
        "body": _text((row.get("body") or {}).get("sim_id"), "unknown"),
        "snapshot": _text(None if row.get("written_sequence") is None else str(row.get("written_sequence")), "unknown"),
        "seq": seq,
        "source_time_ms": source,
        "expires_at_ms": source + _WINDOW_MS,
        "lineage_class": lineage,
        "percepts": percepts,
        "portrait": _portrait(row, ctx.get("resolve_text")),
    }
