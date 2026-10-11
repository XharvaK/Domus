"""8f: Ashley acts. Her options (the probe's act_menu in the game's own words) go into each
observation; her requested acts come back from Mint and go to the probe's inbox; what the
probe recorded about them (act_event rows) goes back to Mint. Nothing here chooses."""
import json
import re

from . import snapshot

OPTIONS_LIMIT = 7800
# Mint expires an act its helper never picked up after 90 s; a written act the probe never
# answers about is unknown after this long.
# W3h (C9): real time. The probe reads its inbox on a real-time alarm and writes the reply then,
# not on the game clock, so 90 s means the same at slow_time 0.5.
PROBE_REPLY_MS = 90_000
# GL8: an act the probe started but never ends is unknown at once when the game detaches, and otherwise only
# after this backstop from her request. Long acts (a night's sleep, a painting) can run well past 15 real
# minutes, so the backstop is generous: it must never call a running act unknown.
ACT_CEILING_MS = 60 * 60_000
# A9-1: how long the game may be detached before an act it began is written unknown (GAME_DETACHED).
DETACH_GRACE_MS = 2 * 60_000
# A9-9: the oldest probe that understands each command the helper sends. cancel 2.20.0 (her queue), answer 2.18.0
# (her dialog answers, with the menu they come from), act 2.18.0 (the menu's acts), owner 2.24.0 (the User's act first).
PROBE_NEEDS = {"cancel": (2, 20, 0), "answer": (2, 18, 0), "act": (2, 18, 0), "owner": (2, 24, 0)}
_TERMINAL = ("finished", "rejected", "unknown")
KNOWN_LIMIT = 64
EVENTS_LIMIT = 64
ASKED_LIMIT = 8
# A dialog that opened this soon before her pushed act was first seen is not its doing.
# W3h (C9): real timestamps of the probe's own rows. At slow_time 0.5 an act stays queued longer in
# real time, so a question that opens while it waits is matched over a longer span; the slack is unchanged.
ASKED_SLACK_MS = 1_000
_PHASES = {"ACCEPTED": "accepted", "REJECTED": "rejected", "PUSHED": "pushed",
           "FINISHED": "finished", "UNKNOWN": "unknown"}
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


class RefBook(object):
    """N8 (F3): the refs of one helper session (one attachment). The first time a key is listed it gets the next
    free number; it keeps that ref in every later view, and a number is never given to another key."""

    def __init__(self):
        self._numbers = {}
        self._next = 1

    def ref(self, key):
        number = self._numbers.get(key)
        if number is None:
            number = self._numbers[key] = self._next
            self._next += 1
        return "a%d" % number


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


def act_names(menu, resolve=None):
    """HE1: a function from an act's tuning name to the game's own words. The newest menu gives each act
    its text key (the words her menu shows); the tuning name is humanized only when the menu has none."""
    keys = {}
    objects = menu.get("objects") if isinstance(menu, dict) else None
    for item in objects if isinstance(objects, list) else []:
        acts = item.get("acts") if isinstance(item, dict) else None
        for act in acts if isinstance(acts, list) else []:
            if isinstance(act, dict) and isinstance(act.get("name"), str) and act.get("text_key") is not None:
                keys.setdefault(act["name"], act["text_key"])

    def name(tuning):
        return _text(resolve, keys.get(tuning)) or humanize(tuning)
    return name


def _sentence(resolve, key):
    """Resolved sentence for a string key, at most 200 characters. Unknown is None."""
    if resolve is None or not isinstance(key, str) or not key:
        return None
    try:
        text = resolve(key)
    except Exception:
        return None
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    return text[:200]


def _object_name(item, resolve, catalog, people=None):
    if item.get("phone") is True:
        # 2.29.0: her own phone is a thing she uses; her body is never named as a person here.
        return "your phone"
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


DIALOG_PREFIX = "dialog:"
DIALOG_ROWS_SHOWN = 12
QUEUE_OBJECT_ID = "queue:her"
QUEUE_SHOWN = 6
# Posture plumbing is not something she chose or the client shows to stop.
_NOT_HERS_TO_STOP = ("InteractionSource.POSTURE_GRAPH", "InteractionSource.BODY_CANCEL_AOP")
_CLASS_REPR = re.compile(r"^<class '([^']+)'>$")


def queue_options(row, refs=None, act_name=None):
    """2.20.0 (live 2026-10-06: her meal waited behind an open-ended piano song she had no
    way to stop): what her body is doing and has queued, each one hers to stop, the way the
    client's X on her queue is. N8 (F3): refs are stable per interaction (refs is a RefBook).
    HE1: act_name gives the game's words."""
    refs = RefBook() if refs is None else refs
    acts = []
    for entry in ((row or {}).get("interactions") or {}).get("observed") or []:
        if not isinstance(entry, dict) or entry.get("source_raw") in _NOT_HERS_TO_STOP:
            continue
        iid = entry.get("interaction_id")
        membership = entry.get("membership")
        if not (isinstance(iid, str) and iid.isdigit()) or membership not in ("RUNNING", "QUEUED_AND_RUNNING", "QUEUED"):
            continue
        text = str(entry.get("affordance_text") or "")
        match = _CLASS_REPR.match(text)
        tuning = match.group(1).rsplit(".", 1)[-1] if match else text
        name = (act_name or humanize)(tuning)
        acts.append({"ref": refs.ref(("queue", iid)), "guid64": iid,
                     "text": ("Cancel (queued): %s" if membership == "QUEUED" else "Stop: %s") % name})
        if len(acts) >= QUEUE_SHOWN:
            break
    if not acts:
        return []
    return [{"object": "What you are doing", "object_id": QUEUE_OBJECT_ID, "where": "your queue", "acts": acts}]


def body_id(row):
    """Her body's sim id in a sample, or None."""
    for item in (row or {}).get("presence") or []:
        if isinstance(item, dict) and item.get("is_body") and item.get("id") is not None:
            return str(item["id"])
    return None


def dialog_is_hers(dialog, body, version=None):
    """W2h: whose window it is. The probe's cause is the answer ("hers", "user", "identity_user").
    W4 (F5): under schema 14 every window carries its cause, so a null cause is not hers. A sample from an
    older probe has no cause: the owner rule decides (no owner, or her owner)."""
    cause = dialog.get("cause")
    if cause is not None:
        return cause == "hers"
    if type(version) is int and version >= 14:
        return False
    owner = dialog.get("owner_id")
    return owner is None or body is None or str(owner) == body


def _int(value):
    return value if type(value) is int else None


def answer_rules(dialog, resolve=None):
    """W2h (wire contract 11): how she may answer a dialog that is more than one button. None for
    plain buttons. Labels are the game's own text for a field's default, resolved here; a field
    without a resolvable default is named by its field name."""
    rules = {}
    select = dialog.get("select")
    # W4 (F2): a max of 0 is no limit (the game's own meaning), so it is a rule too, as is any max above 1.
    high = _int(select.get("max")) if isinstance(select, dict) else None
    if high is not None and (high == 0 or high > 1):
        rules["select"] = {"min": _int(select.get("min")), "max": high}
    counts = dialog.get("counts")
    if isinstance(counts, dict):
        rules["counts"] = {"max_in_row": _int(counts.get("max_in_row")),
                           "max_rows": _int(counts.get("max_rows"))}
    fields = dialog.get("text_inputs")
    if isinstance(fields, list) and fields:
        text = []
        for field in fields:
            if not isinstance(field, dict) or not isinstance(field.get("name"), str):
                continue
            name = field["name"][:32]
            text.append({"name": name, "label": _text(resolve, field.get("default_key")) or name,
                         "min_length": _int(field.get("min_length")),
                         "max_length": _int(field.get("max_length")),
                         "numeric": field.get("numeric") is True,
                         "min_value": _int(field.get("min_value")),
                         "max_value": _int(field.get("max_value")),
                         "profanity_checked": field.get("profanity_checked") is True,
                         # W4 (F9): the probe's restricted-character flag; the letters, digits and space rule is the probe's.
                         "restricted": field.get("restricted") is True})
        if text:
            rules["text"] = text
    return rules or None


def dialog_options(row, resolve=None, refs=None):
    """2.18.0: the game's open dialogs that are hers, as options she answers: a picker's enabled
    rows (with price), then its buttons. W2h: a dialog with more than one selectable row, counts
    or text fields carries answer_rules, and its ok button is listed with the rows. N8 (F3): refs
    are stable per dialog row and button (refs is a RefBook)."""
    dialogs = ((row or {}).get("dialogs") or {}).get("open") or []
    body = body_id(row)
    version = (row or {}).get("schema_version")
    refs = RefBook() if refs is None else refs
    result = []
    for dialog in dialogs:
        if not isinstance(dialog, dict) or not dialog.get("dialog_id"):
            continue
        # W4 (F1): options are offered only for a window the probe holds for her; a shown or unanswerable one is not.
        if dialog.get("held") is not True or not dialog_is_hers(dialog, body, version):
            continue
        rules = answer_rules(dialog, resolve)
        acts = []
        for entry in [r for r in dialog.get("rows") or [] if isinstance(r, dict) and r.get("enabled")][:DIALOG_ROWS_SHOWN]:
            text = _text(resolve, entry.get("name_key")) or "choice %s" % entry.get("option_id")
            if isinstance(entry.get("price"), int):
                text = "%s (§%d)" % (text, entry["price"])
            acts.append({"ref": refs.ref(("dialog", str(dialog["dialog_id"]), "row", str(entry["option_id"]))),
                         "guid64": str(entry["option_id"]), "text": text})
        for response in dialog.get("responses") or []:
            name = response.get("response") if isinstance(response, dict) else None
            if not isinstance(name, str) or (acts and name == "ok" and rules is None):
                continue  # with rows, picking a row is the ok (unless her answer has rules)
            acts.append({"ref": refs.ref(("dialog", str(dialog["dialog_id"]), "response", name)), "guid64": name,
                         "text": _text(resolve, response.get("text_key")) or name})
        if acts:
            title = _text(resolve, dialog.get("title_key")) or _text(resolve, dialog.get("text_key"))
            entry = {"object": "The game asks: %s" % (title or "a question"),
                     "object_id": DIALOG_PREFIX + str(dialog["dialog_id"]),
                     "where": "asked now", "acts": acts}
            if rules is not None:
                entry["answer_rules"] = rules
            result.append(entry)
    return result


def people_names(row, seen_ids=None):
    """{sim id: name} from a presence row: who her menu's people are. SS4-v2: with seen_ids, only the
    Sims she can see are named (the rest are someone she hears, and her menu does not offer them)."""
    names = {}
    for item in (row or {}).get("presence") or []:
        if isinstance(item, dict) and item.get("id") is not None and isinstance(item.get("name"), str):
            if seen_ids is not None and str(item["id"]) not in seen_ids and item.get("is_body") is not True:
                continue
            names[str(item["id"])] = item["name"]
    return names


OPENS_SCREEN = "a screen only the User's hands can use"
# N8 (F2): interactions that open such a screen, so they are marked before the notebook has seen one end on it:
# the event planner (phone), Create a Sim (terrain, every age and sex), Change Sim, outfit planning and try-on.
# Tuning names as the game's atlas lists them; the notebook adds to this list, it never removes from it.
WITHHELD_SEED = (
    "phone_PlanEvent",
    "terrain-createsim_female-adult", "terrain-createsim_female-baby", "terrain-createsim_female-child",
    "terrain-createsim_female-elder", "terrain-createsim_female-infant", "terrain-createsim_female-teen",
    "terrain-createsim_female-toddler", "terrain-createsim_female-youngadult",
    "terrain-createsim_male-adult", "terrain-createsim_male-baby", "terrain-createsim_male-child",
    "terrain-createsim_male-elder", "terrain-createsim_male-infant", "terrain-createsim_male-teen",
    "terrain-createsim_male-toddler", "terrain-createsim_male-youngadult",
    "dresser_ChangeSim",
    "PlanOutfit", "PlanOutfit_Mirror", "tent_PlanOutfit", "vanityTable_planOutfit", "planOutfit_Styleboard",
    "planOutfit_Mirror_toddler", "planOutfit_Toddler",
    "dresser_TryOnOutfits_Start", "dresser_TryOnOutfits_End",
    "Dresser_TryOnOutfit_00", "Dresser_TryOnOutfit_01", "Dresser_TryOnOutfit_02", "Dresser_TryOnOutfit_03")
NO_WAY ="the game sees no way for her to get there from where she is now"


def _where(item, menu_room, room):
    """HE12: where an object is from her room now. The probe's same_room is about the menu's room, which
    may not be the room she is in now (the menu can be older than her last move): "here" only when that
    room is hers now, and "elsewhere" for an object in another room than hers."""
    same = item.get("same_room")
    if room is None or menu_room is None:
        return "nearby"
    if str(menu_room) == str(room):
        return "here" if same is True else ("elsewhere" if same is False else "nearby")
    return "elsewhere" if same is True else "nearby"


def options(menu, resolve=None, catalog=None, limit=OPTIONS_LIMIT, people=None, refs=None, withheld=(), room=None):
    """The observation's options: nearest objects first, each act with a short ref (a1, a2,
    ...), its guid64 and its text. N8 (F3): a ref is stable for one act on one object for the
    life of the helper session (refs is a RefBook). Farthest objects are left out
    until it fits the byte budget. W2h: an act whose interaction the notebook has seen end on a
    screen only the User's hands can use stays listed, marked with what it opens. HE12: room is
    the room she is in now (the zone's), and the menu's own room comes with the menu."""
    if not isinstance(menu, dict) or not isinstance(menu.get("objects"), list):
        return []
    refs = RefBook() if refs is None else refs
    result = []
    for item in menu["objects"]:
        if not isinstance(item, dict) or not isinstance(item.get("acts"), list):
            continue
        if item.get("class") == "sim" and people is not None and str(item.get("object_id")) not in people:
            # SS4-v2 (PR3): a person she cannot see is not offered; the menu names only seen Sims.
            continue
        distance = item.get("distance_m")
        where = _where(item, menu.get("room"), room)
        if isinstance(distance, (int, float)) and not isinstance(distance, bool):
            where = "%s, %.1f m" % (where, distance)
        if item.get("phone") is True:
            where = "with her"  # 2.29.0: her phone is on her, so no distance and no room.
        acts = []
        for act in item["acts"]:
            if not isinstance(act, dict) or not act.get("guid64"):
                continue
            listed = {"ref": refs.ref(("act", str(item.get("object_id")), str(act["guid64"]))),
                      "guid64": str(act["guid64"]),
                      "text": _text(resolve, act.get("text_key")) or humanize(act.get("name"))}
            if act.get("name") in withheld or act.get("name") in WITHHELD_SEED:
                listed["opens"] = OPENS_SCREEN
            acts.append(listed)
        if acts:
            entry = {"object": _object_name(item, resolve, catalog, people),
                     "object_id": str(item.get("object_id")), "where": where, "acts": acts}
            if item.get("reach") is False:
                # 2.25.0: the game's own connectivity check sees no way from her to it now.
                entry["noWay"] = NO_WAY
            result.append(entry)
    while result and _bytes(result) > limit:
        result.pop()
    return result


def _version(probe):
    """A probe's version as a tuple of numbers, or None when it is not one."""
    try:
        return tuple(int(part) for part in str(probe).split("."))
    except ValueError:
        return None


def _too_old(probe, need):
    """True only when the helper knows the installed probe and it predates the command."""
    have = _version(probe) if probe is not None else None
    return have is not None and have < need


def _needs(act, object_id):
    """Which probe command an act of hers is sent as (PROBE_NEEDS key)."""
    if object_id == QUEUE_OBJECT_ID:
        return "cancel"
    if object_id.startswith(DIALOG_PREFIX):
        return "answer"
    return "owner" if act.get("owner") is True else "act"


class ProbeTooOld(ValueError):
    """The installed probe predates the command this act needs (A9-9): it is refused, never sent."""


class AnswerInvalid(ValueError):
    """Her answer to a dialog is not the shape the contract allows (never its values)."""


_OPTION_ID = re.compile(r"[0-9]{1,20}")


def _answer_args(answer):
    """W2h: the extra probe arguments of her answer: rows (option id, count) and text fields. Only
    the shape is checked here; the probe checks the values against the live dialog and the held
    message. Nothing it carries is ever logged, not even in the rejection."""
    if answer is None:
        return {}
    if not isinstance(answer, dict):
        raise AnswerInvalid("answer")
    extra = {}
    rows = answer.get("rows")
    if rows:
        if type(rows) is not list or not all(
                isinstance(row, dict) and type(row.get("option_id")) is str
                and _OPTION_ID.fullmatch(row["option_id"]) and type(row.get("count")) is int and row["count"] >= 1
                for row in rows):
            raise AnswerInvalid("rows")
        extra["rows"] = [{"option_id": row["option_id"], "count": row["count"]} for row in rows]
    text = answer.get("text")
    if text:
        if type(text) is not dict or not all(type(key) is str and type(value) is str for key, value in text.items()):
            raise AnswerInvalid("text")
        extra["text"] = dict(text)
    return extra


class ActCourier(object):
    """Carries her requested acts to the probe and the probe's record of them back.

    One push per act id: an id written once is never written again, across restarts
    (the spool keeps them). Events to Mint are kept until Mint answered the round trip."""

    def __init__(self, spool, publish, resolve=None):
        self._spool = spool
        self._publish = publish
        self._resolve = resolve
        raw = spool.get_kv("acts_known")
        self._known = json.loads(raw) if raw else {}
        raw = spool.get_kv("acts_events")
        self._events = json.loads(raw) if raw else []
        # Live 2026-10-06: Cook opens the recipe question instead of entering her queue, so the
        # probe called it gone (LEFT_QUEUE) and she cooked again and again. Dialogs seen open.
        raw = spool.get_kv("acts_asked")
        self._asked = json.loads(raw) if raw else []
        # H0.5: steps of her plan Ashley still holds; while any wait, her idle is not a decision point.
        self.planned = int(spool.get_kv("acts_planned") or 0)
        # E3: the game dialogs she answered herself in this run (the overlay tells her hand from a human's).
        self.answered_dialogs = []

    def _save(self):
        if len(self._known) > KNOWN_LIMIT:
            for act_id in sorted(self._known, key=lambda key: self._known[key]["written_ms"])[:-KNOWN_LIMIT]:
                del self._known[act_id]
        del self._events[:-EVENTS_LIMIT]
        del self._asked[:-ASKED_LIMIT]
        self._spool.put_many_kv({"acts_known": json.dumps(self._known, sort_keys=True),
                                 "acts_events": json.dumps(self._events),
                                 "acts_asked": json.dumps(self._asked),
                                 "acts_planned": str(self.planned)})

    def _event(self, act_id, phase, at_ms, detail=None):
        event = {"act_id": act_id, "phase": phase, "at_ms": int(at_ms)}
        if detail:
            event["detail"] = detail
        self._events.append(event)

    def on_sample(self, row):
        """Any probe row: remember when each game dialog was first seen open."""
        dialogs = row.get("dialogs") if isinstance(row, dict) else None
        if not isinstance(dialogs, dict):
            return
        at = row.get("wall_timestamp_ms")
        seen = {item["dialog_id"] for item in self._asked}
        added = False
        for item in dialogs.get("open") or []:
            dialog_id = item.get("dialog_id") if isinstance(item, dict) else None
            if dialog_id is None or str(dialog_id) in seen or type(at) is not int:
                continue
            self._asked.append({"dialog_id": str(dialog_id), "kind": str(item.get("kind") or "a question"), "at_ms": at})
            added = True
        if added:
            self._save()

    def _asked_after(self, pushed_ms, until_ms):
        for item in self._asked:
            if pushed_ms - ASKED_SLACK_MS <= item["at_ms"] <= until_ms:
                return item
        return None

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
        if type(e2.get("started")) is bool:
            # 2.24.0: did the game ever begin the pushed act.
            detail["started"] = e2["started"]
        at = row.get("wall_timestamp_ms")
        at = at if type(at) is int and at >= 0 else 0
        known = self._known.get(act_id)
        if phase == "pushed" and known is not None:
            known["pushed_ms"] = at
        if phase == "unknown" and detail.get("code") == "LEFT_QUEUE" and known is not None and "pushed_ms" in known:
            asked = self._asked_after(known["pushed_ms"], at)
            if asked is not None:
                # It did not vanish: the game turned it into a question to her.
                phase = "finished"
                detail = {key: value for key, value in detail.items() if key in ("tuning_name", "interaction_id")}
                detail["finishing_type"] = "ASKED"
                detail["detail"] = ("it opened the game's question (%s); answering it is what queues the action"
                                    % asked["kind"])[:200]
        else:
            sentence = _sentence(self._resolve, e2.get("reason_key"))
            if sentence:
                detail["reason"] = sentence
        self._event(act_id, phase, at, detail)
        if known is not None:
            known["answered"] = True
            if phase in _TERMINAL:
                known["terminal"] = True
        self._save()

    def tick(self, client, helper_session, now_ms, attached, probe=None):
        """One round trip: send what happened, receive what to do. Returns the acts written.
        probe: the installed probe's version, when the helper knows it (A9-9 gates what it is sent)."""
        for act_id, known in self._known.items():
            if known.get("timed_out") or known.get("terminal"):
                continue
            if not known.get("answered"):
                if now_ms - known["written_ms"] >= PROBE_REPLY_MS:
                    known["timed_out"] = True
                    self._event(act_id, "unknown", now_ms, {"code": "NO_PROBE_REPLY"})
            elif not attached:
                # A9-1: a short detach (a zone load, a sleep, a stale telemetry stall) is not the end of an act
                # the game may still finish; the verdict is a guess only after DETACH_GRACE_MS.
                known.setdefault("detached_ms", now_ms)
                if now_ms - known["detached_ms"] >= DETACH_GRACE_MS:
                    known["timed_out"] = True
                    self._event(act_id, "unknown", now_ms, {"code": "GAME_DETACHED"})
            elif now_ms - known["written_ms"] >= ACT_CEILING_MS:
                # GL8: the probe began it, and no end came.
                known["timed_out"] = True
                self._event(act_id, "unknown", now_ms, {"code": "NO_END_REPORTED"})
            else:
                known.pop("detached_ms", None)
        sending = list(self._events)
        response = client.sync_acts({"v": 1, "helper_session": helper_session, "events": sending})
        if response is None:
            self._save()
            return []
        self._events = self._events[len(sending):]
        planned = response.get("planned")
        self.planned = planned if type(planned) is int and planned >= 0 else 0
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
                object_id = str(act.get("object_id"))
                # A9-9: a probe older than the command needs would ignore it (or refuse it as unknown): say so, never send it.
                if _too_old(probe, PROBE_NEEDS[_needs(act, object_id)]):
                    raise ProbeTooOld(_needs(act, object_id))
                if object_id == QUEUE_OBJECT_ID:
                    # 2.20.0: she stops one of her own actions.
                    self._publish("cancel", {"act_id": act_id, "interaction_id": str(act.get("guid64"))})
                elif object_id.startswith(DIALOG_PREFIX):
                    # 2.18.0: her answer to a game dialog (a picker row or a button). W2h: with
                    # her rows or text, the answer is the dialog's ok carrying them.
                    extra = _answer_args(act.get("answer"))
                    self._publish("answer", dict({"act_id": act_id, "dialog_id": object_id[len(DIALOG_PREFIX):],
                                                  "pick": "ok" if extra else str(act.get("guid64"))}, **extra))
                    self.answered_dialogs = (self.answered_dialogs + [object_id[len(DIALOG_PREFIX):]])[-ASKED_LIMIT:]
                else:
                    args = {"act_id": act_id, "object_id": object_id, "guid64": str(act.get("guid64"))}
                    if act.get("owner") is True:
                        # 2.24.0: her Thought said the User asked for it; the probe pushes it first.
                        args["owner"] = True
                    self._publish("act", args)
            except Exception as error:
                self._known[act_id] = {"written_ms": now_ms, "answered": True}
                code = ("ANSWER_INVALID" if isinstance(error, AnswerInvalid) else "PROBE_TOO_OLD" if isinstance(error, ProbeTooOld)
                        else "INBOX_" + type(error).__name__[:40])
                self._event(act_id, "rejected", now_ms, {"code": code})
                continue
            self._known[act_id] = {"written_ms": now_ms}
            self._event(act_id, "received", now_ms)
            written.append(act_id)
        self._save()
        # SNAPSHOT: after the acts, on its own thread, so a picture never delays one. Never raises.
        snapshot.handle_requests_in_background(response.get("snapshots") or [], client,
                                               helper_session=helper_session)
        return written
