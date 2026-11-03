"""OPENVULN 2026-11-03 (Domus, probe side): one regression test per finding."""
import json
import os
import time
import unittest

from test_2330_inbox_order import InboxOrderTests, envelope

KEY = bytes(range(32))


class OpenVulnInboxTests(InboxOrderTests):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.root, "cmd", "key"), "w", encoding="ascii") as handle:
            handle.write(KEY.hex())
        self.events = lambda: [row["e2"] for row in self.probe._WRITER.rows if row.get("event_kind") == "command_event"]

    def signed(self, body, key=KEY):
        body = dict(body)
        body["mac"] = self.probe.cmdbox.mac(key, body)
        return body

    def fresh(self, command_id, issuer="helper"):
        now = int(time.time() * 1000)
        body = envelope(command_id, now - 10, now + 20_000)
        body["issuer"] = issuer
        return body

    def reply_of(self, command_id):
        with open(os.path.join(self.root, "cmd", "outbox", command_id + ".json"), "rb") as handle:
            return json.loads(handle.read())

    # F1: issuer attribution is only believed for a command carrying a valid MAC under the shared key.
    def test_f1_an_unsigned_command_is_refused_and_its_issuer_is_not_attributed(self):
        self.drop("forged", self.fresh("1" * 32, issuer="console"), sign=False)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        reply = self.reply_of("1" * 32)
        self.assertEqual((reply["status"], reply["code"], reply["issuer"]), ("REJECTED", "BAD_MAC", None))
        self.assertEqual(self.events(), [])

    def test_f1_a_command_signed_with_another_key_is_refused(self):
        self.drop("forged", self.signed(self.fresh("2" * 32), key=bytes(32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        self.assertEqual(self.reply_of("2" * 32)["code"], "BAD_MAC")

    def test_f1_a_signed_command_runs_and_is_attributed(self):
        self.drop("good", self.signed(self.fresh("3" * 32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, ["3" * 32])
        self.assertEqual([event["issuer"] for event in self.events()], ["helper"])

    def test_f1_without_a_key_file_nothing_runs(self):
        os.remove(os.path.join(self.root, "cmd", "key"))
        self.drop("good", self.signed(self.fresh("4" * 32)))
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        self.assertEqual(self.reply_of("4" * 32)["code"], "BAD_MAC")


del InboxOrderTests

if __name__ == "__main__":
    unittest.main()
