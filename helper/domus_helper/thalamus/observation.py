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


def _portrait(row):
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
        running.append(str(text)[:80])
    zone = row.get("zone") or {}
    game = row.get("game") or {}
    # DS3 (schema 6): who else is here, how she feels in game terms, who addresses her.
    company = []
    for item in row.get("presence") or []:
        if not isinstance(item, dict) or item.get("is_body") or item.get("id") is None:
            continue
        doing = item.get("doing")
        company.append({"id": str(item["id"]), "name": item.get("name"),
                        "room": item.get("room"), "distance_m": item.get("distance_m"),
                        "doing": str(doing)[:80] if doing is not None else None})
    moodlets = []
    for item in row.get("sim_signals") or []:
        if not isinstance(item, dict) or item.get("kind") != "MOODLET" or item.get("visible") is False:
            continue
        moodlets.append({"id": item.get("tuning_id"), "name": item.get("tuning_name"),
                         "text_key": item.get("text_key"), "weight": item.get("magnitude"),
                         "mood": item.get("mood_type")})
    addressed = []
    for item in row.get("social") or []:
        if isinstance(item, dict):
            text = item.get("affordance_text")
            addressed.append({"by": item.get("actor_id"),
                              "interaction": str(text)[:80] if text is not None else None})
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
        "portrait": _portrait(row),
    }
