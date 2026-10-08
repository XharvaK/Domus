"""W3h: her pace, as facts. The helper's settings (pace.json in the data folder) say how slowly her
needs drain and how slowly the game runs; the probe applies them and reports what it applied in
each row (`pace`). Her portrait says what that means for her: the drain in words, the clock scale
when it is not 1, and what her last decisions cost in game minutes. Facts only: no advice, no rule.

Game facts (CLOCK_RESEARCH.md, date_and_time): a sim second is 25 real milliseconds at the game's
normal tick length and ticks are milliseconds, so a game minute is 60 x 25 = 1500 ticks. The
decision cost counts ticks, so it is the same whatever the clock scale is.
"""
import json
import math

CONFIG = "pace.json"
DEFAULT_NEED_DRAIN = 0.5
DEFAULT_SLOW_TIME = 1.0
LOWEST = 0.25
HIGHEST = 1.0
TICKS_PER_GAME_MINUTE = 60 * 25
# The probe's applied values differ from the wanted ones for this many rows in a row: send again.
MISMATCH_ROWS = 3
# A mismatch resend is at most this often (a probe that refuses the clock must not get a command per row).
MISMATCH_EVERY_MS = 60_000
DECISIONS_SHOWN = 3
DECISIONS_KEPT = 8
PENDING_KEPT = 16
_WORDS = {0.25: "a quarter", 0.5: "half", 0.75: "three quarters"}


def _factor(value):
    """A setting or a reported factor: a finite number in [0.25, 1.0], as a float. Else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if not LOWEST <= value <= HIGHEST:
        return None
    return float(value)


def read_config(path, log=print):
    """{"need_drain", "slow_time"} from the settings file. No file: the defaults. A value that is
    not a number in [0.25, 1.0] keeps its default; one log line says which keys were refused."""
    settings = {"need_drain": DEFAULT_NEED_DRAIN, "slow_time": DEFAULT_SLOW_TIME}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return settings
    except (OSError, ValueError):
        log("pace settings skipped: %s is not readable JSON; using the defaults" % CONFIG)
        return settings
    if not isinstance(raw, dict):
        log("pace settings skipped: %s is not an object; using the defaults" % CONFIG)
        return settings
    refused = []
    for name in ("need_drain", "slow_time"):
        if name not in raw:
            continue
        value = _factor(raw[name])
        if value is None:
            refused.append(name)
        else:
            settings[name] = value
    if refused:
        log("pace settings %s not in [0.25, 1.0]; using the defaults for them" % ", ".join(refused))
    return settings


class PaceSettings(object):
    """The settings file, re-read when it changes (the bridge asks on every tick)."""

    def __init__(self, data_dir, log=print):
        self._path = data_dir / CONFIG
        self._log = log
        self._stamp = "unread"
        self.values = {"need_drain": DEFAULT_NEED_DRAIN, "slow_time": DEFAULT_SLOW_TIME}

    def refresh(self):
        try:
            status = self._path.stat()
            stamp = (status.st_mtime_ns, status.st_size)
        except OSError:
            stamp = None
        if stamp != self._stamp:
            self._stamp = stamp
            self.values = read_config(self._path, self._log)
        return self.values


def amount(factor):
    """A factor in words for her portrait: 0.5 -> "half", 0.4 -> "0.4 times"."""
    if factor in _WORDS:
        return _WORDS[factor]
    return "%g times" % factor


def needs_sentence(factor):
    if factor == 1.0:
        return "your needs drain at the game's pace."
    return "your needs drain at %s the game's pace, by the User's choice." % amount(factor)


def clock_sentence(scale):
    return "the game's clock runs at %s its normal speed." % amount(scale)


def game_minutes(decided_ticks, reached_ticks):
    """Game minutes from the game time of what she decided on to the game time her act reached
    the game (one decimal), or None when either tick is missing or the order is wrong."""
    if type(decided_ticks) is not int or type(reached_ticks) is not int:
        return None
    if reached_ticks < decided_ticks:
        return None
    return round((reached_ticks - decided_ticks) / TICKS_PER_GAME_MINUTE, 1)


def applied_differs(block, wanted):
    """True when a row's `pace` block shows other values than the wanted ones. A probe that
    refused the clock (clock_foreign) is not counted for slow_time: it can never apply it."""
    if not isinstance(block, dict):
        return False
    need = _factor(block.get("need_drain"))
    if need is None or abs(need - wanted["need_drain"]) > 1e-9:
        return True
    if block.get("clock_foreign") is True:
        return False
    slow = _factor(block.get("slow_time"))
    return slow is None or abs(slow - wanted["slow_time"]) > 1e-9


def portrait(block, costs):
    """Her pace entry (portrait "pace"), or None when there is nothing to say. `block` is the
    probe's latest `pace` block; `costs` is PaceLog.costs()."""
    entry = {}
    if isinstance(block, dict):
        need = _factor(block.get("need_drain"))
        if need is not None:
            entry["needs"] = needs_sentence(need)
        scale = block.get("clock_scale")
        if isinstance(scale, (int, float)) and not isinstance(scale, bool) and math.isfinite(scale) \
                and scale > 0 and scale != 1:
            entry["clock"] = clock_sentence(float(scale))
        if block.get("clock_foreign") is True:
            entry["clock_foreign"] = "another mod sets the game's clock; Domus leaves it alone."
    if costs:
        entry["decisions"] = [dict(item) for item in costs[-DECISIONS_SHOWN:]]
    return entry or None


class PaceLog(object):
    """The decision costs, kept in the spool: the game time of the newest observation the helper
    sent, the game time of each act that came back from Ashley (pending until the probe pushes
    it), and the cost in game minutes of each act that reached the game."""

    def __init__(self, spool):
        self._spool = spool
        raw = spool.get_kv("pace_log")
        state = json.loads(raw) if raw else {}
        self._decided = state.get("decided") if type(state.get("decided")) is int else None
        self._pending = {str(key): value for key, value in (state.get("pending") or {}).items()
                         if type(value) is int}
        self._costs = [item for item in state.get("costs") or [] if isinstance(item, dict)]

    def _save(self):
        while len(self._pending) > PENDING_KEPT:
            del self._pending[next(iter(self._pending))]
        del self._costs[:-DECISIONS_KEPT]
        self._spool.put_many_kv({"pace_log": json.dumps(
            {"decided": self._decided, "pending": self._pending, "costs": self._costs}, sort_keys=True)})

    def observed(self, ticks):
        """An observation went to Ashley: its game time is what her next act is decided on."""
        if type(ticks) is int and ticks >= 0 and ticks != self._decided:
            self._decided = ticks
            self._save()

    def received(self, act_ids):
        """Acts came back from Ashley: each was decided on the newest observation sent so far."""
        if self._decided is None or not act_ids:
            return
        for act_id in act_ids:
            self._pending.pop(act_id, None)
            self._pending[act_id] = self._decided
        self._save()

    def on_row(self, record):
        """An act_event row. PUSHED is the act reaching the game; its cost is then kept."""
        if not isinstance(record, dict) or record.get("event_kind") != "act_event":
            return
        e2 = record.get("e2") if isinstance(record.get("e2"), dict) else {}
        act_id = e2.get("act_id")
        if e2.get("phase") != "PUSHED" or not isinstance(act_id, str) or act_id not in self._pending:
            return
        game = record.get("game") if isinstance(record.get("game"), dict) else {}
        minutes = game_minutes(self._pending.pop(act_id), game.get("ticks"))
        if minutes is None:
            self._save()
            return
        tuning = e2.get("tuning_name")
        self._costs.append({"interaction": tuning[:80] if isinstance(tuning, str) and tuning else None,
                            "game_minutes": minutes})
        self._save()

    def costs(self):
        return [dict(item) for item in self._costs]
