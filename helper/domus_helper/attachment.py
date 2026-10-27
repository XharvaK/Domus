"""Attachment health from the probe process and the latest telemetry row."""

# W3h (C9): real time. The probe writes its rows on real-time alarms, so the freshness of a row does not
# depend on the game clock; the same 30 s at slow_time 0.5.
STALE_AFTER_MS = 30_000
SLEEP_GAP_MS = 30_000


def read_probe(row, now_wall_ms):
    """C1b (Owner 2026-10-26): True when a fresh body sample carries needs, False when a fresh one has none, None for
    any other row. It reads only fields the probe already writes; no game API is called."""
    if not isinstance(row, dict) or row.get("event_kind") != "presence_snapshot" or "motives" not in row:
        return None
    wall = row.get("wall_timestamp_ms")
    if type(wall) is not int or now_wall_ms - wall > STALE_AFTER_MS:
        return None
    motives = row.get("motives")
    return isinstance(motives, list) and len(motives) > 0


class AttachmentMonitor:
    def __init__(self, detected_build=None):
        self.detected_build = detected_build
        self._prev = None
        # C1b: the declared build on which the read probe last passed, or None (blocked).
        self._probe_passed = None

    def observe(self, now_wall_ms, now_mono_ms, process, latest_row):
        sleep = False
        if self._prev is not None:
            wall_delta = now_wall_ms - self._prev[0]
            mono_delta = now_mono_ms - self._prev[1]
            if wall_delta - mono_delta > SLEEP_GAP_MS:
                sleep = True
        self._prev = (now_wall_ms, now_mono_ms)
        mismatch = False
        declared = None
        if isinstance(latest_row, dict) and self.detected_build is not None:
            declared = latest_row.get("sims_build")
            if isinstance(declared, str) and declared != self.detected_build:
                mismatch = True
        # C1b: on a build mismatch the reads are put to the test. A fresh body sample with needs lets actuation go on
        # with the new build; one without needs blocks again. Until a sample passes, the mismatch blocks as before.
        override_new = False
        if mismatch:
            probe = read_probe(latest_row, now_wall_ms)
            if probe is True and self._probe_passed != declared:
                self._probe_passed = declared
                override_new = True
            elif probe is False:
                self._probe_passed = None
        blocked = mismatch and self._probe_passed != declared
        if sleep:
            state = "sleep_resume"
        elif blocked:
            state = "version_mismatch"
        elif process:
            wall = latest_row.get("wall_timestamp_ms") if isinstance(latest_row, dict) else None
            fresh = type(wall) is int and now_wall_ms - wall <= STALE_AFTER_MS
            state = "attached" if fresh else "stale"
        elif isinstance(latest_row, dict) and latest_row.get("close_reason"):
            state = "game_exited"
        else:
            state = "crash_suspected"
        result = {"state": state, "telemetry_only": blocked}
        if mismatch and not blocked:
            result["build_override"] = {"declared": declared, "detected": self.detected_build}
            if override_new:
                result["build_override_new"] = True
        return result
