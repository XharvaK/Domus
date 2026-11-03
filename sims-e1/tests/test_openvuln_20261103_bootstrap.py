"""OPENVULN F7 (2026-11-03): a wrong-typed entry at cmd, cmd/inbox, cmd/outbox or cmd/done never stops the pump in
silence. It is moved aside and the folder made; when that cannot be done the status says so."""
import os
import unittest
from unittest import mock

from test_binding import load_probe


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        _, self.p, _ = load_probe()
        self.root = self.p._TELEMETRY_ROOT

    def plant_file(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("planted")
        return path

    def aside(self, folder, name):
        return [entry for entry in os.listdir(folder) if entry.startswith(name + ".misplaced-")]

    def test_a_file_at_cmd_outbox_is_moved_aside_and_the_pump_starts(self):
        self.plant_file("cmd", "outbox")
        self.assertTrue(self.p._start_inbox_pump())
        self.assertTrue(os.path.isdir(os.path.join(self.root, "cmd", "outbox")))
        self.assertEqual(len(self.aside(os.path.join(self.root, "cmd"), "outbox")), 1)

    def test_a_file_at_cmd_is_moved_aside_and_the_pump_starts(self):
        self.plant_file("cmd")
        self.assertTrue(self.p._start_inbox_pump())
        for part in ("inbox", "outbox", "done"):
            self.assertTrue(os.path.isdir(os.path.join(self.root, "cmd", part)))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks")
    def test_a_link_to_a_file_at_cmd_inbox_is_moved_aside(self):
        target = self.plant_file("elsewhere")
        os.makedirs(os.path.join(self.root, "cmd"))
        os.symlink(target, os.path.join(self.root, "cmd", "inbox"))
        self.assertTrue(self.p._start_inbox_pump())
        self.assertTrue(os.path.isdir(os.path.join(self.root, "cmd", "inbox")))
        self.assertFalse(os.path.islink(os.path.join(self.root, "cmd", "inbox")))
        self.assertTrue(os.path.isfile(target))

    def test_when_it_cannot_be_moved_the_status_says_so(self):
        self.plant_file("cmd", "done")
        with mock.patch.object(self.p.os, "replace", side_effect=OSError("locked")):
            self.assertFalse(self.p._start_inbox_pump())
        self.assertEqual(self.p._inbox_status().get("inbox_autostart"), "CMD_PATH_BLOCKED")


if __name__ == "__main__":
    unittest.main()
