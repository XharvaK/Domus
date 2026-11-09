"""D7 (Domus perception 1): a pushed act names what it replaced.

When the push drops a queued or running interaction, the PUSHED row lists each
one's name, whether it was the Sim's own (autonomous), and whether it was queued
or running. Idle and posture acts are left out. Names and ids are invented.
"""
import types
import unittest

import test_2160_act as acts
from test_2160_act import ACT, CHAIR, GUID


class fridge_GrabSnack(object):
    pass


class bookshelf_ReadBook(object):
    pass


def _entry(iid, source, affordance):
    return types.SimpleNamespace(
        id=int(iid),
        affordance=affordance,
        context=types.SimpleNamespace(source=source),
    )


class ReplacedOnPushTests(unittest.TestCase):
    setUp = acts.ActCommandTests.setUp
    tearDown = acts.ActCommandTests.tearDown
    ready = acts.ActCommandTests.ready
    act = acts.ActCommandTests.act
    events = acts.ActCommandTests.events

    def test_a_pushed_act_names_the_queued_autonomous_act_it_replaced(self):
        self.ready()
        stand = type("sim-stand", (object,), {})
        self.base.sim.queue = [_entry(900, "InteractionSource.AUTONOMY", fridge_GrabSnack)]
        self.base.sim.si_state = [
            _entry(800, "InteractionSource.POSTURE_GRAPH", stand),
            _entry(901, "InteractionSource.SCRIPT_WITH_USER_INTENT", bookshelf_ReadBook),
        ]
        original = self.base.sim.push_super_affordance

        def push(affordance, target, context):
            result = original(affordance, target, context)
            self.base.sim.queue = []
            self.base.sim.si_state = [_entry(800, "InteractionSource.POSTURE_GRAPH", stand)]
            return result

        self.base.sim.push_super_affordance = push
        ok, connection = self.act()
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("ACT_PUSHED " + ACT))
        pushed = [row for row in self.events() if row["phase"] == "PUSHED"][-1]
        self.assertEqual(pushed["replaced"], [
            {"name": "fridge_GrabSnack", "autonomous": True, "state": "queued"},
            {"name": "bookshelf_ReadBook", "autonomous": False, "state": "running"},
        ])
        for row in self.base.rows("act_event"):
            self.probe.schema.validate_record(row)

    def test_replaced_is_bounded_and_schema_checked(self):
        schema = self.probe.schema
        self.assertEqual(schema.ACT_MAX_REPLACED, 4)
        payload = {
            "act_id": "a" * 32, "phase": "PUSHED", "code": None, "object_id": "1",
            "guid64": "2", "interaction_id": "3", "tuning_name": "ReadBook",
            "finishing_type": None, "detail": None, "replaced": [
                {"name": "fridge_GrabSnack", "autonomous": True, "state": "queued"},
            ],
        }
        record = schema.make_record(
            "act_event", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload)
        schema.validate_record(record)
        for bad in (
            [{"name": "x" * 129, "autonomous": True, "state": "queued"}],
            [{"name": "x", "autonomous": True, "state": "idle"}],
            [{"name": "x", "autonomous": "yes", "state": "queued"}],
            [{"name": "x", "autonomous": True, "state": "queued"}] * 5,
        ):
            broken = dict(payload, replaced=bad)
            record = schema.make_record(
                "act_event", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=broken)
            with self.assertRaises(schema.SchemaError):
                schema.validate_record(record)


if __name__ == "__main__":
    unittest.main()
