"""Turn one telemetry row into percepts. Explicit extractor state, no I/O."""

from domus_helper.calibration import RUNNING
from domus_helper.thalamus.forward import DurationModel, NeedModel
from domus_helper.thalamus.types import Percept

_USER = "InteractionSource.SCRIPT_WITH_USER_INTENT"
_CANCEL = "InteractionSource.BODY_CANCEL_AOP"
_TEXT_CAP = 120
# Who started an interaction. The game acts on her body's distress even with autonomy
# off (live DA6F: sim_BladderDistress, then toilet). That is her body's own action
# (design 12.3, NATIVE_AUTONOMY), reported as a fact, never as an override or error.
_ORIGINS = {
    "InteractionSource.AUTONOMY": "native_autonomy",
    "InteractionSource.SCRIPT": "script",
    "InteractionSource.SCRIPT_WITH_USER_INTENT": "script",
    "InteractionSource.PIE_MENU": "pie_menu",
}


def _origin(source):
    return _ORIGINS.get(source, "game")


def _text(value):
    if value is None:
        return ""
    return str(value)[:_TEXT_CAP]


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
        self.needs = NeedModel()
        self.durations = DurationModel()
        self.lineage_id = ""
        self.slot_id = None
        self.guid = None
        self.lineage_class = ""
        self._seen_row = False
        self._session = None
        self._seq = None
        self._prev = None
        self._open = {}
        self._barrier = 0
        self._presence = None
        self._social = set()

    def step(self, row):
        percepts = []
        kind = row.get("event_kind")
        session = row.get("telemetry_session_id")
        seq = row.get("written_sequence")
        if self._seen_row and kind == "session_open":
            percepts.append(self._gap(session))
        elif (self._seq is not None and type(seq) is int and session == self._session
              and seq > self._seq + 1):
            percepts.append(self._gap(session))
        if kind == "lineage_event":
            percepts.append(self._lineage(row))
        if kind in ("presence_snapshot", "session_open"):
            percepts.extend(self._snapshot(row))
        if type(seq) is int:
            self._seq = seq
            self._session = session
        if kind is not None:
            self._seen_row = True
        return percepts

    def _gap(self, session):
        self.needs.reset()
        self.durations.reset()
        self._barrier += 1
        self._seen_row = True
        return Percept("gap", "session", "" if session is None else str(session), "gap",
                       urgency="wake", lineage=self.lineage_id)

    def _lineage(self, row):
        e2 = row.get("e2") or {}
        slot = "" if e2.get("slot_id") is None else str(e2.get("slot_id"))
        guid = "" if e2.get("guid") is None else str(e2.get("guid"))
        lineage_class = "" if e2.get("lineage_class") is None else str(e2.get("lineage_class"))
        percept = Percept("lineage", slot, guid, lineage_class, urgency="wake", lineage="")
        self.slot_id = e2.get("slot_id")
        self.guid = e2.get("guid")
        self.lineage_class = lineage_class
        self.lineage_id = f"{slot}:{guid}"
        self.needs.reset()
        self.durations.reset()
        self._barrier += 1
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
        prior_running = {} if previous is None else previous["running"]
        percepts.extend(self._interactions(
            prior_running, running, observed, ticks, paused, sim_s))
        if previous is not None:
            percepts.extend(self._needs(previous, row, ticks, paused, sim, motives, running))
            if posture_name != previous["posture"]:
                percepts.append(Percept(
                    "posture", sim_s, "" if target is None else str(target),
                    "" if posture_name is None else str(posture_name),
                    lineage=self.lineage_id, facts=_facts(ticks, ())))
            percepts.extend(self._zone(previous, zone, ticks))
        if "presence" in row:
            percepts.extend(self._presence_percepts(row.get("presence") or [], ticks))
        if "social" in row:
            percepts.extend(self._social_percepts(row.get("social") or [], sim_s, ticks))
        self._prev = {
            "sim": sim,
            "ticks": ticks,
            "paused": paused,
            "session": row.get("telemetry_session_id"),
            "seq": row.get("written_sequence"),
            "posture": posture_name,
            "zone_id": zone.get("zone_id"),
            "lot_id": zone.get("lot_id"),
            "running": running,
            "motives": motives,
        }
        for identity, entry in running.items():
            span = self._open.get(identity)
            if span is None:
                self._open[identity] = {
                    "affordance_id": entry.get("affordance_id"),
                    "text": entry.get("affordance_text"),
                    "source": entry.get("source_raw"),
                    "ticks": ticks,
                    "barrier": self._barrier,
                    "crossed": paused,
                }
            elif paused:
                span["crossed"] = True
        return percepts

    def _needs(self, previous, row, ticks, paused, sim, motives, running):
        percepts = []
        learn = self._consecutive(previous, row, ticks, paused, sim)
        activity = tuple(sorted({
            entry.get("affordance_id") for entry in previous["running"].values()
        }))
        for motive_id in sorted(motives):
            item = motives[motive_id]
            band = item.get("band")
            value = item.get("value")
            before = previous["motives"].get(motive_id)
            z = 0.0
            if (learn and before is not None and type(before.get("value")) in (int, float)
                    and type(value) in (int, float) and type(previous["ticks"]) is int
                    and type(ticks) is int):
                z = self.needs.observe(
                    motive_id, activity, previous["ticks"], before["value"], ticks, value)
            if before is not None and before.get("band") != band and band is not None:
                percepts.append(self._need(motive_id, band, value, ticks, self._band_urgency(
                    before.get("band"), band), 0.0))
            elif before is not None and z >= 2.0 and band is not None:
                percepts.append(self._need(motive_id, band, value, ticks, "normal", z))
        return percepts

    def _consecutive(self, previous, row, ticks, paused, sim):
        if previous["sim"] != sim:
            return False
        if previous["session"] != row.get("telemetry_session_id"):
            return False
        seq = row.get("written_sequence")
        if type(previous["seq"]) is not int or type(seq) is not int or seq != previous["seq"] + 1:
            return False
        if paused or previous["paused"]:
            return False
        if type(previous["ticks"]) is not int or type(ticks) is not int or ticks <= previous["ticks"]:
            return False
        return True

    def _band_urgency(self, before, after):
        if after == "distress":
            return "always_through"
        if before == "ok" and after == "low":
            return "wake"
        return "normal"

    def _need(self, motive, band, value, ticks, urgency, surprise):
        return Percept(
            "need", str(motive), "", str(band), surprise=surprise, urgency=urgency,
            lineage=self.lineage_id,
            facts=_facts(ticks, (("value", value), ("band", band))))

    def _interactions(self, prior_running, running, observed, ticks, paused, sim_s):
        percepts = []
        gone = [identity for identity in prior_running if identity not in running]
        for identity in gone:
            entry = prior_running[identity]
            closing = _find_entry(observed, identity)
            source = (closing or entry).get("source_raw")
            affordance = entry.get("affordance_id")
            span = self._open.get(identity)
            surprise = 0.0
            if source == _CANCEL:
                surprise = 3.0
            elif span is not None and self._clear_duration(span, ticks, paused):
                duration = ticks - span["ticks"]
                surprise = self.durations.surprise(duration, affordance)
                self.durations.observe(affordance, duration)
            pressure = "action_end" if source == _USER else None
            percepts.append(Percept(
                "interaction", sim_s, str(affordance), "ended", surprise=surprise,
                pressure=pressure, lineage=self.lineage_id,
                facts=_facts(ticks, (("affordance_text", _text(
                    (closing or entry).get("affordance_text"))),
                    ("origin", _origin(entry.get("source_raw")))))))
            self._open.pop(identity, None)
        for identity, entry in running.items():
            if identity in prior_running:
                continue
            percepts.append(Percept(
                "interaction", sim_s, str(entry.get("affordance_id")), "started",
                lineage=self.lineage_id,
                facts=_facts(ticks, (("affordance_text", _text(entry.get("affordance_text"))),
                                     ("origin", _origin(entry.get("source_raw")))))))
        return percepts

    def _clear_duration(self, span, ticks, paused):
        if span["barrier"] != self._barrier or span["crossed"] or paused:
            return False
        if type(span["ticks"]) is not int or type(ticks) is not int:
            return False
        return ticks >= span["ticks"]

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

    def _presence_percepts(self, items, ticks):
        current = set()
        for item in items:
            if isinstance(item, dict) and item.get("id") is not None:
                current.add(str(item["id"]))
        percepts = []
        if self._presence is None:
            self._presence = set()
        for sim_id in sorted(current - self._presence):
            percepts.append(Percept(
                "presence", sim_id, "", "arrived", lineage=self.lineage_id, facts=_facts(ticks, ())))
        for sim_id in sorted(self._presence - current):
            percepts.append(Percept(
                "presence", sim_id, "", "left", lineage=self.lineage_id, facts=_facts(ticks, ())))
        self._presence = current
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
            "needs": self.needs.to_dict(),
            "durations": self.durations.to_dict(),
            "lineage_id": self.lineage_id,
            "slot_id": self.slot_id,
            "guid": self.guid,
            "lineage_class": self.lineage_class,
            "seen_row": self._seen_row,
            "session": self._session,
            "seq": self._seq,
            "prev": self._prev,
            "open": self._open,
            "barrier": self._barrier,
            "presence": None if self._presence is None else sorted(self._presence),
            "social": sorted(self._social),
        }

    @classmethod
    def from_dict(cls, blob):
        extractor = cls(owner_sim_id=blob.get("owner_sim_id"))
        extractor.needs = NeedModel.from_dict(blob.get("needs") or {})
        extractor.durations = DurationModel.from_dict(blob.get("durations") or {})
        extractor.lineage_id = blob.get("lineage_id") or ""
        extractor.slot_id = blob.get("slot_id")
        extractor.guid = blob.get("guid")
        extractor.lineage_class = blob.get("lineage_class") or ""
        extractor._seen_row = bool(blob.get("seen_row"))
        extractor._session = blob.get("session")
        extractor._seq = blob.get("seq")
        extractor._prev = blob.get("prev")
        extractor._open = blob.get("open") or {}
        extractor._barrier = blob.get("barrier") or 0
        presence = blob.get("presence")
        extractor._presence = None if presence is None else set(presence)
        extractor._social = set(blob.get("social") or [])
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
