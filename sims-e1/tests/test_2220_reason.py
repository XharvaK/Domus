"""2.22.0: when the game refuses her act, the tooltip's string key travels with the refusal."""
import json
import unittest

import test_2160_act as acts
import test_da6c
from test_e2 import CHAIR


class _Tooltip(object):
    def __init__(self, string_id=424242):
        self.calls = 0
        self._string_id = string_id

    def __call__(self):
        self.calls += 1
        return "called"


class _Result(object):
    def __init__(self, tooltip):
        self.tooltip = tooltip

    def __bool__(self):
        return False

    def __str__(self):
        return "debug refusal"


class _Raising(object):
    @property
    def tooltip(self):
        raise RuntimeError("attribute")

    def __bool__(self):
        return False

    def __str__(self):
        return "debug refusal"


class _RefusedPush(object):
    def __init__(self, tooltip):
        self.test_result = _Result(tooltip)
        self.execute_result = None

    def __bool__(self):
        return False


def _closed_over_factory():
    factory = type("Factory", (object,), {"_string_id": 88001})()
    called = []
    tooltip = lambda *_args, **_kwargs: called.append(1) or factory
    return tooltip, called


class ReasonKeyTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.actuator = self.case.probe.e2_actuator
        self.schema = self.case.probe.schema

    def tearDown(self):
        self.case.tearDown()

    def test_refusal_key_reads_a_factory_a_closure_and_never_calls(self):
        tip = _Tooltip()
        self.assertEqual(self.actuator.refusal_key(_Result(tip)), "424242")
        self.assertEqual(tip.calls, 0)
        tooltip, called = _closed_over_factory()
        self.assertEqual(self.actuator.refusal_key(_Result(tooltip)), "88001")
        self.assertEqual(called, [])
        self.assertIsNone(self.actuator.refusal_key(_Raising()))
        self.assertIsNone(self.actuator.refusal_key(_Result(None)))
        self.assertEqual(tip.calls, 0)

    def test_a_refused_push_records_the_key_beside_the_debug_text(self):
        self.case.ready()
        tip = _Tooltip()

        def refuse(affordance, target, context):
            return _RefusedPush(tip)

        self.case.base.sim.push_super_affordance = refuse
        ok, connection = self.case.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT PUSH_REFUSED")
        event = self.case.events()[-1]
        self.assertEqual(event["phase"], "REJECTED")
        self.assertEqual(event["code"], "PUSH_REFUSED")
        self.assertEqual(event["reason_key"], "424242")
        self.assertEqual(event["detail"], "debug refusal")
        self.assertEqual(tip.calls, 0)
        for row in self.case.base.rows("act_event"):
            self.schema.validate_record(row)

    def test_a_preflight_refusal_records_the_same_key(self):
        self.case.ready()
        tip = _Tooltip(88001)
        result = _Result(tip)
        self.case.base.sim.test_super_affordance = lambda *args: result
        ok, connection = self.case.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        event = self.case.events()[-1]
        self.assertEqual((event["code"], event["reason_key"]), ("GAME_REFUSED", "88001"))
        self.assertEqual(self.case.base.pushes, [])
        self.assertEqual(tip.calls, 0)

    def test_schema_accepts_the_key_and_rejects_a_non_string(self):
        self.assertEqual(self.schema.OBSERVATION_SCHEMA_VERSION, 18)

        def row(reason_key="424242", include=True):
            payload = {
                "act_id": "a" * 32, "phase": "REJECTED", "code": "PUSH_REFUSED",
                "object_id": "11", "guid64": "4242", "interaction_id": None,
                "tuning_name": "ReadBook", "finishing_type": None, "detail": "debug refusal",
            }
            if include:
                payload["reason_key"] = reason_key
            return self.schema.make_record(
                "act_event", telemetry_session_id="u", wall_timestamp_ms=1,
                monotonic_ns=1, e2=payload)

        accepted = row()
        self.schema.validate_record(accepted)
        self.assertEqual(accepted["e2"]["reason_key"], "424242")
        older = row(include=False)
        self.schema.validate_record(older)
        self.assertIsNone(older["e2"]["reason_key"])
        for bad in (12, True, ["424242"]):
            with self.assertRaises(self.schema.SchemaError):
                self.schema.validate_record(row(bad))


class PreflightRowTests(test_da6c.Hosted):
    def _manager(self, mapping):
        import types
        manager = types.SimpleNamespace(_objects=dict(mapping), get=lambda oid: None)
        self.probe._services_module.object_manager = lambda: manager
        return manager

    def _preflight(self):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": "preflight", "args": {}}, connection)
        return ok, connection

    def test_a_refused_preflight_row_carries_the_key(self):
        self.ready()
        self.assertTrue(self.probe._start_inbox_pump("import"))
        tip = _Tooltip(88001)

        def test_affordance(affordance, obj, context):
            return _Result(tip)

        self.base.sim.test_super_affordance = test_affordance
        stove = test_da6c._Stove(CHAIR)
        self._manager({stove.id: stove})
        ok, connection = self._preflight()
        self.assertTrue(ok, getattr(connection, "code", connection.lines))
        scan = self.probe._PREFLIGHT
        while scan.state == "running":
            self.probe._preflight_tick()
        with open(scan.out_path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        body = [row for row in rows if row["kind"] == "preflight" and row["name"] == "bed_Nap"]
        self.assertEqual(len(body), 1)
        self.assertFalse(body[0]["ok"])
        self.assertEqual(body[0]["reason_key"], "88001")
        self.assertIn("debug refusal", body[0]["reason"])
        picker = [row for row in rows if row["kind"] == "preflight" and row["name"] == "FoodPicker"]
        self.assertEqual(picker[0]["reason_key"], None)
        self.assertEqual(tip.calls, 0)


if __name__ == "__main__":
    unittest.main()
