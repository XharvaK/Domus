"""E5: the camera director. While the overlay is live and nobody has touched the mouse or keyboard
for IDLE_MS, the camera follows her Sim, and cuts for HOLD_MS to what already draws her attention:
the object of an action she just started, or a Sim who just came onto her lot. The User's hand always
wins: while input is recent nothing is sent. It moves only the view.

Run: python -m domus_helper.director on | off | show
"""
import argparse
import ctypes
import json
from ctypes import wintypes

from .paths import Paths
from .spool import Spool

IDLE_MS = 3_000
HOLD_MS = 8_000
MIN_GAP_MS = 2_000
SEEN_FORGET_MS = 30 * 60_000
SWITCH_KEY = "director"


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_ms():
    """Milliseconds since the last mouse or keyboard input anywhere on this PC; None if unknown."""
    try:
        info = _LastInput()
        info.cbSize = ctypes.sizeof(_LastInput)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    except (AttributeError, OSError):
        return None


def _digits(value):
    return (type(value) is str and 1 <= len(value) <= 20 and
            all(ch in "0123456789" for ch in value))


class Director:
    def __init__(self, spool, publish, idle=idle_ms):
        self._spool = spool
        self._publish = publish
        self._idle = idle
        self._her = None
        self._seen = {}
        self._cut = None
        self._sent = None
        self._sent_ms = None
        self._was_idle = False
        self._booted = False
        self.last = None

    def on_row(self, record, now_ms):
        if not isinstance(record, dict):
            return
        kind = record.get("event_kind")
        if kind == "presence_snapshot":
            sim_id = (record.get("body") or {}).get("sim_id")
            if sim_id is not None:
                self._her = str(sim_id)
            first = not self._booted
            self._booted = True
            for item in record.get("presence") or []:
                if not isinstance(item, dict) or "id" not in item or item.get("is_body"):
                    continue
                if item.get("on_lot") is not True:
                    continue
                sid = str(item["id"])
                previous = self._seen.get(sid)
                fresh = previous is None or now_ms - previous > SEEN_FORGET_MS
                if not first and fresh:
                    self._cut = ("follow_sim", sid, now_ms + HOLD_MS)
                self._seen[sid] = now_ms
            while len(self._seen) > 64:
                oldest = min(self._seen, key=self._seen.get)
                del self._seen[oldest]
        elif kind == "act_event":
            body = record.get("e2") or {}
            object_id = body.get("object_id")
            if body.get("phase") == "PUSHED" and _digits(object_id):
                self._cut = ("focus_object", object_id, now_ms + HOLD_MS)

    def tick(self, now_ms, live):
        try:
            enabled = self._spool.get_kv(SWITCH_KEY) != "off"
            if not live or not enabled or self._her is None:
                self._was_idle = False
                return None
            quiet = self._idle()
            if quiet is None or quiet < IDLE_MS:
                self._was_idle = False
                return None
            if self._cut is not None and now_ms < self._cut[2]:
                target = self._cut[:2]
            else:
                self._cut = None
                target = ("follow_sim", self._her)
            sent = None
            due = not self._was_idle or target != self._sent
            gap = self._sent_ms is None or now_ms - self._sent_ms >= MIN_GAP_MS
            if due and gap:
                try:
                    self._publish("camera", {"op": target[0], "target_id": target[1]})
                    self._sent, self._sent_ms = target, now_ms
                    self.last = "camera %s %s" % target
                    sent = target
                except (OSError, ValueError):
                    self.last = "publish failed"
            self._was_idle = True
            return sent
        except Exception:
            self._was_idle = False
            return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.director")
    parser.add_argument("state", choices=["on", "off", "show"])
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    spool = Spool(paths.data_dir / "spool.db")
    try:
        if args.state != "show":
            spool.put_kv(SWITCH_KEY, args.state)
        switch = "off" if spool.get_kv(SWITCH_KEY) == "off" else "on"
        print(json.dumps({"switch": switch, "idle_ms": idle_ms()}))
        return 0
    finally:
        spool.close()


if __name__ == "__main__":
    raise SystemExit(main())
