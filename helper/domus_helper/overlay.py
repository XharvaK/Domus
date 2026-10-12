"""E3: the overlay. Local pages for a capture tool, served on this PC only (127.0.0.1).

What the pages show is put together here from two sources:
- her body as the probe reports it: needs, mood, moodlets, the game clock, and what her body is
  doing, each marked by whose hand started it (her choice, her body's reflex, the game, or a
  human at the controls);
- the lines she chose to put on the overlay, from Ashley's overlay feed. Each is stamped
  `inputs: "chosen"`; anything else is refused and counted. The feed is polled whatever the old
  game-only switch says (O1): that switch no longer decides what reaches the pages.

A line that matches the User's privacy list (`overlay_privacy.txt` in the data folder, one
name or place per line) is held: "..." is shown instead. Names of other Sims in the save are
learned from telemetry and held the same way (`overlay_save_names.json`); her own Sim is exempt.
Ashley holds her own lines too; this is the second, local line.

Run: python -m domus_helper.overlay curtain on | off | show
Run: python -m domus_helper.overlay show
"""
import argparse
import json
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import inputs as game_inputs
from . import obs, proof
from .acts import humanize
from .overlay_page import PAGE
from .paths import Paths
from .spool import Spool
from .thalamus.observation import _affordance_name, game_time

PORT = 47213
FEED_EVERY_MS = 8_000
# A human touch (a click that queued something, a pop-up answered by hand, a helper restart)
# keeps the label up this long.
HUMAN_HAND_MS = 120_000
PRIVACY_FILE = "overlay_privacy.txt"
SAVE_NAMES_FILE = "overlay_save_names.json"
SAVE_NAMES_EVERY_MS = 60_000
CURTAIN_KEY = "overlay_curtain"
# HELPER3-5/20 (R3-H): the pass ids she has said, kept in the spool across restarts; the passes seen in this process are capped.
SAID_KEY = "overlay_said"
SAID_LIMIT = 200
PASSES_SEEN_LIMIT = 2000
THOUGHTS_LIMIT = 8
PASSES_SHOWN = 6
# O1: the one stamp a feed line may carry; she chose to show it.
CHOSEN = "chosen"
# W14 (S4): at the first feed read after a start, a chosen line older than this is not shown in the game.
THOUGHT_OLD_MS = 2 * 60_000
DOING_SHOWN = 4
MOODLETS_SHOWN = 4
HELD = "…"
NEEDS = ("hunger", "energy", "bladder", "hygiene", "fun", "social")
# Whose hand started an interaction, from the game's own InteractionSource.
_BY = {
    "InteractionSource.PIE_MENU": "human",
    "InteractionSource.AUTONOMY": "body",
    "InteractionSource.BODY_CANCEL_AOP": "body",
    "InteractionSource.SCRIPT": "game",
    "InteractionSource.REACTION": "game",
}
_NOT_SHOWN = ("InteractionSource.POSTURE_GRAPH",)
_IDLE = ("sim-stand", "stand_Passive")
_NO_ANSWER = (None, "closed", "no_response")
_MECHANICAL = (re.compile(r"<[@#][!&]?\d+>"), re.compile(r"(^|[^\w])@[A-Za-z0-9_.]{2,}"),
               re.compile(r"\d{15,}"), re.compile(r"https?://", re.I),
               re.compile(r"discord(app)?\.(com|gg)", re.I))
_LIMIT = 64


class PrivacyList:
    """The User's own list of names and places that never appear, reread when the file changes."""

    def __init__(self, path):
        self._path = path
        self._stamp = None
        self._terms = []
        self._missing = False

    def missing(self):
        """HE18: the User has not written the list. Nothing is invented in its place; the screen says so."""
        self._load()
        return self._missing

    def _load(self):
        try:
            stamp = self._path.stat().st_mtime_ns
        except OSError:
            self._stamp, self._terms, self._missing = None, [], True
            return
        self._missing = False
        if stamp == self._stamp:
            return
        self._stamp = stamp
        terms = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            term = line.strip()
            if len(term) >= 2 and not term.startswith("#"):
                terms.append(re.compile(r"(?<!\w)%s(?!\w)" % re.escape(term), re.I))
        self._terms = terms

    def held(self, text):
        if not isinstance(text, str):
            return False
        self._load()
        return any(pattern.search(text) for pattern in _MECHANICAL + tuple(self._terms))


def _name_pieces(text):
    """Full name, then each word, when the piece is at least 3 characters."""
    if not isinstance(text, str):
        return []
    text = " ".join(text.split())
    if len(text) < 3:
        return []
    pieces = [text]
    for word in text.split(" "):
        if len(word) >= 3 and word != text:
            pieces.append(word)
    return pieces


def _row_save_names(row):
    """Sim names on a telemetry row. Her own body is public and is not learned.

    The probe sends one presence `name` ('First Last'). That full name, and each
    word of it, is stored when it is at least 3 characters. A separate first name,
    last name, or household name is taken too when the row carries that field."""
    found = []
    for item in (row or {}).get("presence") or []:
        if not isinstance(item, dict) or item.get("is_body"):
            continue
        for key in ("name", "first_name", "last_name", "household_name"):
            found.extend(_name_pieces(item.get(key)))
        household = item.get("household")
        if isinstance(household, dict):
            found.extend(_name_pieces(household.get("name")))
        elif isinstance(household, str):
            found.extend(_name_pieces(household))
    return found


class SaveNames:
    """Names of Sims in the save. Learned from rows, kept in memory, written at most once a minute."""

    def __init__(self, path):
        self._path = path
        self._names = set()
        self._terms = []
        self._dirty = False
        self._written_ms = None
        self._load()

    def _load(self):
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if isinstance(item, str) and len(item.strip()) >= 3:
                self._names.add(item.strip().casefold())
        self._compile()

    def _compile(self):
        self._terms = [re.compile(r"(?<!\w)%s(?!\w)" % re.escape(name), re.I)
                       for name in self._names]

    def learn(self, row, now_ms):
        grew = False
        for name in _row_save_names(row):
            key = name.casefold()
            if key not in self._names:
                self._names.add(key)
                grew = True
        if grew:
            self._compile()
            self._dirty = True
        self._flush(now_ms)

    def _flush(self, now_ms):
        if not self._dirty or type(now_ms) is not int:
            return
        if self._written_ms is not None and now_ms - self._written_ms < SAVE_NAMES_EVERY_MS:
            return
        try:
            self._path.write_text(json.dumps(sorted(self._names)), encoding="utf-8")
        except OSError:
            return
        self._written_ms = now_ms
        self._dirty = False

    def held(self, text):
        if not isinstance(text, str):
            return False
        return any(pattern.search(text) for pattern in self._terms)

    @property
    def count(self):
        return len(self._names)


def curtain(spool):
    return spool.get_kv(CURTAIN_KEY) == "on"


def _day(data_dir, inputs_now, today):
    """Day N: the days the switch was game-only, counted from the session log (today included
    while it is on)."""
    days = set()
    try:
        lines = (data_dir / game_inputs.LOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if item.get("inputs") == game_inputs.GAME_ONLY and type(item.get("at_ms")) is int:
            days.add(datetime.fromtimestamp(item["at_ms"] / 1000).date())
    if inputs_now == game_inputs.GAME_ONLY:
        days.add(today)
    return len(days) or None


def _clock(calendar):
    time_ = game_time(calendar)
    if time_ is None:
        return None
    return "%s %02d:%02d" % (time_["weekday"], time_["hour"], time_["minute"])


def _young(at_ms, now_ms):
    """W14 (S4): a line written no more than THOUGHT_OLD_MS before now. An unknown time is not young."""
    return type(at_ms) is int and type(now_ms) is int and now_ms - at_ms <= THOUGHT_OLD_MS


class Overlay:
    def __init__(self, spool, data_dir, now_ms, resolve=None, trace=None, helper_build=None):
        self._spool = spool
        # E4: the private proof trace of what was shown, and this helper's own build.
        self._trace = trace
        self._helper_build = helper_build
        self._data_dir = data_dir
        self._resolve = resolve
        # HE1: tuning name -> the game's own words for an act (set by the bridge from the newest menu).
        self.act_name = None
        self._privacy = PrivacyList(data_dir / PRIVACY_FILE)
        self._save_names = SaveNames(data_dir / SAVE_NAMES_FILE)
        self._row = None
        self._open = {}
        self._hers = []
        self._items = []
        # W14 (S4): the passes this helper session has seen (a pass's line is shown in the game once), the lines the
        # bridge takes to say in the game, and whether a feed has been read yet (the first read is the one with a rule).
        self._passes_seen = {}  # insertion-ordered: the oldest is dropped past PASSES_SEEN_LIMIT
        self._thoughts = []
        raw = spool.get_kv(SAID_KEY)
        self._said = list(json.loads(raw)) if raw else []  # the pass ids said, newest last (at most SAID_LIMIT)
        self._fed_once = False
        self._polled_ms = None
        self._feed_ok = None
        self._refused = 0
        # The helper just started: someone at this PC started it.
        self._human_ms = now_ms
        self.published = {"v": 1, "mode": "off"}

    def on_row(self, record, now_ms):
        if not isinstance(record, dict):
            return
        if record.get("event_kind") == "act_event":
            iid = (record.get("e2") or {}).get("interaction_id")
            if isinstance(iid, str) and iid not in self._hers:
                self._hers = (self._hers + [iid])[-_LIMIT:]
            return
        if record.get("event_kind") != "presence_snapshot":
            return
        self._row = record
        self._save_names.learn(record, now_ms)
        dialogs = record.get("dialogs")
        if isinstance(dialogs, dict):
            for item in dialogs.get("open") or []:
                if isinstance(item, dict) and item.get("dialog_id") is not None:
                    self._open[str(item["dialog_id"])] = item.get("auto_respond") is True
            for item in dialogs.get("closed") or []:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("dialog_id"))
                auto = self._open.pop(key, False)
                if item.get("response") not in _NO_ANSWER and not auto and key not in self.answered:
                    self._human_ms = now_ms
            while len(self._open) > _LIMIT:
                self._open.pop(next(iter(self._open)))
        for entry in ((record.get("interactions") or {}).get("observed")) or []:
            if isinstance(entry, dict) and _BY.get(entry.get("source_raw")) == "human":
                self._human_ms = now_ms

    # Dialog ids she answered herself (the act courier fills it when it sends her answer).
    answered = ()
    # E4: whether the capture tool was last asked to keep the recording (False: no settings file).
    kept = None

    def poll(self, client, helper_session, now_ms):
        if client is None or not hasattr(client, "post_feed"):
            return
        if self._polled_ms is not None and now_ms - self._polled_ms < FEED_EVERY_MS:
            return
        self._polled_ms = now_ms
        response = client.post_feed({"v": 1, "helper_session": helper_session})
        self._feed_ok = response is not None
        if response is not None:
            first = not self._fed_once
            self._fed_once = True
            self._items = self._accept(response.get("items"), now_ms, first)
            self._marks(response.get("marks"), now_ms)

    def take_thoughts(self):
        """W14 (S4): the lines she chose since the last take, each once: the bridge says them in the game."""
        lines, self._thoughts = self._thoughts, []
        if curtain(self._spool):
            return []  # User ruling 2026-10-12: the curtain on means nothing of hers shows, in the game either
        return lines

    def _said_now(self, pass_id):
        """HELPER3-5: a pass whose line is said is kept, so a restart does not say it again."""
        self._said = (self._said + [pass_id])[-SAID_LIMIT:]
        self._spool.put_kv(SAID_KEY, json.dumps(self._said))

    def _marks(self, marks, now_ms):
        """E4: a word-watch flag on Ashley's side: logged in the proof ledger once, and the capture
        tool keeps its replay buffer and marks the recording."""
        raw = self._spool.get_kv("overlay_marks_seen")
        seen = json.loads(raw) if raw else []
        new = [item["id"] for item in marks if isinstance(item, dict) and type(item.get("id")) is int
               and item["id"] not in seen] if isinstance(marks, list) else []
        if not new:
            return
        for mark in new:
            proof.ledger(self._spool, self._data_dir, "flagged", "word watch flag %d (review on the host)" % mark,
                         now_ms=now_ms)
        self._spool.put_kv("overlay_marks_seen", json.dumps((seen + new)[-_LIMIT:]))
        self.kept = obs.keep_recording(self._data_dir)

    def _accept(self, items, now_ms=None, first=False):
        accepted = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or item.get("inputs") != CHOSEN:
                self._refused += 1
                continue
            # W14 (S4): a pass this helper session has not seen is seen now, once; its line may be a thought for the game.
            pass_id = item.get("pass")
            new_pass = isinstance(pass_id, str) and bool(pass_id) and pass_id not in self._passes_seen
            if new_pass:
                self._passes_seen[pass_id] = True
                while len(self._passes_seen) > PASSES_SEEN_LIMIT:
                    self._passes_seen.pop(next(iter(self._passes_seen)))  # HELPER3-20
            shown = {"at_ms": item.get("at_ms"), "_pass": item.get("pass"),
                     "_regime": item.get("regime") if isinstance(item.get("regime"), dict) else {}}
            line = item.get("line")
            if item.get("quiet"):
                shown["quiet"] = True
            elif item.get("held") or not isinstance(line, str) or self._held(line):
                shown["held"] = True
            else:
                shown["line"] = line[:400]
                if new_pass and pass_id not in self._said and (not first or _young(item.get("at_ms"), now_ms)):
                    self._thoughts = (self._thoughts + [shown["line"]])[-THOUGHTS_LIMIT:]
                    self._said_now(pass_id)
            act = item.get("act")
            if isinstance(act, dict):
                shown["act"] = {"label": self._label(act.get("label")), "state": str(act.get("state")),
                                "how": act.get("how") if isinstance(act.get("how"), str) else None}
            plan = item.get("plan")
            if isinstance(plan, list):
                shown["plan"] = [{"label": self._label(step.get("label")), "state": str(step.get("state"))}
                                 for step in plan if isinstance(step, dict)]
            accepted.append(shown)
        return accepted[-PASSES_SHOWN:]

    def _label(self, label):
        if not isinstance(label, str) or not label or self._held(label):
            return HELD
        return label[:120]

    def _doing(self, row):
        doing = []
        for entry in ((row.get("interactions") or {}).get("observed")) or []:
            if not isinstance(entry, dict) or entry.get("source_raw") in _NOT_SHOWN:
                continue
            name = _affordance_name(entry.get("affordance_text"))
            if not name or name in _IDLE:
                continue
            by = "her" if entry.get("interaction_id") in self._hers else _BY.get(entry.get("source_raw"))
            text = (self.act_name or humanize)(name)
            doing.append({"text": HELD if self._held(text) else text, "by": by,
                          "queued": entry.get("membership") == "QUEUED"})
        return doing[:DOING_SHOWN]

    def publish(self, now_ms, attached):
        inputs_now = game_inputs.current(self._spool)
        row = self._row or {}
        game = row.get("game") or {}
        today = datetime.fromtimestamp(now_ms / 1000).date()
        card = {"day": _day(self._data_dir, inputs_now, today), "time": _clock(game.get("calendar")),
                "label": "AI-controlled"}
        jobs = ((row.get("self") or {}).get("careers")) or []
        work = next((item for item in jobs if isinstance(item, dict) and item.get("at_work") is True), None)
        if curtain(self._spool) or not attached:
            mode = "curtain"
        elif work is not None:
            mode = "work"
        else:
            mode = "live"
        state = {"v": 1, "mode": mode, "card": card}
        needs = {str(item.get("id")): item for item in row.get("motives") or [] if isinstance(item, dict)}
        mood = row.get("mood") if isinstance(row.get("mood"), dict) else {}
        moodlets = []
        for item in row.get("sim_signals") or []:
            if not isinstance(item, dict) or item.get("kind") != "MOODLET" or item.get("visible") is False:
                continue
            text = None
            if self._resolve is not None and item.get("text_key") is not None:
                try:
                    text = self._resolve(item["text_key"])
                except Exception:
                    text = None
            if isinstance(text, str) and text and not self._held(text):
                moodlets.append({"text": text[:60], "mood": item.get("mood_type")})
        mood_name = mood.get("name") if isinstance(mood.get("name"), str) else None
        state.update({
            "privacy_list": "missing" if self._privacy.missing() else "ok",
            "paused": game.get("paused") is True,
            "needs": [{"need": key, "value": needs[key].get("value"), "band": needs[key].get("band")}
                      for key in NEEDS if key in needs],
            "mood": humanize(re.sub(r"^Mood_", "", mood_name)) if mood_name else None,
            "moodlets": moodlets[:MOODLETS_SHOWN],
            "doing": self._doing(row),
            "human_at_controls": now_ms - self._human_ms < HUMAN_HAND_MS,
            "passes": [{key: value for key, value in item.items() if not key.startswith("_")} for item in self._items],
            "feed": {"ok": self._feed_ok, "refused": self._refused},
        })
        if mode == "live" and self._trace is not None:
            self._seal(state["passes"], row, now_ms)
        if work is not None:
            title = None
            if self._resolve is not None and work.get("title_key") is not None:
                try:
                    title = self._resolve(work["title_key"])
                except Exception:
                    title = None
            state["work"] = {"title": title if isinstance(title, str) and not self._held(title) else None}
        self.published = state
        return state

    def _held(self, text):
        return self._privacy.held(text) or self._save_names.held(text)

    def _seal(self, shown, row, now_ms):
        """E4: a pass goes into the trace the first time it is on screen, as it was shown. Every pass on
        the overlay is one she chose to show (O1), so the regime says so, and no more."""
        probe = row.get("probe_version")
        for item, public in zip(self._items, shown):
            regime = dict(item["_regime"], inputs=CHOSEN, helper_build=self._helper_build,
                          probe_version=probe if isinstance(probe, str) else None)
            try:
                self._trace.shown(item["_pass"], public, regime, now_ms)
            except OSError:
                return


class _Handler(BaseHTTPRequestHandler):
    overlay = None
    port = PORT
    pages = {"/": "main", "/vertical": "vertical", "/curtain": "curtain", "/work": "work"}

    def do_GET(self):
        # Only this PC, by its own name: a page elsewhere can't reach it through DNS rebinding.
        if self.headers.get("Host") not in ("127.0.0.1:%d" % self.port, "localhost:%d" % self.port):
            self._send(403, "text/plain", b"forbidden")
            return
        path = self.path.split("?", 1)[0]
        if path == "/state.json":
            self._send(200, "application/json", json.dumps(self.overlay.published).encode("utf-8"))
        elif path in self.pages:
            self._send(200, "text/html; charset=utf-8", PAGE.replace("__LAYOUT__", self.pages[path]).encode("utf-8"))
        else:
            self._send(404, "text/plain", b"not found")

    def _send(self, status, kind, body):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(overlay, port=PORT):
    """Serve the pages on 127.0.0.1 in a daemon thread. Returns the server, or None if the port
    is taken (another helper already serves them)."""
    handler = type("Handler", (_Handler,), {"overlay": overlay, "port": port})
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        return None
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="overlay", daemon=True).start()
    return server


def _save_name_count(data_dir):
    return SaveNames(data_dir / SAVE_NAMES_FILE).count


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.overlay")
    parser.add_argument("what", choices=["curtain", "show"])
    parser.add_argument("state", nargs="?", choices=["on", "off", "show"])
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    if args.what == "show":
        print(json.dumps({"save_names": _save_name_count(paths.data_dir)}))
        return 0
    if args.state is None:
        parser.error("curtain needs on, off, or show")
    spool = Spool(paths.data_dir / "spool.db")
    try:
        if args.state != "show":
            spool.put_kv(CURTAIN_KEY, args.state)
        shown = {"curtain": "on" if curtain(spool) else "off", "port": PORT,
                 "at_ms": int(time.time() * 1000)}
        if args.state == "show":
            shown["save_names"] = _save_name_count(paths.data_dir)
        print(json.dumps(shown))
        return 0
    finally:
        spool.close()


if __name__ == "__main__":
    raise SystemExit(main())
