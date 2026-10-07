"""2.24.0: an act her Thought marked as asked for by the User is pushed at Critical, and a
pushed act's end says whether the game ever began it."""
import json
import types
import unittest

import test_2160_act as acts
from test_e2 import CHAIR

GUID = acts.GUID
ACT = acts.ACT


class OwnerActTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.schema = self.probe.schema

    def tearDown(self):
        self.case.tearDown()

    def _act(self, owner):
        args = {"act_id": ACT, "object_id": CHAIR, "guid64": GUID}
        if owner is not None:
            args["owner"] = owner
        connection = self.probe._InboxReply("helper")
        return self.probe._inbox_dispatch({"command": "act", "args": args}, connection)

    def _capture(self):
        captured = []
        original = self.case.base.sim.push_super_affordance

        def capture(affordance, target, context):
            result = original(affordance, target, context)
            captured.append((context, result.execute_result.interaction))
            return result

        self.case.base.sim.push_super_affordance = capture
        return captured

    def test_version(self):
        self.assertEqual(self.probe.schema.PROBE_VERSION, "2.24.0")

    def test_an_owner_act_goes_in_at_critical_and_says_so(self):
        self.case.ready()
        captured = self._capture()
        self.assertTrue(self._act(True))
        self.assertEqual(captured[-1][0].priority, "Critical")
        accepted = [e for e in self.case.events() if e["phase"] == "ACCEPTED"][-1]
        self.assertIs(accepted["owner"], True)
        for row in self.case.base.rows("act_event"):
            self.schema.validate_record(row)

    def test_her_own_act_stays_high(self):
        self.case.ready()
        captured = self._capture()
        self.assertTrue(self._act(None))
        self.assertEqual(captured[-1][0].priority, "High")
        accepted = [e for e in self.case.events() if e["phase"] == "ACCEPTED"][-1]
        self.assertIs(accepted["owner"], False)

    def test_the_wire_takes_owner_only_as_true(self):
        cmdbox = self.probe.cmdbox
        for owner, good in ((True, True), (False, False), ("yes", False), (1, False)):
            raw = json.dumps({"v": 1, "id": "b" * 32, "issued_at_ms": 1, "expires_at_ms": 2, "issuer": "helper",
                              "command": "act", "args": {"act_id": ACT, "object_id": CHAIR, "guid64": GUID,
                                                         "owner": owner}}).encode()
            cmd, code = cmdbox.parse(raw, 1, set())
            self.assertEqual(code is None, good, owner)

    def _finish(self, start_time):
        self.case.ready()
        captured = self._capture()
        self.assertTrue(self._act(None))
        interaction = captured[-1][1]
        if start_time is not _RAISE:
            interaction.start_time = start_time
        interaction.finishing_type = "FinishingType.INTERACTION_INCOMPATIBILITY"
        interaction.callbacks[0](interaction)
        last = self.case.events()[-1]
        self.assertEqual(last["phase"], "FINISHED")
        for row in self.case.base.rows("act_event"):
            self.schema.validate_record(row)
        return last["started"]

    def test_an_act_that_never_began_says_so(self):
        self.assertIs(self._finish(None), False)

    def test_an_act_that_ran_says_so(self):
        self.assertIs(self._finish(123456), True)

    def test_an_unreadable_start_is_unknown(self):
        self.assertIsNone(self._finish(_RAISE))

    def test_schema_takes_owner_and_started_as_bools_and_fills_older_rows(self):
        def row(**extra):
            payload = {"act_id": "a" * 32, "phase": "FINISHED", "code": None, "object_id": "11", "guid64": "4242",
                       "interaction_id": "7", "tuning_name": "ReadBook", "finishing_type": "FinishingType.NATURAL",
                       "detail": None}
            payload.update(extra)
            return self.schema.make_record("act_event", telemetry_session_id="u", wall_timestamp_ms=1,
                                           monotonic_ns=1, e2=payload)

        older = row()
        self.schema.validate_record(older)
        self.assertIsNone(older["e2"]["owner"])
        self.assertIsNone(older["e2"]["started"])
        self.schema.validate_record(row(started=False, owner=True))
        for bad in ({"started": "no"}, {"owner": 1}):
            with self.assertRaises(self.schema.SchemaError):
                self.schema.validate_record(row(**bad))


_RAISE = object()

if __name__ == "__main__":
    unittest.main()
