"""2.33.0 (A9-11): the inbox reads the oldest command first, by when it was issued, not by its random name; and an act
that came too late is refused as an act (act_event REJECTED, code EXPIRED), so Ashley hears it, not only the reply."""
import json
import os
import tempfile
import time
import unittest

from test_binding import FakeWriter, load_probe

def envelope(command_id, issued, expires, command="status", args=None):
    return {"v": 1, "id": command_id, "issued_at_ms": issued, "expires_at_ms": expires,
            "issuer": "helper", "command": command, "args": {} if args is None else args}


class InboxOrderTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        self.root = tempfile.mkdtemp()
        for part in ("inbox", "done", "outbox"):
            os.makedirs(os.path.join(self.root, "cmd", part))
        self.probe._TELEMETRY_ROOT = self.root
        self.probe._TELEMETRY_SESSION_ID = "a" * 32
        self.probe._WRITER = FakeWriter(self.root, "a" * 32, self.probe.schema.PROBE_VERSION, "1.0")
        self.probe._WRITER_IDLE = False
        self.probe._INBOX_USED_IDS.clear()
        self.dispatched = []

        def dispatch(cmd, connection):
            self.dispatched.append(cmd["id"])
            return True

        self.probe._inbox_dispatch = dispatch

    def drop(self, name, body):
        with open(os.path.join(self.root, "cmd", "inbox", name + ".json"), "w", encoding="utf-8") as handle:
            json.dump(body, handle)

    def replies(self):
        folder = os.path.join(self.root, "cmd", "outbox")
        found = []
        for name in sorted(os.listdir(folder)):
            with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
                body = json.load(handle)
            found.append((body.get("status"), body.get("code")))
        return found

    def act_events(self):
        return [row["e2"] for row in self.probe._WRITER.rows if row.get("event_kind") == "act_event"]

    def test_the_oldest_command_by_issue_time_goes_first_not_the_lowest_name(self):
        now = int(time.time() * 1000)
        ids = {name: str(index) * 32 for index, name in enumerate("abcde", start=1)}
        issued = {"a": now - 100, "b": now - 200, "c": now - 300, "d": now - 400, "e": now - 500}
        for name in "abcde":
            self.drop(name, envelope(ids[name], issued[name], issued[name] + 20_000))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [ids["e"], ids["d"], ids["c"], ids["b"]], self.replies())
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched[-1], ids["a"])

    def test_an_act_that_came_too_late_is_refused_as_an_act_and_never_sent(self):
        act_id = "a" * 32
        now = int(time.time() * 1000)
        self.drop("late", envelope("6" * 32, now - 40_000, now - 10_000, command="act",
                                   args={"act_id": act_id, "object_id": "1001", "guid64": "14000"}))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        events = self.act_events()
        self.assertEqual([(event["act_id"], event["phase"], event["code"]) for event in events], [(act_id, "REJECTED", "EXPIRED")])
        self.probe.schema.validate_record(self.probe._WRITER.rows[-1])


if __name__ == "__main__":
    unittest.main()
