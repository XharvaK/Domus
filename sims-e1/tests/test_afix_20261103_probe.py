"""AU_DOMUS_FULL_2026-11-03 NOTE-3: an expired act is told as an act event only for a valid issuer and a 32-hex
act id, so another writer of the inbox cannot make telemetry claim any act id was refused."""
import time
import unittest

from test_2330_inbox_order import InboxOrderTests, envelope


class ExpiredActEventTests(InboxOrderTests):
    def late_act(self, act_id, issuer="helper"):
        now = int(time.time() * 1000)
        body = envelope("6" * 32, now - 40_000, now - 10_000, command="act",
                        args={"act_id": act_id, "object_id": "1001", "guid64": "14000"})
        body["issuer"] = issuer
        self.drop("late", body)
        self.probe._inbox_tick_body()
        self.assertEqual(self.dispatched, [])
        return self.act_events()

    def test_a_valid_late_act_is_still_told(self):
        self.assertEqual([event["act_id"] for event in self.late_act("b" * 32)], ["b" * 32])

    def test_an_act_id_that_is_not_32_hex_is_not_told(self):
        self.assertEqual(self.late_act("not-an-act-id"), [])
        self.assertEqual(self.late_act("B" * 32), [])
        self.assertEqual(self.late_act("b" * 64), [])

    def test_an_invalid_issuer_is_not_told(self):
        self.assertEqual(self.late_act("b" * 32, issuer="Mallory!"), [])
        self.assertEqual(self.late_act("b" * 32, issuer=None), [])


del InboxOrderTests

if __name__ == "__main__":
    unittest.main()
