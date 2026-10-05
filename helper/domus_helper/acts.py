"""8f: Ashley acts. Her options (the probe's act_menu in the game's own words) go into each
observation; her requested acts come back from Mint and go to the probe's inbox; what the
probe recorded about them (act_event rows) goes back to Mint. Nothing here chooses."""
import json
import re

OPTIONS_LIMIT = 7800
# Mint expires an act its helper never picked up after 90 s; a written act the probe never
# answers about is unknown after this long.
PROBE_REPLY_MS = 90_000
KNOWN_LIMIT = 64
EVENTS_LIMIT = 64
_PHASES = {"ACCEPTED": "accepted", "REJECTED": "rejected", "PUSHED": "pushed",
           "FINISHED": "finished", "UNKNOWN": "unknown"}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def humanize(name):
    """A tuning name in words ("bookshelf_ReadBook" -> "bookshelf Read Book"), used only
    when the game's own text for the action is not in the string index."""
    words = re.split(r"[_\-]+", name or "")
    return " ".join(_CAMEL.sub(" ", word) for word in words if word).strip()[:80] or "unnamed"


def _text(resolve, key):
    if resolve is None or key is None:
        return None
    try:
        text = resolve(key)
    except Exception:
        return None
    return text.strip()[:80] if isinstance(text, str) and text.strip() else None


def _object_name(item, resolve, catalog, people=None):
    if item.get("class") == "sim":
        # 2.17.0: a person in her menu is named as her senses name them.
        return (people or {}).get(str(item.get("object_id"))) or "someone"
    if catalog is not None and item.get("definition_id"):
        try:
            entry = catalog(item["definition_id"])
        except Exception:
            entry = None
        text = _text(resolve, (entry or {}).get("name_key")) if entry else None
        if text:
            return text
    return humanize(item.get("class") or "object")


def people_names(row):
    """{sim id: name} from a presence row: who her menu's people are."""
    names = {}
    for item in (row or {}).get("presence") or []:
        if isinstance(item, dict) and item.get("id") is not None and isinstance(item.get("name"), str):
            names[str(item["id"])] = item["name"]
    return names


def options(menu, resolve=None, catalog=None, limit=OPTIONS_LIMIT, people=None):
    """The observation's options: nearest objects first, each act with a short ref (a1, a2,
    ...) unique in this observation, its guid64 and its text. Farthest objects are left out
    until it fits the byte budget."""
    if not isinstance(menu, dict) or not isinstance(menu.get("objects"), list):
        return []
    result = []
    count = 0
    for item in menu["objects"]:
        if not isinstance(item, dict) or not isinstance(item.get("acts"), list):
            continue
        distance = item.get("distance_m")
        where = "here" if item.get("same_room") is True else "nearby"
        if isinstance(distance, (int, float)) and not isinstance(distance, bool):
            where = "%s, %.1f m" % (where, distance)
        acts = []
        for act in item["acts"]:
            if not isinstance(act, dict) or not act.get("guid64"):
                continue
            count += 1
            acts.append({"ref": "a%d" % count, "guid64": str(act["guid64"]),
                         "text": _text(resolve, act.get("text_key")) or humanize(act.get("name"))})
        if acts:
            result.append({"object": _object_name(item, resolve, catalog, people),
                           "object_id": str(item.get("object_id")), "where": where, "acts": acts})
    while result and _bytes(result) > limit:
        result.pop()
    return result


class ActCourier(object):
    """Carries her requested acts to the probe and the probe's record of them back.

    One push per act id: an id written once is never written again, across restarts
    (the spool keeps them). Events to Mint are kept until Mint answered the round trip."""

    def __init__(self, spool, publish):
        self._spool = spool
        self._publish = publish
        raw = spool.get_kv("acts_known")
        self._known = json.loads(raw) if raw else {}
        raw = spool.get_kv("acts_events")
        self._events = json.loads(raw) if raw else []

    def _save(self):
        if len(self._known) > KNOWN_LIMIT:
            for act_id in sorted(self._known, key=lambda key: self._known[key]["written_ms"])[:-KNOWN_LIMIT]:
                del self._known[act_id]
        del self._events[:-EVENTS_LIMIT]
        self._spool.put_many_kv({"acts_known": json.dumps(self._known, sort_keys=True),
                                 "acts_events": json.dumps(self._events)})

    def _event(self, act_id, phase, at_ms, detail=None):
        event = {"act_id": act_id, "phase": phase, "at_ms": int(at_ms)}
        if detail:
            event["detail"] = detail
        self._events.append(event)

    def on_row(self, row):
        """An act_event row from the probe's telemetry."""
        if not isinstance(row, dict) or row.get("event_kind") != "act_event":
            return
        e2 = row.get("e2") or {}
        act_id = e2.get("act_id")
        phase = _PHASES.get(e2.get("phase"))
        if not isinstance(act_id, str) or phase is None:
            return
        detail = {key: e2[key] for key in ("code", "detail", "tuning_name", "finishing_type", "interaction_id")
                  if isinstance(e2.get(key), str) and e2[key]}
        at = row.get("wall_timestamp_ms")
        self._event(act_id, phase, at if type(at) is int and at >= 0 else 0, detail)
        if act_id in self._known:
            self._known[act_id]["answered"] = True
        self._save()

    def tick(self, client, helper_session, now_ms, attached):
        """One round trip: send what happened, receive what to do. Returns the acts written."""
        for act_id, known in self._known.items():
            if not known.get("answered") and not known.get("timed_out") and now_ms - known["written_ms"] >= PROBE_REPLY_MS:
                known["timed_out"] = True
                self._event(act_id, "unknown", now_ms, {"code": "NO_PROBE_REPLY"})
        sending = list(self._events)
        response = client.sync_acts({"v": 1, "helper_session": helper_session, "events": sending})
        if response is None:
            self._save()
            return []
        self._events = self._events[len(sending):]
        written = []
        for act in response.get("acts") or []:
            act_id = act.get("act_id") if isinstance(act, dict) else None
            if not isinstance(act_id, str) or act_id in self._known:
                continue
            if not attached:
                self._known[act_id] = {"written_ms": now_ms, "answered": True}
                self._event(act_id, "rejected", now_ms, {"code": "NOT_ATTACHED"})
                continue
            try:
                self._publish("act", {"act_id": act_id, "object_id": str(act.get("object_id")),
                                      "guid64": str(act.get("guid64"))})
            except Exception as error:
                self._known[act_id] = {"written_ms": now_ms, "answered": True}
                self._event(act_id, "rejected", now_ms, {"code": "INBOX_" + type(error).__name__[:40]})
                continue
            self._known[act_id] = {"written_ms": now_ms}
            self._event(act_id, "received", now_ms)
            written.append(act_id)
        self._save()
        return written
