"""Attachment health from the probe process and the latest telemetry row."""

# W3h (C9): real time. The probe writes its rows on real-time alarms, so the freshness of a row does not
# depend on the game clock; the same 30 s at slow_time 0.5.
STALE_AFTER_MS = 30_000
SLEEP_GAP_MS = 30_000


class AttachmentMonitor:
    def __init__(self, detected_build=None):
        self.detected_build = detected_build
        self._prev = None

    def observe(self, now_wall_ms, now_mono_ms, process, latest_row):
        sleep = False
        if self._prev is not None:
            wall_delta = now_wall_ms - self._prev[0]
            mono_delta = now_mono_ms - self._prev[1]
            if wall_delta - mono_delta > SLEEP_GAP_MS:
                sleep = True
        self._prev = (now_wall_ms, now_mono_ms)
        mismatch = False
        if isinstance(latest_row, dict) and self.detected_build is not None:
            declared = latest_row.get("sims_build")
            if isinstance(declared, str) and declared != self.detected_build:
                mismatch = True
        if sleep:
            state = "sleep_resume"
        elif mismatch:
            state = "version_mismatch"
        elif process:
            wall = latest_row.get("wall_timestamp_ms") if isinstance(latest_row, dict) else None
            fresh = type(wall) is int and now_wall_ms - wall <= STALE_AFTER_MS
            state = "attached" if fresh else "stale"
        elif isinstance(latest_row, dict) and latest_row.get("close_reason"):
            state = "game_exited"
        else:
            state = "crash_suspected"
        return {"state": state, "telemetry_only": mismatch}
