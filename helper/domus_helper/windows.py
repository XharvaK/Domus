"""W2h: what happened to the windows that were, or became, not hers, as facts for her portrait.

Read from the probe's speed events and act events: a held window the User was shown after the
wait, a window she could not answer that went to the User, an identity window (always the User's),
a screen her act would have opened that only the User's hands can use, a screen nobody could
name, and a held window that vanished or was dropped by a zone change (W4, ids only). Facts only: what she does about them is her Thought's. Kept in the spool, so a restart keeps
the last half hour."""
import json
import re

WINDOW_MS = 30 * 60_000
PORTRAIT_LIMIT = 4
KEPT = 32
TUNINGS_KEPT = 64
DIALOG_SHOWN = "DIALOG_SHOWN"
DIALOG_DROPPED = "DIALOG_DROPPED"
DROP_CODES = ("VANISHED", "ZONE_CHANGE")
SCREEN_WITHHELD = "SCREEN_WITHHELD"
UNKNOWN_SCREEN = "UNKNOWN_SCREEN"
_ACT = re.compile(r"\bact (\S+)")


def _act_of(detail):
    """The act id a speed event names in its detail ("dialog <id> act <act id>"), or None."""
    match = _ACT.search(detail) if isinstance(detail, str) else None
    return match.group(1) if match else None


def withheld_of(record):
    """(tuning name, screen name) when her act ended on a screen only the User's hands can use
    (act code SCREEN_WITHHELD:<screen>), else None. Ids only; no text."""
    if not isinstance(record, dict) or record.get("event_kind") != "act_event":
        return None
    e2 = record.get("e2") if isinstance(record.get("e2"), dict) else {}
    code = e2.get("code")
    tuning = e2.get("tuning_name")
    if not isinstance(code, str) or not code.startswith(SCREEN_WITHHELD + ":"):
        return None
    if not isinstance(tuning, str) or not tuning:
        return None
    return tuning[:80], (code[len(SCREEN_WITHHELD) + 1:] or "unnamed")[:128]


class WindowLog(object):
    """The window facts, one entry per window (a later fact about the same window replaces it)."""

    def __init__(self, spool):
        self._spool = spool
        raw = spool.get_kv("windows")
        state = json.loads(raw) if raw else {}
        self._entries = [item for item in state.get("entries") or [] if isinstance(item, dict)]
        self._tunings = {str(key): str(value) for key, value in (state.get("tunings") or {}).items()}

    def _save(self):
        del self._entries[:-KEPT]
        while len(self._tunings) > TUNINGS_KEPT:
            del self._tunings[next(iter(self._tunings))]
        self._spool.put_many_kv({"windows": json.dumps({"entries": self._entries, "tunings": self._tunings},
                                                       sort_keys=True)})

    def _add(self, event, code, act_id, at_ms, session):
        if type(at_ms) is not int or at_ms < 0:
            return False
        # One window per (event, act): a dialog shown is told apart by its code, a screen by its act.
        key = "%s|%s|%s" % (event, code if event in (DIALOG_SHOWN, DIALOG_DROPPED) else "",
                            act_id or "at%d" % at_ms)
        entry = {"key": key, "event": event, "code": code, "at_ms": at_ms, "session": session}
        for index, item in enumerate(self._entries):
            if item.get("key") == key:
                self._entries[index] = entry
                return True
        self._entries.append(entry)
        return True

    def on_row(self, record, clock_ms):
        """One probe row from the telemetry (read in order, once)."""
        if not isinstance(record, dict):
            return
        kind = record.get("event_kind")
        e2 = record.get("e2") if isinstance(record.get("e2"), dict) else {}
        session = record.get("telemetry_session_id")
        changed = False
        if kind == "act_event":
            act_id = e2.get("act_id")
            tuning = e2.get("tuning_name")
            if isinstance(act_id, str) and isinstance(tuning, str) and tuning:
                self._tunings.pop(act_id, None)
                self._tunings[act_id] = tuning[:80]
                changed = True
            held = withheld_of(record)
            if held is not None:
                changed = self._add(SCREEN_WITHHELD, held[0], act_id if isinstance(act_id, str) else None,
                                    clock_ms, session) or changed
        elif kind == "speed_event":
            phase = e2.get("phase")
            code = e2.get("code")
            act_id = _act_of(e2.get("detail"))
            if phase == DIALOG_SHOWN and isinstance(code, str) and (
                    code == "TIMEOUT" or code == "IDENTITY_USER" or code.startswith("NOT_ANSWERABLE:")):
                changed = self._add(DIALOG_SHOWN, code[:64], act_id, clock_ms, session)
            elif phase == DIALOG_DROPPED and code in DROP_CODES:
                changed = self._add(DIALOG_DROPPED, code, act_id, clock_ms, session)
            elif phase in (SCREEN_WITHHELD, UNKNOWN_SCREEN):
                changed = self._add(phase, self._tunings.get(act_id) or "unnamed", act_id, clock_ms, session)
        if changed:
            self._save()

    def recent(self, now_ms, session):
        """Her session's window facts of the last 30 minutes, newest last, at most 4. Each says
        what happened (event and code) and how many whole minutes ago."""
        if type(now_ms) is not int:
            return []
        found = [item for item in self._entries
                 if item.get("session") == session and now_ms - WINDOW_MS <= item.get("at_ms", -1)]
        found.sort(key=lambda item: item["at_ms"])
        return [{"event": item["event"], "code": item["code"],
                 "ago_min": max(0, (now_ms - item["at_ms"]) // 60_000)}
                for item in found[-PORTRAIT_LIMIT:]]
