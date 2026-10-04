"""DA6A trial command: one parameter-free affordance, judged by an interaction card."""
import json
import time
import types
import unittest

import test_e2
from test_e2 import CHAIR, PIE, POSTURE, SOFA, _load_pure

GUID = "4242"


class WatchTV(object):
    guid64 = int(GUID)


class SeatPicker(object):
    guid64 = int(GUID)


class Greet(object):
    guid64 = int(GUID)
    is_social = True


class sim_delete_item(object):
    guid64 = int(GUID)


class _Offer:
    def __init__(self, object_id, affordances):
        self.id = int(object_id)
        self._affordances = affordances

    def super_affordances(self, context=None):
        for item in self._affordances:
            yield item


def _running(iid, source, target=CHAIR):
    return types.SimpleNamespace(
        id=int(iid), guid64=1, affordance="x",
        target=types.SimpleNamespace(id=int(target)),
        context=types.SimpleNamespace(source=source))


class TrialCheckTests(unittest.TestCase):
    def setUp(self):
        load = _load_pure()
        self.adm = load[0]
        from ashley_e1 import e2_actuator, e2_trial
        self.trial = e2_trial
        self.actuator = e2_actuator

    def view(self, **overrides):
        view = {
            "sampling": True, "lineage_class": "CONTINUES_LAST_SAVE",
            "designated_sim_id": None, "sim_id": "s", "body_available": True,
            "paused": False, "armed_name": "LAB_E1_FORK", "object_id": CHAIR,
            "excluded_ids": (SOFA,), "own_open_ids": (), "motives": [],
            "entries": [],
            "object": {"exists": True, "offer_count": 1, "excluded": False},
        }
        view.update(overrides)
        return view

    def test_reject_codes_in_admission_order(self):
        T = self.trial
        A = self.adm
        cases = [
            ({"sampling": False}, A.NOT_SAMPLING),
            ({"lineage_class": None}, A.LINEAGE_PENDING),
            ({"lineage_class": "PENDING"}, A.LINEAGE_PENDING),
            ({"lineage_class": "BODY_MISMATCH"}, A.BODY_MISMATCH),
            ({"lineage_class": "ROLLBACK"}, A.LINEAGE_NOT_ADMISSIBLE),
            ({"designated_sim_id": "other"}, A.BODY_MISMATCH),
            ({"sim_id": None}, A.BODY_UNAVAILABLE),
            ({"body_available": False}, A.BODY_UNAVAILABLE),
            ({"object": {"exists": False, "offer_count": 1, "excluded": False}}, A.NO_OBJECT),
            ({"object_id": SOFA}, A.OBJECT_EXCLUDED),
            ({"armed_name": "LAB_E1"}, T.TRIAL_FORK_ONLY),
            ({"object": {"exists": True, "offer_count": 0, "excluded": False}},
             A.AFFORDANCE_NOT_OFFERED),
            ({"object": {"exists": True, "offer_count": 1, "excluded": True}}, T.TRIAL_EXCLUDED),
            ({"motives": [{"band": "ok"}, {"band": "distress"}]}, T.NEED_DISTRESS),
            ({"entries": [{"interaction_id": "9", "source_raw": POSTURE,
                           "membership": "RUNNING"}], "own_open_ids": ("9",)}, A.BODY_BUSY),
            ({"entries": [{"interaction_id": "9", "source_raw": PIE,
                           "membership": "QUEUED"}]}, A.BODY_BUSY),
            ({"entries": [{"interaction_id": "9", "source_raw": "InteractionSource.AUTONOMY",
                           "membership": "RUNNING"}]}, A.BODY_BUSY),
            ({"paused": True}, A.CLOCK_PAUSED),
            ({"entries": [{"interaction_id": "9", "source_raw": POSTURE,
                           "membership": "RUNNING"}]}, None),
        ]
        for overrides, code in cases:
            self.assertEqual(T.trial_check(self.view(**overrides)), code, overrides)

    def test_excluded_picker_social_and_deny_name(self):
        self.assertEqual(self.actuator.excluded(SeatPicker), "picker")
        self.assertEqual(self.actuator.excluded(Greet), "social")
        self.assertEqual(self.actuator.excluded(sim_delete_item), "deny_name")
        self.assertIsNone(self.actuator.excluded(WatchTV))


class TrialCommandTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.base.objects[CHAIR] = _Offer(CHAIR, [WatchTV])

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def e2(self):
        return self.base.e2("experiment_event")

    def ready(self, name="LAB_E1_FORK"):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm(name))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()

    def trial(self, object_id=CHAIR, guid64=GUID):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "trial", "args": {"object_id": object_id, "guid64": guid64}},
            connection)
        return ok, connection

    def test_each_live_reject_and_a_passing_interaction_card(self):
        self.ready("LAB_E1")
        ok, connection = self.trial()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "TRIAL_REJECT TRIAL_FORK_ONLY")
        self.probe._cmd_stop()
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()

        self.ready()
        self.base.objects[CHAIR] = _Offer(CHAIR, [SeatPicker])
        ok, connection = self.trial()
        self.assertEqual(connection.lines[-1], "TRIAL_REJECT TRIAL_EXCLUDED")
        self.base.objects[CHAIR] = _Offer(CHAIR, [Greet])
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT TRIAL_EXCLUDED")
        self.base.objects[CHAIR] = _Offer(CHAIR, [sim_delete_item])
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT TRIAL_EXCLUDED")
        self.base.objects[CHAIR] = _Offer(CHAIR, [WatchTV])

        self.probe.observers.read_motives = lambda *args, **kwargs: [{"band": "distress"}]
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT NEED_DISTRESS")
        self.probe.observers.read_motives = lambda *args, **kwargs: []

        self.base.sim.si_state = [_running(9, PIE)]
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT BODY_BUSY")
        self.base.sim.si_state = [_running(8, POSTURE)]

        self.base.clock_speed = "PAUSED"
        self.assertEqual(self.trial()[1].lines[-1], "TRIAL_REJECT CLOCK_PAUSED")
        self.base.clock_speed = "NORMAL"

        self.probe._cmd_calibrate()
        ok, connection = self.trial()
        self.assertFalse(ok)
        self.assertEqual(connection.code, "CALIBRATE_OBSERVE_ONLY")
        self.assertEqual(self.base.pushes, [])

    def test_push_then_running_ten_seconds_passes_with_names(self):
        self.ready()
        mono = {"n": 1_000_000_000}
        self.probe.observers._monotonic_ns = lambda: mono["n"]
        ok, connection = self.trial()
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("TRIAL_PUSHED "))
        pushed = self.e2()[-1]
        self.assertEqual(pushed["phase"], "PUSHED")
        self.assertEqual(pushed["guid64"], GUID)
        self.assertEqual(pushed["card_class"], "interaction")
        self.assertEqual(pushed["tuning_name"], "WatchTV")
        experiment = list(self.probe._E2.experiments.values())[-1]
        self.assertEqual(experiment.card["card_class"], "interaction")
        self.base.sim.si_state = [_running(777, "InteractionSource.SCRIPT_WITH_USER_INTENT")]
        self.base.tick()
        mono["n"] += int(10e9)
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        verdict = self.e2()[-1]
        self.assertEqual(verdict["phase"], "VERDICT")
        self.assertEqual(verdict["code"], "PASS")
        self.assertEqual(verdict["guid64"], GUID)
        self.assertEqual(verdict["tuning_name"], "WatchTV")
        self.assertEqual(verdict["card_class"], "interaction")
        self.assertEqual(verdict["ambiguous"], [])

    def test_foreign_root_is_outcome_unknown(self):
        self.ready()
        self.assertTrue(self.trial()[0])
        self.base.sim.si_state = [
            _running(777, "InteractionSource.SCRIPT_WITH_USER_INTENT"),
            _running(50, PIE),
        ]
        self.base.tick()
        self.assertTrue(self.probe._cmd_stop())
        verdict = self.e2()[-1]
        self.assertEqual(verdict["code"], "OUTCOME_UNKNOWN")
        self.assertEqual(verdict["guid64"], GUID)

    def test_five_push_failures_latch_until_arm(self):
        self.ready()
        self.base.push_ok = False
        for _ in range(5):
            ok, connection = self.trial()
            self.assertFalse(ok)
            self.assertEqual(connection.lines[-1], "PUSH_FAILED")
        ok, connection = self.trial()
        self.assertEqual(connection.lines[-1], "TRIAL_REJECT TRIAL_STORM")
        self.assertEqual(len(self.base.pushes), 5)
        self.base.push_ok = True
        self.probe._cmd_stop()
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        self.ready()
        ok, connection = self.trial()
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("TRIAL_PUSHED "))

    def test_sit_and_sit_trial_still_push_the_sit_guid(self):
        self.base.objects[CHAIR] = self.base.objects.get(CHAIR)
        self.base.objects[CHAIR] = test_e2._Obj(CHAIR)
        self.ready("LAB_E1")
        self.base.learn_signature()
        self.assertTrue(self.probe._dispatch_e2_prepare(CHAIR, _session_id=1))
        token = self.e2()[-1]["token"]
        self.assertTrue(self.probe._dispatch_e2_sit(token, _session_id=1))
        self.assertEqual(self.base.pushes[-1][0], 31564)
        before = len(self.base.pushes)
        self.probe._cmd_stop()
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        self.ready("LAB_E1")
        self.base.learn_signature()
        connection = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(
            {"command": "sit_trial", "args": {"object_id": CHAIR}}, connection))
        self.assertEqual(len(self.base.pushes), before + 1)
        self.assertEqual(self.base.pushes[-1][0], 31564)

    def test_t1_and_n5_replays_unchanged(self):
        case = test_e2.RegistryTests("test_t1_evidence_replay_continuation_and_empty_set")
        case.setUp()
        case.test_t1_evidence_replay_continuation_and_empty_set()
        case.test_n5_evidence_learns_sit_and_continuation()

    def test_cmdbox_rejects_bad_trial_args(self):
        box = self.probe.cmdbox
        now = int(time.time() * 1000)

        def parse(args):
            raw = json.dumps({
                "v": 1, "id": "a" * 32, "issued_at_ms": now, "expires_at_ms": now + 1000,
                "issuer": "helper", "command": "trial", "args": args,
            }).encode("utf-8")
            return box.parse(raw, now, ())[1]

        self.assertIsNone(parse({"object_id": "12", "guid64": "34"}))
        self.assertEqual(parse({"guid64": "34"}), "BAD_ARGS")
        self.assertEqual(parse({"object_id": "12", "guid64": "34", "extra": "1"}), "BAD_ARGS")
        self.assertEqual(parse({"object_id": "12a", "guid64": "34"}), "BAD_ARGS")
        self.assertEqual(parse({"object_id": "1", "guid64": "1" * 21}), "BAD_ARGS")


