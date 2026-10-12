"""8f: Ashley acts. Her options (the probe's act_menu in the game's own words) go into each
observation; her requested acts come back from Mint and go to the probe's inbox; what the
probe recorded about them (act_event rows) goes back to Mint. Nothing here chooses."""
import json
import re
import threading

from . import snapshot
from .transport import SyncRefused

# N8 (F4): the options of one view: at most 160 objects and 32,768 bytes (contract.py takes the same).
OPTIONS_LIMIT = 32768
OPTIONS_OBJECTS_LIMIT = 160
# N8 (F4): an object within this many metres of her is near, as one in her room is.
NEAR_M = 4.0
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
# W12 (F5): a pie-menu choice (variant) and a numbered response need 2.39.0; every command is gated the same way.
PROBE_NEEDS = {"cancel": (2, 20, 0), "answer": (2, 18, 0), "act": (2, 18, 0), "owner": (2, 24, 0),
               "variant": (2, 39, 0), "response": (2, 39, 0),
               # W13 (D4, D5, D9): the verb acts (each its own probe command) and a Sim picked for a phone act.
               "go": (2, 40, 0), "save": (2, 40, 0), "event": (2, 40, 0), "buy": (2, 40, 0), "place": (2, 40, 0),
               "move": (2, 40, 0), "sell": (2, 40, 0), "sim": (2, 40, 0)}
# W13 (H): the verb acts Natalis may send (SyncAct.verb); each is the probe command of the same name.
VERBS = ("go", "save", "event", "buy", "place", "move", "sell")
# W13 (H): a verb act's args are the probe command's args, as Natalis wrote them; this bounds what is forwarded.
VERB_ARGS_BYTES = 4096
# W13 (H): the most characters of a result's words the sync event carries (the contract's detail.result).
RESULT_WORDS_MAX = 400
# W13 (H): a sync event's whole detail is under this many bytes of JSON (Natalis's limit).
DETAIL_BYTES = 1024
_TERMINAL = ("finished", "rejected", "unknown")
KNOWN_LIMIT = 64
EVENTS_LIMIT = 64
ASKED_LIMIT = 8
# A dialog that opened this soon before her pushed act was first seen is not its doing.
# W3h (C9): real timestamps of the probe's own rows. At slow_time 0.5 an act stays queued longer in
# real time, so a question that opens while it waits is matched over a longer span; the slack is unchanged.
ASKED_SLACK_MS = 1_000
_PHASES = {"ACCEPTED": "accepted", "REJECTED": "rejected", "PUSHED": "pushed",
           "FINISHED": "finished", "UNKNOWN": "unknown",
           # W12 (A1): a pushed act waits behind an open window (not finished, not gone); a screen withheld (not terminal).
           "WAITING": "waiting", "NOTED": "noted"}
# W12 (B4): Mint takes at most this many events in one sync; the rest wait for the next tick.
EVENTS_PER_SYNC = 64
QUARANTINE_LIMIT = 32
# W12 (S2): her words to a Sim, as the request carries them (1 to 240 characters).
WORDS_MAX = 240
_WINDOW = re.compile(r"\bdialog (\d{1,20})\b")
_GUID_VARIANT = re.compile(r"([0-9]{1,20})(?:v([0-9]{1,3}))?")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


class MenuParts(object):
    """N8 (F4): the probe writes a menu in parts, one act_menu row each, with the same menu_rev and each part's
    index of the count. take() returns the whole menu once all of its parts have come, else None. A row without
    parts (an older probe) is a whole menu. A menu whose parts are not all in is never shown part-way."""

    def __init__(self):
        self._key = None
        self._pieces = {}

    def take(self, session, e2):
        parts = e2.get("parts") if type(e2.get("parts")) is int else 1
        part = e2.get("part") if type(e2.get("part")) is int else 0
        if not 1 <= parts <= 64 or not 0 <= part < parts:
            return None
        key = (session, e2.get("menu_rev"))
        if key != self._key:
            self._key, self._pieces = key, {}
        self._pieces[part] = e2
        if len(self._pieces) < parts:
            return None
        objects = []
        for index in range(parts):
            objects.extend(self._pieces[index].get("objects") or [])
        # W12 (C8, C11): the facts the probe writes with part 0 (what the object cap left out, the spot counters)
        # belong to the whole menu, whichever part came last.
        head = self._pieces[0]
        self._key, self._pieces = None, {}
        return dict(e2, objects=objects, part=0, parts=1, dropped=head.get("dropped"),
                    spot_stages=head.get("spot_stages"))


class RefBook(object):
    """N8 (F3): the refs of one helper session (one attachment). The first time a key is listed it gets the next
    free number; it keeps that ref in every later view, and a number is never given to another key.
    W13 (H): one letter per kind of name, each numbered on its own from 1: a (a game act), p (a person she knows),
    h (a place she can go), t (a thing of hers), e (an event type), c (a catalogue item). No two kinds share a letter.
    The book is shared by the view and the lists, so a thread may ask for a ref while the tick does: a lock keeps
    each number given once."""

    def __init__(self):
        self._numbers = {}
        self._next = {}
        self._lock = threading.Lock()

    def ref(self, key, prefix="a"):
        with self._lock:
            number = self._numbers.get((prefix, key))
            if number is None:
                number = self._next.get(prefix, 1)
                self._numbers[(prefix, key)] = number
                self._next[prefix] = number + 1
        return "%s%d" % (prefix, number)


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def humanize(name):
    """A tuning name in words ("bookshelf_ReadBook" -> "bookshelf Read Book"), used only
    when the game's own text for the action is not in the string index."""
    words = re.split(r"[_\-]+", name or "")
    return " ".join(_CAMEL.sub(" ", word) for word in words if word).strip()[:80] or "unnamed"


_TOKEN = re.compile(r"\{([^{}]*)\}")


def clean_text(text, person=None):
    """N8 (F10): a game sentence with its string tokens resolved, never with braces. A token that names the
    target (index 1 or more) is filled with the person's name when the target is a person (a first-name field
    gets the first name, a last-name field the last name, anything else the full name); every other token is
    dropped. Then the spaces are tidied. None when nothing is left."""
    def fill(match):
        index, _dot, field = match.group(1).partition(".")
        if not person or index == "0" or not index.isdigit():
            return ""
        if "FirstName" in field:
            return person.split()[0]
        if "LastName" in field:
            return person.split()[-1]
        return person
    text = _TOKEN.sub(fill, text).replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text or None


def _text(resolve, key, person=None):
    if resolve is None or key is None:
        return None
    try:
        text = resolve(key)
    except Exception:
        return None
    if not isinstance(text, str):
        return None
    cleaned = clean_text(text, person)
    return cleaned[:80] if cleaned else None


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


def act_words_by_guid(menu, resolve=None):
    """W13 (S1): each act of the newest menu by its guid64, in the game's words (a phone notice names the act it is about).
    An act with no guid64 or no name is left out."""
    words = {}
    objects = menu.get("objects") if isinstance(menu, dict) else None
    for item in objects if isinstance(objects, list) else []:
        acts_of = item.get("acts") if isinstance(item, dict) else None
        for act in acts_of if isinstance(acts_of, list) else []:
            if not isinstance(act, dict) or act.get("guid64") in (None, "") or not isinstance(act.get("name"), str):
                continue
            text = _text(resolve, act.get("text_key")) or humanize(act["name"])
            if text:
                words.setdefault(str(act["guid64"]), text[:64])
    return words


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
    text = clean_text(text)
    return text[:200] if text else None


def _person_name(item, people):
    """N8 (F10): the name of the person an act is on, when the object is a person she can name, else None."""
    if item.get("class") != "sim":
        return None
    return (people or {}).get(str(item.get("object_id")))


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
# W12 (A7): the probe keeps 40 rows of a picker; the helper shows them all and says "N of M" when it shows fewer.
DIALOG_ROWS_SHOWN = 40
# W12 (C2, C9): room 0 is the outside of the house. It is never "near" by its room, and it is named "outside".
OUTSIDE_ROOM = "0"
OUTSIDE_NAME = "outside"
OUTSIDE_WHERE = "outside"
OUTSIDE_ON_LOT_WHERE = "outside, on your lot"
OUTSIDE_OFF_LOT_WHERE = "outside, off your lot"
OFF_LOT_WHERE = "off your lot"
REFUSALS_SHOWN = 8
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
        enabled = [r for r in dialog.get("rows") or [] if isinstance(r, dict) and r.get("enabled")]
        shown = enabled[:DIALOG_ROWS_SHOWN]
        for entry in shown:
            text = _text(resolve, entry.get("name_key")) or "choice %s" % entry.get("option_id")
            if isinstance(entry.get("price"), int):
                text = "%s (§%d)" % (text, entry["price"])
            acts.append({"ref": refs.ref(("dialog", str(dialog["dialog_id"]), "row", str(entry["option_id"]))),
                         "guid64": str(entry["option_id"]), "text": text})
        for response in dialog.get("responses") or []:
            name = response.get("response") if isinstance(response, dict) else None
            if not isinstance(name, str) or (acts and name == "ok" and rules is None):
                continue  # with rows, picking a row is the ok (unless her answer has rules)
            # W12: a custom button the probe names response_<N> reads as choice N, never a bare name or number.
            custom = name[len("response_"):] if name.startswith("response_") and name[len("response_"):].isdigit() else None
            words = _text(resolve, response.get("text_key")) or ("choice %s" % custom if custom else name)
            acts.append({"ref": refs.ref(("dialog", str(dialog["dialog_id"]), "response", name)), "guid64": name,
                         "text": words})
        if acts:
            title = _text(resolve, dialog.get("title_key")) or _text(resolve, dialog.get("text_key"))
            where = "asked now" if len(shown) == len(enabled) else "asked now, %d of %d choices" % (len(shown), len(enabled))
            entry = {"object": "The game asks: %s" % (title or "a question"),
                     "object_id": DIALOG_PREFIX + str(dialog["dialog_id"]),
                     "where": where, "acts": acts}
            if rules is not None:
                entry["answer_rules"] = rules
            # W12 (hold_left_s): the whole seconds until the window's fallback hands it to the User.
            held_for = dialog.get("hold_left_s")
            if type(held_for) is int and held_for >= 0:
                entry["hold_left_s"] = held_for
            result.append(entry)
    return result


def people_names(row, seen_ids=None):
    """{sim id: name} from a presence row: who her menu's people are. SS4-v2: with seen_ids, only the
    Sims she can see are named. 2.38.0 (W11 H2): a Sim she hears on her lot (on the lot, not seen) is named too;
    a Sim off her lot that she does not see is not."""
    names = {}
    for item in (row or {}).get("presence") or []:
        if isinstance(item, dict) and item.get("id") is not None and isinstance(item.get("name"), str):
            if (seen_ids is not None and str(item["id"]) not in seen_ids and item.get("is_body") is not True
                    and item.get("on_lot") is not True):
                continue
            names[str(item["id"])] = item["name"]
    return names


def people_heard(row, seen_ids):
    """2.38.0 (W11 H2): the ids of the Sims she hears on her lot and does not see: on the lot (on_lot True) and not
    in the seen list. Empty until the seen list is known, so nothing is called heard before it is."""
    heard = set()
    if seen_ids is None:
        return heard
    for item in (row or {}).get("presence") or []:
        if (isinstance(item, dict) and item.get("id") is not None and item.get("is_body") is not True
                and item.get("on_lot") is True and str(item["id"]) not in seen_ids):
            heard.add(str(item["id"]))
    return heard


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


def _is_outside(item):
    """W12 (C2, C9): an object in room 0 is outside the house."""
    return item.get("room") is not None and str(item.get("room")) == OUTSIDE_ROOM


def _in_her_room(item, room):
    """N8 (F4): whether an object is in the room she is in now. The probe's room id for the object decides
    when both are known; an older menu without one is judged by the probe's same_room flag.
    W12 (C2): outside is no room: an outdoor object is not near her by its room, nor is one indoors when she is out."""
    object_room = item.get("room")
    if _is_outside(item) or (room is not None and str(room) == OUTSIDE_ROOM):
        return False
    if object_room is not None and room is not None:
        return str(object_room) == str(room)
    return item.get("same_room") is True


def _refusals(item, resolve, near):
    """W12 (C4): the acts the game refused on an object near her, in the game's own words: "<act>: refused: <reason>".
    Only near objects carry them (the probe sends them for those alone); at most REFUSALS_SHOWN."""
    if near is not True or not isinstance(item.get("refusals"), list):
        return []
    found = []
    for refusal in item["refusals"]:
        if not isinstance(refusal, dict):
            continue
        act = _text(resolve, refusal.get("text_key")) or humanize("act")
        reason = _sentence(resolve, refusal.get("reason_key")) or "no reason given"
        found.append(("%s: refused: %s" % (act, reason))[:240])
        if len(found) >= REFUSALS_SHOWN:
            break
    return found


def _near(item, room):
    distance = item.get("distance_m")
    close = isinstance(distance, (int, float)) and not isinstance(distance, bool) and distance <= NEAR_M
    return item.get("phone") is True or close or _in_her_room(item, room)


def _room_label(item, room_labels):
    """N8 (F4): the room's label when it is known; None when it is not (the object then names no room).
    W12 (C9): the outside of the house is named outside, whatever the notebook says."""
    object_room = item.get("room")
    if object_room is None:
        return None
    if str(object_room) == OUTSIDE_ROOM:
        return OUTSIDE_NAME
    return (room_labels or {}).get(str(object_room))


# 2.35.0 (D3): a spot is a place she can go to. Its act is Go here, whatever the probe names the game's act.
SPOT_ACT_TEXT = "Go here"
SPOT_OUTSIDE = "outside"
SPOT_FRONT_DOOR = "the front door, outside"


def _spot_name(item, label):
    """2.35.0 (D3): a spot is named by its place: the front door, outside; else the room's label when it is known;
    else outside for room 0; else a room upstairs or a room, by level."""
    if item.get("spot") == "front_door":
        return SPOT_FRONT_DOOR
    if label:
        return label[:64]
    if str(item.get("room")) == "0":
        return SPOT_OUTSIDE
    level = item.get("level")
    upstairs = isinstance(level, int) and not isinstance(level, bool) and level > 0
    return "a room upstairs" if upstairs else "a room"


# 2.38.0 (W11 H2): where a Sim she hears on her lot says so (the distance follows it, as for any object).
HEARD_WHERE = "heard, not seen"
# 2.38.0 (W11 H1): how a folded entry says how many objects it stands for, and in how many rooms.
FOLD_TAIL = "; %d of them%s, the nearest is listed"


def _fold(rows):
    """2.38.0 (W11 H1): objects with the same shown name and the same act words are one entry. The first in the
    given order (the nearest, the menu's order) keeps its acts and refs; its where says how many there are, and in
    how many rooms when they span more than one. A spot, her phone and a person are never folded. rows are
    (entry, where_named, room_id, is_spot, foldable); the folded rows are not in the result."""
    first_of, counts, rooms_of = {}, {}, {}
    kept = []
    for row in rows:
        entry, _name, room_id, _is_spot, foldable = row
        if not foldable:
            kept.append(row)
            continue
        key = (entry["object"], tuple(act["text"] for act in entry["acts"]))
        if key not in first_of:
            first_of[key] = row
            kept.append(row)
            counts[key], rooms_of[key] = 0, set()
        counts[key] += 1
        if room_id is not None:
            rooms_of[key].add(room_id)
    for key, first in first_of.items():
        if counts[key] > 1:
            rooms = len(rooms_of[key])
            clause = " in %d rooms" % rooms if rooms > 1 else ""
            first[0]["where"] = first[0]["where"] + FOLD_TAIL % (counts[key], clause)
    return kept


def options(menu, resolve=None, catalog=None, limit=OPTIONS_LIMIT, people=None, refs=None, withheld=(), room=None,
            room_labels=None, cut=None, objects_limit=OPTIONS_OBJECTS_LIMIT, heard=None, states=None):
    """The observation's options: near objects first (her room, or within NEAR_M), each act with a short ref
    (a1, a2, ...), its guid64 and its text. N8 (F3): a ref is stable for one act on one object for the life
    of the helper session (refs is a RefBook). N8 (F4): identical act texts on one object are listed once;
    each object names its room (room_labels gives the label, when known) and whether it is near. Farthest
    objects are left out until it fits the byte budget and the object limit; cut (a dict, filled in) names
    how many were left out and in which rooms. W2h: an act whose interaction the notebook has seen end on a
    screen only the User's hands can use stays listed, marked with what it opens. HE12: room is the room she
    is in now (the zone's), and the menu's own room comes with the menu."""
    if not isinstance(menu, dict) or not isinstance(menu.get("objects"), list):
        return []
    refs = RefBook() if refs is None else refs
    result = []
    left_out = []
    for item in menu["objects"]:
        if not isinstance(item, dict) or not isinstance(item.get("acts"), list):
            continue
        is_spot = item.get("class") == "spot"  # 2.35.0 (D3): a place she goes to, not a thing she uses
        if item.get("class") == "sim" and people is not None and str(item.get("object_id")) not in people:
            # SS4-v2 (PR3): a person she cannot see is not offered; the menu names only seen Sims.
            continue
        distance = item.get("distance_m")
        where = _where(item, menu.get("room"), room)
        if item.get("class") == "sim" and heard is not None and str(item.get("object_id")) in heard:
            where = HEARD_WHERE  # 2.38.0 (W11 H2): a Sim she hears on her lot, not seen: the room word does not apply
        elif _is_outside(item):
            # W12 (C9, G3): outside the house, and on her lot or not. A meal left at the step is a thing with acts.
            where = {True: OUTSIDE_ON_LOT_WHERE, False: OUTSIDE_OFF_LOT_WHERE}.get(item.get("on_lot"), OUTSIDE_WHERE)
        elif item.get("on_lot") is False:
            where = OFF_LOT_WHERE  # W12 (C10): a neighbour's thing is said to be off her lot
        if isinstance(distance, (int, float)) and not isinstance(distance, bool):
            where = "%s, %.1f m" % (where, distance)
        if item.get("phone") is True:
            where = "with her"  # 2.29.0: her phone is on her, so no distance and no room.
        acts = []
        texts = set()
        for act in item["acts"]:
            if not isinstance(act, dict) or not act.get("guid64"):
                continue
            if is_spot:
                text = SPOT_ACT_TEXT
            else:
                text = _text(resolve, act.get("text_key"), _person_name(item, people)) or humanize(act.get("name"))
            if text in texts:
                continue  # N8 (F4): the same words twice on one object is one act (all the lights, once)
            texts.add(text)
            guid = str(act["guid64"])
            if type(act.get("variant")) is int and not isinstance(act.get("variant"), bool):
                # W12 (G1): a pie-menu choice is its own act; its guid64 carries its variant ("<guid64>v<variant>").
                guid = "%sv%d" % (guid, act["variant"])
            if is_spot:
                # 2.35.0 (D3): a spot's ref is its room, level and kind, not the probe's number (it can change).
                ref_key = ("spot", str(item.get("room")), item.get("level"), item.get("spot"))
            else:
                ref_key = ("act", str(item.get("object_id")), guid)
            listed = {"ref": refs.ref(ref_key), "guid64": guid, "text": text}
            if act.get("name") in withheld or act.get("name") in WITHHELD_SEED:
                listed["opens"] = OPENS_SCREEN
            if act.get("needs_sim") is True:
                listed["needs_sim"] = True  # W13 (D4.1): a phone act that opens a Sim picker; game_act names the Sim
            acts.append(listed)
        if acts:
            label = _room_label(item, room_labels)
            name = _spot_name(item, label) if is_spot else _object_name(item, resolve, catalog, people)
            near = _near(item, room)
            entry = {"object": name, "object_id": str(item.get("object_id")), "where": where, "acts": acts,
                     "near": near}
            if label:
                entry["room"] = label[:64]
            if item.get("reach") is False:
                # 2.25.0: the game's own connectivity check sees no way from her to it now.
                entry["noWay"] = NO_WAY
            if states and not is_spot and str(item.get("object_id")) in states:
                # W13 (D9.6): a thing that is broken or dirty says so, in the words of the things list (at most 4).
                entry["states"] = list(states[str(item.get("object_id"))])[:4]
            refused = _refusals(item, resolve, near)
            if refused:
                entry["refused"] = refused  # W12 (C4): why the game refused her acts here (near objects only)
            if type(item.get("acts_cut")) is int and item["acts_cut"] > 0:
                entry["acts_cut"] = item["acts_cut"]  # W12 (C12): passing acts not listed, after folding by words
            # A room with no label is named by its id in a cut, so a cut is never silent about where it was.
            where_named = label[:64] if label else (str(item["room"])[:64] if item.get("room") is not None else None)
            room_id = None if item.get("room") is None else str(item["room"])
            # 2.38.0 (W11 H1): a thing is folded with its identical kin; a spot, her phone and a person are not.
            foldable = not is_spot and item.get("phone") is not True and item.get("class") != "sim"
            result.append((entry, where_named, room_id, is_spot, foldable))
    # Near first; then the rooms in the menu's order, and a spot before the objects of its own room, so a cut takes
    # a spot only once its room's objects are gone (2.35.0, D3). Within a room the menu's order is kept.
    heads = {}
    for index, row in enumerate(result):
        heads.setdefault(row[2], index)
    result.sort(key=lambda row: (row[0]["near"] is not True, heads[row[2]], not row[3]))
    # 2.38.0 (W11 H1): folded before the budget, so the budget counts what she is shown, not the same thing many times.
    result = _fold(result)
    while result and (len(result) > objects_limit or _bytes([row[0] for row in result]) > limit):
        left_out.append(result.pop()[1])
    # W12 (C8): what the probe's own object cap left out joins the cut, named by room (labels when known).
    dropped = menu.get("dropped") if isinstance(menu.get("dropped"), dict) else {}
    dropped_objects = dropped.get("objects") if type(dropped.get("objects")) is int and dropped["objects"] > 0 else 0
    dropped_rooms = [_probe_room_name(value, room_labels) for value in (dropped.get("rooms") or [])[:16]
                     if isinstance(value, (str, int)) and not isinstance(value, bool)]
    if cut is not None and (left_out or dropped_objects):
        cut["objects"] = len(left_out) + dropped_objects
        cut["rooms"] = sorted({name for name in left_out + dropped_rooms if name})[:16]
    return [row[0] for row in result]


def _probe_room_name(value, room_labels):
    """W12 (C8, C9): a room the probe names by its id, in words: its label, outside, or "room <id>"."""
    if str(value) == OUTSIDE_ROOM:
        return OUTSIDE_NAME
    label = (room_labels or {}).get(str(value))
    return (label if isinstance(label, str) and label else "room %s" % str(value))[:64]


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


class ArgsInvalid(ValueError):
    """W13 (H): a verb act's verb, args or sim id is not the shape the contract allows (never its values)."""


class RoomUnknown(ValueError):
    """W13 (H): the room a place names is not exactly one room of her view (none, or more than one). known: the labels
    of her rooms (at most 8), so the refusal can name them (A4-8)."""

    def __init__(self, reason, known=()):
        super().__init__(reason)
        self.known = [name for name in known if isinstance(name, str)][:8]


class EnvelopeRefused(ArgsInvalid):
    """W13 (H, A6-30): the probe's envelope refused a command the helper wrote (its code is the message)."""


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


def _detail_bytes(detail):
    return len(json.dumps(detail, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _verb_of(act):
    """W13 (H): a verb act's verb, which must be one of VERBS; a verb act carries no guid64."""
    verb = act.get("verb")
    if verb not in VERBS or act.get("guid64") not in (None, ""):
        raise ArgsInvalid("verb")
    return verb


def _verb_args(args):
    """W13 (H): a verb act's probe args, as Natalis wrote them (a dict of text keys, or none). Only the shape and the size
    are checked here; the probe checks the values. Nothing it carries is ever logged."""
    if args is None:
        return {}
    if type(args) is not dict or not all(type(key) is str for key in args) or _bytes(args) > VERB_ARGS_BYTES:
        raise ArgsInvalid("args")
    return dict(args)


def _place_args(args, rooms):
    """W13 (H, D9.3): a buy, place or move names its room the way her view does; the probe takes the room's id. The name
    is matched exactly, ignoring case, against the room labels (rooms maps a room id to its label). No room, or more than
    one, is RoomUnknown: nothing is sent. Relations, targets and facings pass through as Natalis wrote them."""
    place = args.get("place")
    if not isinstance(place, dict) or "room" not in place:
        return args
    name = place["room"]
    if type(name) is not str:
        raise ArgsInvalid("place")
    matches = [room for room, label in (rooms or {}).items()
               if isinstance(label, str) and label.casefold() == name.casefold()]
    if len(matches) != 1 or not str(matches[0]).isdigit():
        raise RoomUnknown("room", sorted((label for label in (rooms or {}).values() if isinstance(label, str)),
                                         key=str.casefold))
    moved = {key: value for key, value in place.items() if key != "room"}
    moved["room_id"] = str(matches[0])  # W13 (S4): a room id is a digit string on the wire
    return dict(args, place=moved)


def _rooms_known(names):
    """W13 (H, A4-8): the rooms she knows, in words for an UNKNOWN_ROOM refusal (at most 200 characters)."""
    text = "rooms known: "
    for index, name in enumerate(names):
        piece = name if index == 0 else "; " + name
        if len(text) + len(piece) > 200:
            break
        text += piece
    return text if names else "rooms known: none"


def _start_of(args):
    """W13 (S7): an event's start as the helper words it: "now", or the day offset (0 today, 1 tomorrow) and the game
    time; None when the args name no start the shape allows."""
    start = args.get("start") if isinstance(args, dict) else None
    if start == "now":
        return "now"
    if (type(start) is dict and set(start) == {"day_offset", "hour", "minute"} and type(start["day_offset"]) is int
            and start["day_offset"] in (0, 1) and type(start["hour"]) is int and 0 <= start["hour"] <= 23
            and type(start["minute"]) is int and 0 <= start["minute"] <= 59):
        return {"day_offset": start["day_offset"], "hour": start["hour"], "minute": start["minute"]}
    return None


def _sim_of(act):
    """W13 (D4.1): the Sim an act names (digits), or None when it names none."""
    sim = act.get("sim_id")
    if sim is None:
        return None
    if type(sim) is int:
        sim = str(sim)
    if type(sim) is not str or _OPTION_ID.fullmatch(sim) is None:
        raise ArgsInvalid("sim_id")
    return sim


def _window_of(detail):
    """W12 (A1): the question a waiting or noted act names in its detail ("dialog <id> ..."), or None."""
    match = _WINDOW.search(detail) if isinstance(detail, str) else None
    return match.group(1) if match else None


def _refusal_code(reply):
    """W12 (B3): the probe's code for a refusal: its reply code, else the word after a "*_REJECT " line, else REFUSED."""
    code = reply.get("code")
    if isinstance(code, str) and 0 < len(code) <= 64:
        return code
    for line in (reply.get("result") or {}).get("lines") or []:
        if isinstance(line, str) and "_REJECT " in line:
            word = line.split("_REJECT ", 1)[1].split(" ")[0]
            if word:
                return word[:64]
    return "REFUSED"


def _split_guid(value):
    """W12 (G1): an option's guid64 is "<guid64>v<variant>" for a pie-menu choice; the probe takes the two apart.
    Anything else passes through unchanged, as before."""
    match = _GUID_VARIANT.fullmatch(str(value))
    if match is None:
        return str(value), None
    return match.group(1), (int(match.group(2)) if match.group(2) is not None else None)


def _variant_of(value):
    """W12 (G1): the variant in an option's guid64, or None when it has none."""
    return _split_guid(value)[1] if value is not None else None


class ActCourier(object):
    """Carries her requested acts to the probe and the probe's record of them back.

    One push per act id: an id written once is never written again, across restarts
    (the spool keeps them). Events to Mint are kept until Mint answered the round trip.
    W12 (B3): the probe's refusal of a command is read from its reply (by the probe); the helper's own refusals say
    by the helper. W12 (B4): a failed round trip is logged; an event Mint refuses is quarantined; unsent events are
    never trimmed. W12 (S2): her words go out as one talk line when the act is pushed. W12 (G1): a pie choice's
    variant is gated on the probe."""

    def __init__(self, spool, publish, resolve=None, memory=None, *, reply=None, log=None, say=None, her_name=None,
                 answered=None, result_words=None, rooms=None, ended=None):
        self._spool = spool
        self._publish = publish
        self._resolve = resolve
        # D7b: called with each sync answer's memory asks, the client and the helper session; it answers off the tick.
        self._memory = memory
        # W12: the probe's reply to one command id (or None while it has not answered); a log line sink; the talk line
        # for her words (text, object id); her first name, or None.
        self._reply = reply
        self._log = log
        self._say = say
        self._her_name = her_name
        # W13 (H): called with each sync answer, the client and the helper session (the lists and the catalogue asks);
        # result_words turns a probe act's result facts into words for its event (None when it cannot).
        self._answered = answered
        self._result_words = result_words
        # W13 (H, D9.3): the room labels of her view (a room id to its label), so a place's room name is an id.
        self._rooms = rooms
        # HELPER2-4: called (no arguments) when a verb act ends, so her lists can be asked for again.
        self._ended = ended
        raw = spool.get_kv("acts_known")
        self._known = json.loads(raw) if raw else {}
        raw = spool.get_kv("acts_events")
        self._events = json.loads(raw) if raw else []
        raw = spool.get_kv("acts_quarantined")
        self.quarantined = json.loads(raw) if raw else []
        # Live 2026-10-06: Cook opens the recipe question instead of entering her queue, so the
        # probe called it gone (LEFT_QUEUE) and she cooked again and again. Dialogs seen open, per telemetry session.
        raw = spool.get_kv("acts_asked")
        self._asked = json.loads(raw) if raw else []
        # H0.5: steps of her plan Ashley still holds (the view sender no longer reads them, D2).
        self.planned = int(spool.get_kv("acts_planned") or 0)
        # D2 (H3): Ashley asked for a look at her body now; handed over once by take_look().
        self.look_owed = False
        # E3: the game dialogs she answered herself in this run (the overlay tells her hand from a human's).
        self.answered_dialogs = []
        # W12 (F1): whether the last round trip was answered; a view waits while it is not.
        self.sync_ok = True

    def _save(self):
        if len(self._known) > KNOWN_LIMIT:
            for act_id in sorted(self._known, key=lambda key: self._known[key]["written_ms"])[:-KNOWN_LIMIT]:
                del self._known[act_id]
        # W12 (B4): unsent events are never trimmed (the round trip sends at most EVENTS_PER_SYNC at a time).
        del self._asked[:-ASKED_LIMIT]
        del self.quarantined[:-QUARANTINE_LIMIT]
        self._spool.put_many_kv({"acts_known": json.dumps(self._known, sort_keys=True),
                                 "acts_events": json.dumps(self._events),
                                 "acts_quarantined": json.dumps(self.quarantined),
                                 "acts_asked": json.dumps(self._asked),
                                 "acts_planned": str(self.planned)})

    def _event(self, act_id, phase, at_ms, detail=None):
        event = {"act_id": act_id, "phase": phase, "at_ms": int(at_ms)}
        if detail:
            event["detail"] = detail
        self._events.append(event)

    def _verb_ended(self, known):
        """HELPER2-4: a verb act (her buy, place, move, sell, save, trip or event) that ended may have changed her lists."""
        if known is not None and known.get("verb") and self._ended is not None:
            self._ended()

    def _log_line(self, now_ms, trigger, error, count):
        """W12 (B4, F6): one line per failed round trip (the decision log's record; never raises)."""
        if self._log is None:
            return
        try:
            self._log({"wall_ms": int(now_ms), "trigger": trigger, "error": error, "events": int(count)})
        except (OSError, ValueError, TypeError):
            pass

    def on_sample(self, row):
        """Any probe row: remember when each game dialog was first seen open, per telemetry session (B1)."""
        dialogs = row.get("dialogs") if isinstance(row, dict) else None
        if not isinstance(dialogs, dict):
            return
        at = row.get("wall_timestamp_ms")
        session = row.get("telemetry_session_id")
        seen = {(item.get("session"), item["dialog_id"]) for item in self._asked}
        added = False
        for item in dialogs.get("open") or []:
            dialog_id = item.get("dialog_id") if isinstance(item, dict) else None
            if dialog_id is None or (session, str(dialog_id)) in seen or type(at) is not int:
                continue
            self._asked.append({"dialog_id": str(dialog_id), "session": session,
                                "kind": str(item.get("kind") or "a question"), "at_ms": at})
            seen.add((session, str(dialog_id)))
            added = True
        if added:
            self._save()

    def _asked_after(self, session, pushed_ms, until_ms):
        """W12 (B1): a question first seen in this telemetry session, between the push and the removal."""
        for item in self._asked:
            if item.get("session") == session and pushed_ms - ASKED_SLACK_MS <= item["at_ms"] <= until_ms:
                return item
        return None

    def _say_words(self, known):
        """W12 (S2): her words, as one talk line in her name, once, when the act is pushed."""
        words = known.get("words")
        if not words or known.get("said") or self._say is None:
            return
        known["said"] = True
        first = self._her_name() if self._her_name is not None else None
        if not first:
            self._log_line(known.get("pushed_ms") or 0, "act_words", "no_name", 0)
            return
        self._say('%s: "%s"' % (first, words), known.get("object"))

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
        window = _window_of(e2.get("detail"))
        if window is not None:
            detail["window"] = window  # W12: the question (dialog) the act is waiting on, when there is one
        known = self._known.get(act_id)
        if isinstance(e2.get("result"), dict) and self._result_words is not None:
            # W13 (D9.3): the probe's facts about a verb act, in words for her (never the probe's ids).
            words = self._words_of_result(e2["result"], (known or {}).get("start"))
            if words:
                detail["result"] = words[:RESULT_WORDS_MAX]
                # Natalis takes a whole detail under 1024 bytes: the words give way first.
                while detail["result"] and _detail_bytes(detail) > DETAIL_BYTES:
                    excess = _detail_bytes(detail) - DETAIL_BYTES
                    detail["result"] = detail["result"][:max(0, len(detail["result"]) - excess)]
                if not detail["result"]:
                    del detail["result"]
        at = row.get("wall_timestamp_ms")
        at = at if type(at) is int and at >= 0 else 0
        session = row.get("telemetry_session_id")
        if phase == "pushed" and known is not None:
            known["pushed_ms"] = at
            known["session"] = session
            self._say_words(known)
            if known.get("words"):
                detail["words"] = known["words"]  # W12 (S2): her words, kept with the act for her outcome and day records
        if phase == "unknown" and detail.get("code") == "LEFT_QUEUE" and known is not None and "pushed_ms" in known:
            asked = self._asked_after(known.get("session"), known["pushed_ms"], at)
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
                detail["text"] = sentence
            if phase == "rejected":
                # W12 (B3): the game's own sentence means the game refused it; with none, the probe did.
                detail["by"] = "game" if sentence else "probe"
        self._event(act_id, phase, at, detail)
        if known is not None:
            known["answered"] = True
            if phase in _TERMINAL:
                known["terminal"] = True
                self._verb_ended(known)
        self._save()

    def _words_of_result(self, result, start=None):
        """W13 (D9.3): the result words for an act's event, or None. A words function that fails says nothing; it never
        stops the act's record from being written. start is the act's own start (W13 S7), or None."""
        try:
            words = self._result_words(result, start)
        except Exception:
            return None
        return words if isinstance(words, str) and words else None

    def take_look(self):
        """D2 (H3): whether a look was asked since the last call; the flag is cleared when it is read."""
        owed, self.look_owed = self.look_owed, False
        return owed

    def _read_replies(self, now_ms):
        """W12 (B3): the probe's refusal of a command of hers, read from its reply, is a REJECTED by the probe; a reply
        that accepted it is read once and says nothing. An act the probe already told about is left alone."""
        if self._reply is None:
            return
        for act_id, known in self._known.items():
            command_id = known.get("cmd")
            if not command_id or known.get("reply_read") or known.get("terminal") or known.get("answered"):
                continue
            reply = self._reply(command_id)
            if not isinstance(reply, dict):
                continue
            known["reply_read"] = True
            if reply.get("status") in ("REJECTED", "ERROR"):
                self._event(act_id, "rejected", now_ms, {"code": _refusal_code(reply), "by": "probe"})
                known["answered"] = True
                known["terminal"] = True
                self._verb_ended(known)

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
                    self._verb_ended(known)
            elif not attached:
                # A9-1: a short detach (a zone load, a sleep, a stale telemetry stall) is not the end of an act
                # the game may still finish; the verdict is a guess only after DETACH_GRACE_MS.
                known.setdefault("detached_ms", now_ms)
                if now_ms - known["detached_ms"] >= DETACH_GRACE_MS:
                    known["timed_out"] = True
                    self._event(act_id, "unknown", now_ms, {"code": "GAME_DETACHED"})
                    self._verb_ended(known)
            elif now_ms - known["written_ms"] >= ACT_CEILING_MS:
                # GL8: the probe began it, and no end came.
                known["timed_out"] = True
                self._event(act_id, "unknown", now_ms, {"code": "NO_END_REPORTED"})
                self._verb_ended(known)
            else:
                known.pop("detached_ms", None)
        self._read_replies(now_ms)
        batch = self._events[:EVENTS_PER_SYNC]
        response = client.sync_acts({"v": 1, "helper_session": helper_session, "events": list(batch)})
        written = []
        answers = []
        if isinstance(response, SyncRefused):
            # W12 (B4): Mint refused the batch as a whole; each event is sent alone, and the ones Mint refuses are
            # quarantined, so one bad event cannot hold the others for ever.
            self._log_line(now_ms, "acts_sync", "refused:%s" % (response.reason or "unknown"), len(batch))
            written, answers = self._send_alone(client, helper_session, now_ms, attached, probe)
        elif response is None:
            self.sync_ok = False
            self._log_line(now_ms, "acts_sync", "no_reply", len(batch))
            self._save()
            return []
        else:
            self.sync_ok = True
            del self._events[:len(batch)]
            written = self._receive(response, now_ms, attached, probe)
            answers = [response]
        self._save()
        for answer in answers:
            # SNAPSHOT: after the acts, on its own thread, so a picture never delays one. Never raises.
            snapshot.handle_requests_in_background(answer.get("snapshots") or [], client, helper_session=helper_session)
            # D7b: her questions to the game's memory; the search runs on its own thread, never on this one.
            if self._memory is not None:
                self._memory(answer.get("memory") or [], client, helper_session)
            # W13 (H): the lists Natalis lacks are sent from here; a catalogue ask is answered on its own thread.
            if self._answered is not None:
                self._answered(answer, client, helper_session)
        return written

    def _push(self, command, args):
        """W13 (H, A6-30): the probe's envelope refuses a command with a code (a ValueError): that is her act's refusal,
        ARGS_INVALID, with the code in its detail. Any other error is not changed."""
        try:
            return self._publish(command, args)
        except ValueError as error:
            raise EnvelopeRefused(str(error)[:40]) from error

    def _send_alone(self, client, helper_session, now_ms, attached, probe):
        """Returns the acts written, and every answer that came (its pictures and memory asks are handled by the caller)."""
        written, answers = [], []
        for _ in range(min(len(self._events), EVENTS_PER_SYNC)):
            event = self._events[0]
            response = client.sync_acts({"v": 1, "helper_session": helper_session, "events": [event]})
            if response is None:
                self.sync_ok = False
                self._log_line(now_ms, "acts_sync", "no_reply", 1)
                break
            del self._events[0]
            if isinstance(response, SyncRefused):
                self.quarantined.append({"event": event, "reason": response.reason or "unknown", "at_ms": int(now_ms)})
                self._log_line(now_ms, "acts_quarantined", "refused:%s" % (response.reason or "unknown"), 1)
                continue
            self.sync_ok = True
            answers.append(response)
            written += self._receive(response, now_ms, attached, probe)
        return written, answers

    def _receive(self, response, now_ms, attached, probe):
        """What Mint answered: the plan, a look, and the acts to push to the probe."""
        planned = response.get("planned")
        self.planned = planned if type(planned) is int and planned >= 0 else 0
        if response.get("look") is True:
            self.look_owed = True
        written = []
        for act in response.get("acts") or []:
            act_id = act.get("act_id") if isinstance(act, dict) else None
            if not isinstance(act_id, str) or act_id in self._known:
                continue
            if not attached:
                self._known[act_id] = {"written_ms": now_ms, "answered": True}
                self._event(act_id, "rejected", now_ms, {"code": "NOT_ATTACHED", "by": "helper"})
                continue
            try:
                object_id = str(act.get("object_id"))
                verb = _verb_of(act) if act.get("verb") is not None else None
                sim = _sim_of(act)
                if verb is not None:
                    # W13 (D5, D9): a verb act is the probe command of its own verb, with Natalis's args.
                    if sim is not None:
                        raise ArgsInvalid("sim_id")
                    needs = [verb]
                    verb_args = _verb_args(act.get("args"))
                    if verb in ("buy", "place", "move") and "place" in verb_args:
                        verb_args = _place_args(verb_args, self._rooms() if self._rooms is not None else {})
                else:
                    needs = [_needs(act, object_id)]
                    if _variant_of(act.get("guid64")) is not None:
                        needs.append("variant")  # W12 (G1): a pie-menu choice needs the probe that can push one
                    if object_id.startswith(DIALOG_PREFIX) and str(act.get("guid64")).startswith("response_"):
                        needs.append("response")  # W12: a numbered response needs the probe that answers by its number
                    if sim is not None:
                        # W13 (D4.1): a Sim picked for a phone act; a window or the queue names none.
                        if object_id == QUEUE_OBJECT_ID or object_id.startswith(DIALOG_PREFIX):
                            raise ArgsInvalid("sim_id")
                        needs.append("sim")
                for need in needs:
                    # A9-9: a probe older than the command needs would ignore it (or refuse it as unknown): say so, never send it.
                    if _too_old(probe, PROBE_NEEDS[need]):
                        raise ProbeTooOld(need)
                if verb is not None:
                    # W13 (A4-19): the act is recorded before its command goes out, so a restart never sends it twice.
                    self._known[act_id] = {"written_ms": now_ms, "answered": True, "object": None}
                    self._save()
                    command = self._push(verb, dict(verb_args, act_id=act_id))
                elif object_id == QUEUE_OBJECT_ID:
                    # 2.20.0: she stops one of her own actions.
                    command = self._push("cancel", {"act_id": act_id, "interaction_id": str(act.get("guid64"))})
                elif object_id.startswith(DIALOG_PREFIX):
                    # 2.18.0: her answer to a game dialog (a picker row or a button). W2h: with
                    # her rows or text, the answer is the dialog's ok carrying them.
                    extra = _answer_args(act.get("answer"))
                    command = self._push("answer", dict({"act_id": act_id, "dialog_id": object_id[len(DIALOG_PREFIX):],
                                                            "pick": "ok" if extra else str(act.get("guid64"))}, **extra))
                    self.answered_dialogs = (self.answered_dialogs + [object_id[len(DIALOG_PREFIX):]])[-ASKED_LIMIT:]
                else:
                    guid, variant = _split_guid(act.get("guid64"))
                    args = {"act_id": act_id, "object_id": object_id, "guid64": guid}
                    if variant is not None:
                        args["variant"] = variant
                    if act.get("owner") is True:
                        # 2.24.0: her Thought said the User asked for it; the probe pushes it first.
                        args["owner"] = True
                    if sim is not None:
                        args["sim_id"] = sim  # W13 (D4.1): the Sim she picked for this phone act
                    command = self._push("act", args)
            except Exception as error:
                self._known[act_id] = {"written_ms": now_ms, "answered": True}
                code = ("ANSWER_INVALID" if isinstance(error, AnswerInvalid) else "ARGS_INVALID" if isinstance(error, ArgsInvalid)
                        else "UNKNOWN_ROOM" if isinstance(error, RoomUnknown)
                        else "PROBE_TOO_OLD" if isinstance(error, ProbeTooOld) else "INBOX_" + type(error).__name__[:40])
                detail = {"code": code, "by": "helper"}
                if isinstance(error, RoomUnknown):
                    detail["detail"] = _rooms_known(error.known)  # W13 (A4-8): the rooms she knows
                elif isinstance(error, EnvelopeRefused):
                    detail["detail"] = str(error)  # W13 (A6-30): the probe's envelope code
                self._event(act_id, "rejected", now_ms, detail)
                continue
            known = {"written_ms": now_ms, "object": object_id if object_id.isdigit() else None}
            if verb is not None:
                known["verb"] = True  # HELPER2-4: a verb act's end is told to the bridge (it may change her lists)
            if isinstance(command, str):
                known["cmd"] = command  # W12 (B3): the probe's reply to this command, read on the next ticks
            if verb == "event":
                known["start"] = _start_of(verb_args)  # W13 (S7): the start the event's words are said from
            words = act.get("words")
            if (object_id.isdigit() and isinstance(words, str) and 1 <= len(words) <= WORDS_MAX
                    and words.strip() == words):
                known["words"] = words  # W12 (S2): her words to the Sim this act targets
            self._known[act_id] = known
            self._event(act_id, "received", now_ms)
            written.append(act_id)
        return written
