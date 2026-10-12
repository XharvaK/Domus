"""2.26.0: social talk on the User's screen. Each new social sentence in her portrait (what she is
doing now, and what someone does to her) goes to the probe as one `talk` line, which the game shows
as its own notification. A sentence shows once while it lasts; it can show again after it has been
gone for FORGET_MS. Text only: it changes nothing in the world.

Run: python -m domus_helper.talk on | off | show
"""
import argparse
import json

from .paths import Paths
from .spool import Spool
from .thalamus.observation import _named, _portrait, _seen_memory, _sentence, _sim_names

MIN_GAP_MS = 2_100
FORGET_MS = 60_000
WAITING_MAX = 3
REPLY_WAIT_MS = 10_000  # HELPER3-12: how long a line waits for the probe to answer it
WORDS_MAX = 8
TEXT_MAX = 240
SWITCH_KEY = "talk"


def _line(text):
    """One printable line the probe accepts, or None."""
    if not isinstance(text, str):
        return None
    clean = " ".join("".join(ch if ch >= " " and ch != "\x7f" else " " for ch in text).split())
    if not clean:
        return None
    if len(clean) > TEXT_MAX:
        clean = clean[:TEXT_MAX - 1].rstrip() + "…"
    return clean


def _digits(value):
    value = None if value is None else str(value)
    return value if value is not None and 1 <= len(value) <= 20 and value.isdigit() else None


def sentences(row):
    """(key, text, sim_id) for each social sentence on this body sample: her running acts first,
    then what others do to her. The User reads these lines, so her name stays in them (the portrait
    says "you" for Ashley)."""
    portrait = _portrait(row)
    her = _digits((row.get("body") or {}).get("sim_id"))
    found = []
    for item in portrait.get("doing_said") or []:
        if item.get("state") == "running":
            found.append((item.get("interaction"), item.get("sentence"), her))
    names, her_name = _sim_names(row, set(_seen_memory(row, None).seen_ids))
    for item in portrait.get("addressed_by") or []:
        if item.get("sentence"):
            text = _sentence(item.get("interaction"), [_named(item.get("by"), names), her_name])
            found.append((item.get("interaction"), text, _digits(item.get("by"))))
    out = []
    for interaction, sentence, sim_id in found:
        text = _line(sentence)
        if text is not None:
            out.append(((interaction, text), text, sim_id))
    return out


class Talk:
    def __init__(self, spool, publish, reply=None):
        self._spool = spool
        self._publish = publish
        # HELPER3-12: reply(command_id) is the probe's answer to one command (None while it has not answered).
        self._reply = reply
        self._present = {}
        self._waiting = []
        # W12 (S2): her own words to a Sim, shown before the sentences the portrait waits on; at most a few.
        self._words = []
        self._again = []  # a line the probe refused as TOO_SOON: sent once more, first
        self._sent = None  # the line on its way until the probe answers: {id, queue, item, at_ms, again}
        self._sent_ms = None
        self.last = None

    def say(self, text, sim_id=None):
        """W12 (S2): one line in her name (her words), queued for the same throttle as the sentences; it is dropped
        when talk is off or the game is not live, as they are. Never raises."""
        line = _line(text)
        if line is not None:
            self._words.append((("words", line[:32]), line, _digits(sim_id)))
            del self._words[:-WORDS_MAX]

    def on_row(self, record, now_ms, body_sample):
        if not body_sample or not isinstance(record, dict):
            return
        try:
            found = sentences(record)
        except Exception:
            return
        for key, text, sim_id in found:
            if key not in self._present:
                self._waiting.append((key, text, sim_id))
            self._present[key] = now_ms
        for key in [key for key, seen in self._present.items() if now_ms - seen > FORGET_MS]:
            del self._present[key]
        del self._waiting[:-WAITING_MAX]

    def _answered(self, now_ms):
        """HELPER3-12: whether the line on its way is done. The probe's TALK_REJECT TOO_SOON puts the line back once, first in
        line. A line with no answer after REPLY_WAIT_MS is done; so is every line when there is no reply reader."""
        sent = self._sent
        if sent["id"] is None or self._reply is None:
            self._sent = None
            return True
        reply = self._reply(sent["id"])
        if reply is None:
            if now_ms - sent["at_ms"] < REPLY_WAIT_MS:
                return False
            self._sent = None
            return True
        self._sent = None
        lines = [str(line) for line in (reply.get("result") or {}).get("lines") or []]
        if (any("TALK_REJECT TOO_SOON" in line for line in lines) or reply.get("code") == "TOO_SOON") and not sent["again"]:
            self._again.insert(0, (sent["item"], sent["queue"]))
        return True

    def tick(self, now_ms, live):
        try:
            if not live or self._spool.get_kv(SWITCH_KEY) == "off":
                self._waiting.clear()
                self._words.clear()
                self._again.clear()
                self._sent = None
                return None
            if self._sent is not None and not self._answered(now_ms):
                return None
            if not self._waiting and not self._words and not self._again:
                return None
            if self._sent_ms is not None and now_ms - self._sent_ms < MIN_GAP_MS:
                return None
            again = bool(self._again)
            if again:
                (key, text, sim_id), queue = self._again.pop(0)
            elif self._words:
                (key, text, sim_id), queue = self._words.pop(0), "words"
            else:
                (key, text, sim_id), queue = self._waiting.pop(0), "waiting"
            args = {"text": text}
            if sim_id is not None:
                args["sim_id"] = sim_id
            try:
                command_id = self._publish("talk", args)
            except (OSError, ValueError):
                self.last = "publish failed"
                return None
            self._sent_ms = now_ms
            self._sent = {"id": command_id, "queue": queue, "item": (key, text, sim_id), "at_ms": now_ms, "again": again}
            self.last = "talk %s" % (key[0],)
            return text
        except Exception:
            return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.talk")
    parser.add_argument("state", choices=["on", "off", "show"])
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    spool = Spool(paths.data_dir / "spool.db")
    try:
        if args.state != "show":
            spool.put_kv(SWITCH_KEY, args.state)
        switch = "off" if spool.get_kv(SWITCH_KEY) == "off" else "on"
        print(json.dumps({"switch": switch}))
        return 0
    finally:
        spool.close()


if __name__ == "__main__":
    raise SystemExit(main())
