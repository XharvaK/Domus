"""DA6C failure classes: window cleanup, refusals, preflight, family, interrupt."""
import json
import os
import types
import unittest

import test_e2
from test_da6a_trial import GUID, WatchTV, _Offer, _running
from test_e2 import CHAIR, PIE

DISH = "744245394127586618"


class _Reason(object):
    def __init__(self, text):
        self.text = text

    def __bool__(self):
        return False

    def __str__(self):
        return self.text


class _Refused(object):
    def __init__(self, text):
        self.test_result = _Reason(text)
        self.execute_result = None

    def __bool__(self):
        return False


class FoodPicker(object):
    guid64 = 77


class bed_Nap(object):
    guid64 = 88


class upgrade_Stove(object):
    guid64 = 99


class _Host(object):
    def __init__(self):
        from test_da6a_trial import TrialCommandTests
        self.host = TrialCommandTests()
        self.host.setUp()
        self.base = self.host.base
        self.probe = self.host.probe

    def close(self):
        self.host.tearDown()

    def ready(self, name="LAB_E1_FORK"):
        self.host.ready(name)

    def trial(self, object_id=CHAIR, guid64=GUID):
        return self.host.trial(object_id, guid64)

    def e2(self):
        return self.host.e2()


class Hosted(unittest.TestCase):
    def setUp(self):
        self.box = _Host()
        self.base = self.box.base
        self.probe = self.box.probe

    def tearDown(self):
        self.box.close()

    def ready(self, name="LAB_E1_FORK"):
        self.box.ready(name)

    def trial(self, object_id=CHAIR, guid64=GUID):
        return self.box.trial(object_id, guid64)

    def e2(self):
        return self.box.e2()


class FailureClassTests(Hosted):
    def _clock(self):
        mono = {"n": 5_000_000_000}

        def now():
            return mono["n"]

        self.probe.observers._monotonic_ns = now
        self.probe.e2_control.time.perf_counter_ns = now
        return mono

    def _verdict(self):
        return [row for row in self.e2() if row["phase"] == "VERDICT"][-1]

    def test_f1_window_close_cleans_up_without_stop(self):
        self.ready()
        mono = self._clock()
        self.assertTrue(self.trial()[0])
        pushed = list(self.probe._E2.experiments.values())[-1].interaction_ref
        self.base.sim.si_state = [_running(777, "InteractionSource.SCRIPT_WITH_USER_INTENT")]
        self.base.tick()
        mono["n"] += int(180e9)
        self.base.tick()
        self.assertFalse(any(row["phase"] == "VERDICT" for row in self.e2()[:-2]))
        events = self.e2()
        self.assertEqual(events[-2]["phase"], "VERDICT")
        self.assertEqual(events[-1]["phase"], "TRIAL_CLEANUP")
        self.assertEqual(pushed.cancels, [("FinishingType.USER_CANCEL", "ashley_e2_trial_end")])

    def test_f2_test_refusal_does_not_latch_storm(self):
        self.ready()
        reason = "skill level not in desired range"

        def refuse(affordance, target, context):
            self.base.pushes.append((affordance.guid64, target.id, context))
            return _Refused(reason)

        self.base.sim.push_super_affordance = refuse
        for _ in range(5):
            ok, connection = self.trial()
            self.assertFalse(ok)
            self.assertEqual(connection.lines[-1], "PUSH_REFUSED %s" % reason)
        ok, connection = self.trial()
        self.assertNotEqual(connection.lines[-1], "TRIAL_REJECT TRIAL_STORM")
        self.assertEqual(connection.lines[-1], "PUSH_REFUSED %s" % reason)
        self.assertEqual(self.e2()[-1]["phase"], "PUSH_REFUSED")

        def fail(affordance, target, context):
            self.base.pushes.append((affordance.guid64, target.id, context))
            return test_e2._EnqueueResult(False, test_e2._Interaction(777))

        self.base.sim.push_super_affordance = fail
        for _ in range(5):
            self.assertEqual(self.trial()[1].lines[-1], "PUSH_FAILED")
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT TRIAL_STORM")

    def test_f4_natural_finish_passes_only_after_attributed(self):
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        self.base.sim.si_state = [_running(777, "InteractionSource.SCRIPT_WITH_USER_INTENT")]
        self.base.tick()
        experiment.interaction_ref.finishing_type = "FinishingType.NATURAL"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.assertTrue(self.probe._cmd_stop())
        verdict = self._verdict()
        self.assertEqual(verdict["code"], "PASS")
        self.assertIn("family=0", verdict["detail"])

        self.base.sim.si_state = []
        self.base.sim.queue = []
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        experiment.interaction_ref.finishing_type = "FinishingType.NATURAL"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.assertTrue(self.probe._cmd_stop())
        self.assertEqual(self._verdict()["code"], "OUTCOME_UNKNOWN")

    def test_f5_script_child_passes_and_pie_or_reaction_stay_foreign(self):
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        experiment.interaction_ref.finishing_type = "FinishingType.NATURAL"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.base.sim.si_state = [_running(862, "InteractionSource.SCRIPT_WITH_USER_INTENT", DISH)]
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        verdict = self._verdict()
        self.assertEqual(verdict["code"], "PASS")
        self.assertIn("family=1", verdict["detail"])
        self.assertIn("foreign_roots=0", verdict["detail"])

        self.base.sim.si_state = []
        self.base.sim.queue = []
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        experiment.interaction_ref.finishing_type = "FinishingType.NATURAL"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.base.sim.si_state = [_running(50, PIE, DISH)]
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        self.assertEqual(self._verdict()["code"], "OUTCOME_UNKNOWN")

        self.base.sim.si_state = []
        self.base.sim.queue = []
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        experiment.interaction_ref.finishing_type = "FinishingType.NATURAL"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.base.sim.si_state = [_running(51, "InteractionSource.REACTION", DISH)]
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        self.assertEqual(self._verdict()["code"], "OUTCOME_UNKNOWN")

    def test_f6_incompatibility_before_attributed_is_interrupted(self):
        self.ready()
        self._clock()
        self.assertTrue(self.trial()[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        experiment.interaction_ref.finishing_type = "FinishingType.INTERACTION_INCOMPATIBILITY"
        experiment.interaction_ref.callbacks[0](experiment.interaction_ref)
        self.base.sim.si_state = [_running(900, "InteractionSource.AUTONOMY", DISH)]
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        verdict = self._verdict()
        self.assertEqual(verdict["code"], "INTERRUPTED")
        self.assertIn("interrupted=FinishingType.INTERACTION_INCOMPATIBILITY", verdict["detail"])


class _Obj(object):
    def __init__(self, object_id):
        self.id = int(object_id)


class _Stove(_Obj):
    _super_affordances = (bed_Nap, FoodPicker, upgrade_Stove)


class _Fridge(_Obj):
    _super_affordances = (bed_Nap,)


class PreflightTests(Hosted):
    def _manager(self, mapping):
        manager = types.SimpleNamespace(_objects=dict(mapping), get=lambda oid: None)
        self.probe._services_module.object_manager = lambda: manager
        return manager

    def _preflight(self):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": "preflight", "args": {}}, connection)
        return ok, connection

    def test_f3_preflight_rows_and_refusal_gates(self):
        ok, connection = self._preflight()
        self.assertFalse(ok)
        self.assertEqual(connection.code, "PREFLIGHT_UNARMED")

        self.ready()
        self.probe._cmd_calibrate()
        ok, connection = self._preflight()
        self.assertFalse(ok)
        self.assertEqual(connection.code, "CALIBRATE_OBSERVE_ONLY")
        self.probe._cmd_stop()
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()

        self.probe._STATE = "ARMED"
        self.probe._ARMED_NAME = "OTHER"
        ok, connection = self._preflight()
        self.assertFalse(ok)
        self.assertEqual(connection.code, "PREFLIGHT_NOT_LAB")
        self.probe._STATE = "UNARMED"
        self.probe._ARMED_NAME = None

        self.ready()
        self.assertTrue(self.probe._start_inbox_pump("import"))
        calls = []

        def test_affordance(affordance, obj, context):
            calls.append(affordance.__name__)
            if affordance.__name__ == "upgrade_Stove":
                return _Reason("Object failed state check")
            return True

        self.base.sim.test_super_affordance = test_affordance
        stove = _Stove(CHAIR)
        fridge = _Fridge("118245043789434088")
        self._manager({stove.id: stove, fridge.id: fridge})
        scan_cls = self.probe.preflight.PreflightScan
        original = scan_cls.__init__

        def capped(this, *args, **kwargs):
            kwargs["max_per_chunk"] = 1
            original(this, *args, **kwargs)

        scan_cls.__init__ = capped
        try:
            ok, connection = self._preflight()
            self.assertTrue(ok, connection.code)
            scan = self.probe._PREFLIGHT
            self.assertTrue(os.path.isfile(scan.partial))
            self.assertFalse(os.path.isfile(scan.out_path))
            while scan.state == "running":
                self.probe._preflight_tick()
        finally:
            scan_cls.__init__ = original
        with open(scan.out_path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(rows[0]["kind"], "preflight_header")
        self.assertEqual(rows[-1]["kind"], "preflight_footer")
        body = [row for row in rows if row["kind"] == "preflight"]
        by_key = {(row["object_id"], row["name"]): row for row in body}
        self.assertTrue(by_key[(CHAIR, "bed_Nap")]["ok"])
        self.assertFalse(by_key[(CHAIR, "FoodPicker")]["ok"])
        self.assertEqual(by_key[(CHAIR, "FoodPicker")]["reason"], "picker")
        self.assertFalse(by_key[(CHAIR, "upgrade_Stove")]["ok"])
        self.assertIn("state check", by_key[(CHAIR, "upgrade_Stove")]["reason"])
        self.assertNotIn("FoodPicker", calls)
        self.assertFalse(os.path.isfile(scan.partial))


if __name__ == "__main__":
    unittest.main()
