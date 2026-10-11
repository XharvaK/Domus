"""Turn one telemetry row into percepts. Explicit extractor state, no I/O."""

from domus_helper.calibration import RUNNING
from domus_helper.thalamus.types import Percept

_USER = "InteractionSource.SCRIPT_WITH_USER_INTENT"
_CANCEL = "InteractionSource.BODY_CANCEL_AOP"
# H0.5: what the game runs to hold a body in place (stand, sit): not doing anything.
_IDLE_SOURCES = ("InteractionSource.POSTURE_GRAPH", _CANCEL)
_TEXT_CAP = 120
# GL9: a mood change this soon after her own act ended folds into her next wake; it does not wake her by itself.
MOOD_FOLD_MS = 60_000
# Who started an interaction. The game acts on her body's distress even with autonomy
# off (live DA6F: sim_BladderDistress, then toilet). That is her body's own action
# (design 12.3, NATIVE_AUTONOMY), reported as a fact, never as an override or error.
_ORIGINS = {
    "InteractionSource.AUTONOMY": "native_autonomy",
    # D36: plain SCRIPT and REACTION are the game reacting (a bad smell); only a
    # push with user intent is hers.
    "InteractionSource.SCRIPT": "native_reaction",
    "InteractionSource.REACTION": "native_reaction",
    "InteractionSource.SCRIPT_WITH_USER_INTENT": "script",
    "InteractionSource.PIE_MENU": "pie_menu",
}


def _origin(source):
    return _ORIGINS.get(source, "game")


def _text(value):
    if value is None:
        return ""
    return str(value)[:_TEXT_CAP]


def _conditions_of(objects):
    """2.32.0 (HE7): object id -> {class, states: [[state, value], ...]} from a sample's near_conditions."""
    found = {}
    for item in objects.get("near_conditions") or []:
        if not isinstance(item, dict) or item.get("object_id") is None:
            continue
        states = sorted([str(state.get("state")), str(state.get("value"))]
                        for state in item.get("states") or [] if isinstance(state, dict))
        found[str(item["object_id"])] = {"class": item.get("class"), "states": states}
    return found


def _facts(ticks, pairs):
    items = []
    if type(ticks) is int:
        items.append(("ticks", str(ticks)))
    for key, value in pairs:
        if value is None:
            continue
        items.append((key, value if isinstance(value, str) else str(value)))
    return tuple(items)


def _entry_id(entry):
    identity = entry.get("interaction_id")
    if identity is None:
        identity = entry.get("entry_key")
    if identity is None:
        return None
    return str(identity)


class Extractor:
    def __init__(self, owner_sim_id=None):
        self.owner_sim_id = owner_sim_id
        self.lineage_id = ""
        self.slot_id = None
        self.guid = None
        self.lineage_class = ""
        self._seen_row = False
        self._session = None
        self._seq = None
        self._prev = None
        self._presence = None
        # HE3: who each present Sim was (name and last room), so "left" can say who and where.
        self._presence_names = {}
        self._on_lot = set()
        self._social = set()
        self._asked = set()
        self._busy = None
        self._mood = None
        self._wall_ms = None
        self._finished_ms = None

    def step(self, row):
        percepts = []
        kind = row.get("event_kind")
        wall = row.get("wall_timestamp_ms")
        self._wall_ms = wall if type(wall) is int else None
        session = row.get("telemetry_session_id")
        seq = row.get("written_sequence")
        if kind == "session_open":
            self._new_session(row)
        if self._seen_row and kind == "session_open":
            percepts.append(self._gap(session))
        elif (self._seq is not None and type(seq) is int and session == self._session
              and seq > self._seq + 1):
            # HE16: the rows between the two sequence numbers are the ones she did not get.
            percepts.append(self._gap(session, lost=seq - self._seq - 1))
        if kind == "lineage_event":
            percepts.append(self._lineage(row))
        if kind == "act_event":
            percepts.extend(self._act(row))
        if kind in ("presence_snapshot", "session_open"):
            percepts.extend(self._snapshot(row))
        if type(seq) is int:
            self._seq = seq
            self._session = session
        if kind is not None:
            self._seen_row = True
        return percepts

    def _new_session(self, row):
        """D51 (live 2026-10-05): a new session may be another save. Its first observation
        carried the old save's world, and its first snapshot was compared with the old
        save's last row (four lab Sims "left" her new home). The save comes from
        session_open itself; nothing is compared across sessions."""
        save = row.get("save") or {}
        slot, guid = save.get("slot_id"), save.get("save_slot_guid")
        if slot is not None and guid is not None and (str(slot), str(guid)) != (str(self.slot_id), str(self.guid)):
            self.slot_id, self.guid = slot, guid
            self.lineage_class = ""
            if self.lineage_id:  # a known lineage is left; a first one waits for its lineage event
                self.lineage_id = f"{slot}:{guid}"
        self._prev = None
        self._presence = None
        self._on_lot = set()
        self._social = set()
        self._asked = set()
        self._busy = None
        self._mood = None
        self._wall_ms = None
        self._finished_ms = None

    def _act(self, row):
        """8f: her chosen act was refused, or nobody can tell what became of it. Wakes her;
        a pushed act's start and end are already seen as her interactions. 2.24.0: a pushed
        act the game ended before it ever began was never one of her interactions, so its end
        wakes her too."""
        e2 = row.get("e2") or {}
        phase = e2.get("phase")
        if phase == "FINISHED" and e2.get("started") is False:
            name = "act_never_started"
        elif phase in ("REJECTED", "UNKNOWN"):
            name = "act_" + phase.lower()
        else:
            return []
        return [Percept("interaction", str(e2.get("act_id") or ""), str(e2.get("guid64") or ""),
                        name, urgency="wake", lineage=self.lineage_id,
                        facts=_facts(None, (("code", e2.get("code")), ("detail", e2.get("detail")),
                                            ("tuning_name", e2.get("tuning_name")),
                                            ("finishing_type", e2.get("finishing_type")), ("origin", "her_choice"))))]

    def _gap(self, session, lost=None):
        self._seen_row = True
        return Percept("gap", "session", "" if session is None else str(session), "gap",
                       urgency="wake", lineage=self.lineage_id, facts=_facts(None, (("lost", lost),)))

    def _lineage(self, row):
        e2 = row.get("e2") or {}
        slot = "" if e2.get("slot_id") is None else str(e2.get("slot_id"))
        guid = "" if e2.get("guid") is None else str(e2.get("guid"))
        lineage_class = "" if e2.get("lineage_class") is None else str(e2.get("lineage_class"))
        # 2.32.0 (PR5): a BODY_GONE record says why (her Sim died); the reason is a fact of the percept.
        reason = e2.get("reason")
        facts = (("reason", str(reason)[:64]),) if isinstance(reason, str) and reason else ()
        percept = Percept("lineage", slot, guid, lineage_class, urgency="wake", lineage="", facts=facts)
        self.slot_id = e2.get("slot_id")
        self.guid = e2.get("guid")
        self.lineage_class = lineage_class
        self.lineage_id = f"{slot}:{guid}"
        return percept

    def _snapshot(self, row):
        game = row.get("game") or {}
        ticks = game.get("ticks")
        paused = game.get("paused") is True
        body = row.get("body") or {}
        sim = body.get("sim_id")
        sim_s = "" if sim is None else str(sim)
        posture = (body.get("posture") or {})
        posture_name = posture.get("posture_name")
        target = posture.get("target_id") or ""
        zone = row.get("zone") or {}
        observed = ((row.get("interactions") or {}).get("observed")) or []
        running = {}
        for entry in observed:
            if entry.get("membership") not in RUNNING:
                continue
            identity = _entry_id(entry)
            if identity is None or entry.get("affordance_id") is None:
                continue
            running[identity] = entry
        motives = {}
        for item in row.get("motives") or []:
            motive_id = item.get("id")
            if motive_id is None:
                continue
            motives[motive_id] = item
        percepts = []
        previous = self._prev
        objects = row.get("objects")
        # HE7: the notable conditions of the 16 nearest objects, when this sample names them.
        conditions = (_conditions_of(objects) if isinstance(objects, dict) and "near_conditions" in objects
                      else None)
        prior_running = {} if previous is None else previous["running"]
        percepts.extend(self._interactions(prior_running, running, observed, ticks, sim_s))
        if previous is not None:
            percepts.extend(self._needs(previous, ticks, motives))
            if posture_name != previous["posture"]:
                percepts.append(Percept(
                    "posture", sim_s, "" if target is None else str(target),
                    "" if posture_name is None else str(posture_name),
                    lineage=self.lineage_id, facts=_facts(ticks, ())))
            percepts.extend(self._zone(previous, zone, ticks))
            percepts.extend(self._room(previous, zone, ticks))
            if conditions is not None:
                percepts.extend(self._condition_percepts(previous.get("conditions") or {}, conditions, ticks))
        if "presence" in row:
            percepts.extend(self._presence_percepts(row.get("presence") or [], ticks))
        if "social" in row:
            percepts.extend(self._social_percepts(row.get("social") or [], sim_s, ticks))
        if "dialogs" in row:
            percepts.extend(self._dialog_percepts(row.get("dialogs") or {}, sim_s, ticks))
        percepts.extend(self._decision_points(observed, row.get("mood"), sim_s, ticks))
        self._prev = {
            "sim": sim,
            "ticks": ticks,
            "paused": paused,
            "session": row.get("telemetry_session_id"),
            "seq": row.get("written_sequence"),
            "posture": posture_name,
            "zone_id": zone.get("zone_id"),
            "lot_id": zone.get("lot_id"),
            "room": zone.get("room"),
            "running": running,
            "motives": motives,
            # HE7: the notable conditions of the near objects this sample named (kept when a sample names none).
            "conditions": conditions if conditions is not None else (previous or {}).get("conditions"),
        }
        return percepts

    def _needs(self, previous, ticks, motives):
        percepts = []
        for motive_id in sorted(motives):
            item = motives[motive_id]
            band = item.get("band")
            before = previous["motives"].get(motive_id)
            # D2: a need is sent when its band changes. How far it drifted inside one band is not sent.
            if before is not None and before.get("band") != band and band is not None:
                percepts.append(self._need(motive_id, band, item.get("value"), ticks,
                                           self._band_urgency(before.get("band"), band)))
        return percepts

    def _band_urgency(self, before, after):
        if after == "distress":
            return "always_through"
        if before == "ok" and after == "low":
            return "wake"
        return "normal"

    def _need(self, motive, band, value, ticks, urgency):
        return Percept(
            "need", str(motive), "", str(band), urgency=urgency,
            lineage=self.lineage_id,
            facts=_facts(ticks, (("value", value), ("band", band))))

    def _interactions(self, prior_running, running, observed, ticks, sim_s):
        percepts = []
        gone = [identity for identity in prior_running if identity not in running]
        for identity in gone:
            entry = prior_running[identity]
            closing = _find_entry(observed, identity)
            source = (closing or entry).get("source_raw")
            affordance = entry.get("affordance_id")
            pressure = "action_end" if source == _USER else None
            self._finished_ms = self._wall_ms
            percepts.append(Percept(
                "interaction", sim_s, str(affordance), "ended",
                pressure=pressure, urgency="wake", lineage=self.lineage_id,
                facts=_facts(ticks, (("affordance_text", _text(
                    (closing or entry).get("affordance_text"))),
                    ("origin", _origin(entry.get("source_raw")))))))
        for identity, entry in running.items():
            if identity in prior_running:
                continue
            percepts.append(Percept(
                "interaction", sim_s, str(entry.get("affordance_id")), "started",
                lineage=self.lineage_id,
                facts=_facts(ticks, (("affordance_text", _text(entry.get("affordance_text"))),
                                     ("origin", _origin(entry.get("source_raw")))))))
        return percepts

    def _zone(self, previous, zone, ticks):
        zone_id = zone.get("zone_id")
        lot_id = zone.get("lot_id")
        before_zone = previous["zone_id"]
        before_lot = previous["lot_id"]
        if not _zone_changed(before_zone, zone_id) and not _zone_changed(before_lot, lot_id):
            return []
        return [Percept(
            "env", "zone", "" if zone_id is None else str(zone_id),
            "" if lot_id is None else str(lot_id), urgency="wake", lineage=self.lineage_id,
            facts=_facts(ticks, ()))]

    def _condition_percepts(self, before, now, ticks):
        """HE7: a near object's notable condition came, changed, or cleared (an empty state list)."""
        found = []
        for object_id in sorted(set(before) | set(now)):
            was = (before.get(object_id) or {}).get("states") or []
            is_now = (now.get(object_id) or {}).get("states") or []
            if was == is_now:
                continue
            klass = ((now.get(object_id) or before.get(object_id) or {}).get("class")) or ""
            text = "; ".join("%s=%s" % (state, value) for state, value in is_now)
            found.append(Percept("env", "object_state", object_id, str(klass)[:64], lineage=self.lineage_id,
                                 facts=_facts(ticks, (("states", text[:256]),))))
        return found

    def _room(self, previous, zone, ticks):
        """DS3: her body moved to another room (schema 6 fills zone.room)."""
        room = zone.get("room")
        before = previous.get("room")
        if room is None or room == before:
            return []
        return [Percept("env", "room", str(room), str(room), lineage=self.lineage_id,
                        facts=_facts(ticks, (("from_room", before),)))]

    def _presence_percepts(self, items, ticks):
        current = {}
        for item in items:
            # DS3: schema 6 lists her own body too (is_body); it never "arrives".
            if isinstance(item, dict) and item.get("id") is not None and not item.get("is_body"):
                current[str(item["id"])] = item
        percepts = []
        if self._presence is None:
            self._presence = set()
        for sim_id in sorted(set(current) - self._presence):
            item = current[sim_id]
            doing = item.get("doing")
            percepts.append(Percept(
                "presence", sim_id, "", "arrived", lineage=self.lineage_id, facts=_facts(ticks, (
                    ("name", item.get("name")), ("room", item.get("room")),
                    ("distance_m", item.get("distance_m")),
                    ("doing", doing[:120] if isinstance(doing, str) else None)))))
        for sim_id in sorted(self._presence - set(current)):
            gone = self._presence_names.get(sim_id) or {}
            percepts.append(Percept(
                "presence", sim_id, "", "left", lineage=self.lineage_id, facts=_facts(ticks, (
                    ("name", gone.get("name")), ("room", gone.get("room"))))))
        self._presence = set(current)
        self._presence_names = {sim_id: {"name": item.get("name"), "room": item.get("room")}
                                for sim_id, item in current.items()}
        # 2.17.0 (live 2026-10-06: the welcome wagon waited at her door while she stood at the
        # mirror): someone stepping onto the lot she is on wakes her, with the game situation
        # they are in. Walkbys on the street stay ordinary presence.
        here = {sim_id for sim_id, item in current.items() if item.get("on_lot") is True}
        for sim_id in sorted(here - self._on_lot):
            item = current[sim_id]
            roles = [str(s.get("role")) for s in item.get("situations") or [] if isinstance(s, dict) and s.get("role")]
            percepts.append(Percept(
                "presence", sim_id, "", "on_lot", urgency="wake", lineage=self.lineage_id, facts=_facts(ticks, (
                    ("name", item.get("name")), ("room", item.get("room")),
                    ("distance_m", item.get("distance_m")),
                    ("role", roles[0][:96] if roles else None)))))
        self._on_lot = here
        return percepts

    def _decision_points(self, observed, mood, sim_s, ticks):
        """H0.5: she becomes idle (nothing she or her body is doing; the posture the game keeps
        her in does not count), or her mood changes. Both wake her; drift does not."""
        busy = any(
            entry.get("membership") in RUNNING + ("QUEUED",)
            and entry.get("source_raw") not in _IDLE_SOURCES
            for entry in observed if isinstance(entry, dict))
        percepts = []
        if self._busy is True and not busy:
            percepts.append(Percept("interaction", sim_s, "", "idle", urgency="wake",
                                    lineage=self.lineage_id, facts=_facts(ticks, ())))
        self._busy = busy
        name = mood.get("name") if isinstance(mood, dict) else None
        if isinstance(name, str) and name:
            if self._mood is not None and name != self._mood:
                folds = (self._finished_ms is not None and self._wall_ms is not None
                         and 0 <= self._wall_ms - self._finished_ms < MOOD_FOLD_MS)
                percepts.append(Percept("moodlet", "mood", self._mood[:64], name[:64],
                                        urgency="normal" if folds else "wake",
                                        lineage=self.lineage_id,
                                        facts=_facts(ticks, (("from", self._mood[:64]), ("to", name[:64])))))
            self._mood = name
        return percepts

    def _dialog_percepts(self, dialogs, sim_s, ticks):
        """2.19.0 (live 2026-10-06: a work event asked her to nuke or remake a dish, the game
        paused for her answer, and nothing woke her): a question the game puts to her (a
        dialog that is hers or nobody's) wakes her once, when it opens."""
        open_now = set()
        percepts = []
        for item in (dialogs.get("open") if isinstance(dialogs, dict) else None) or []:
            if not isinstance(item, dict) or item.get("dialog_id") is None or item.get("auto_respond") is True:
                continue
            owner = item.get("owner_id")
            if owner is not None and sim_s and str(owner) != sim_s:
                continue
            dialog_id = str(item["dialog_id"])
            open_now.add(dialog_id)
            if dialog_id in self._asked:
                continue
            percepts.append(Percept(
                "env", "dialog", dialog_id, "asked", urgency="wake", lineage=self.lineage_id,
                facts=_facts(ticks, (("title_key", item.get("title_key")),))))
        self._asked = open_now
        return percepts

    def _social_percepts(self, items, sim_s, ticks):
        percepts = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            target = item.get("target_id")
            if target is None or str(target) != sim_s:
                continue
            identity = _entry_id(item) or str(item.get("affordance_id"))
            seen.add(identity)
            if identity in self._social:
                continue
            source = item.get("source_sim")
            if source is None:
                source = item.get("actor_id")
            source_s = "" if source is None else str(source)
            urgency = "always_through" if source_s and source_s == self.owner_sim_id else "normal"
            percepts.append(Percept(
                "social", source_s, "" if item.get("affordance_id") is None else str(item.get("affordance_id")),
                "addressed", urgency=urgency, lineage=self.lineage_id, facts=_facts(ticks, ())))
        self._social = seen
        return percepts

    def to_dict(self):
        return {
            "owner_sim_id": self.owner_sim_id,
            "lineage_id": self.lineage_id,
            "slot_id": self.slot_id,
            "guid": self.guid,
            "lineage_class": self.lineage_class,
            "seen_row": self._seen_row,
            "session": self._session,
            "seq": self._seq,
            "prev": self._prev,
            "presence": None if self._presence is None else sorted(self._presence),
            "presence_names": self._presence_names,
            "on_lot": sorted(self._on_lot),
            "social": sorted(self._social),
            "asked": sorted(self._asked),
            "busy": self._busy,
            "mood": self._mood,
        }

    @classmethod
    def from_dict(cls, blob):
        extractor = cls(owner_sim_id=blob.get("owner_sim_id"))
        extractor.lineage_id = blob.get("lineage_id") or ""
        extractor.slot_id = blob.get("slot_id")
        extractor.guid = blob.get("guid")
        extractor.lineage_class = blob.get("lineage_class") or ""
        extractor._seen_row = bool(blob.get("seen_row"))
        extractor._session = blob.get("session")
        extractor._seq = blob.get("seq")
        extractor._prev = blob.get("prev")
        presence = blob.get("presence")
        extractor._presence = None if presence is None else set(presence)
        extractor._presence_names = blob.get("presence_names") or {}
        extractor._on_lot = set(blob.get("on_lot") or [])
        extractor._social = set(blob.get("social") or [])
        extractor._asked = set(blob.get("asked") or [])
        extractor._busy = blob.get("busy")
        extractor._mood = blob.get("mood")
        return extractor


def _find_entry(observed, identity):
    for entry in observed:
        if _entry_id(entry) == identity:
            return entry
    return None


def _zone_changed(before, after):
    if before == after:
        return False
    if before is None and after is not None:
        return True
    return before is not None and after is not None
