"""2.21.0: the overlay's camera follows her Sim or looks at one object. View only."""
import json
import types
import unittest

import test_2160_act as acts
from test_e2 import CHAIR

HER = "118245043779534861"


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.control = self.probe.e2_control
        self.followed = []
        self.focused = []
        self.control.focus_on_sim = lambda sim=None, follow=True, client=None: self.followed.append((sim, follow))
        self.control.focus_on_object = lambda object=None, follow=True: self.focused.append((object, follow))
        self.now = [1000.0]
        self.control.time.monotonic = lambda: self.now[0]
        sim = self.case.base.sim
        sim.id = int(HER)
        services = self.case.base.services
        previous = services.sim_info_manager()
        infos = previous.get_all()

        def get(sim_id):
            for item in infos:
                if int(getattr(item, "id", -1)) == int(sim_id):
                    return item
            return None

        services.sim_info_manager = lambda: types.SimpleNamespace(get_all=lambda: infos, get=get)
        self.services = services

    def tearDown(self):
        self.case.tearDown()

    def camera(self, op, target_id):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "camera", "args": {"op": op, "target_id": target_id}}, connection)
        return ok, connection

    def test_follow_sim_moves_only_the_view(self):
        self.case.ready()
        ok, connection = self.camera("follow_sim", HER)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1], "CAMERA_OK follow_sim %s" % HER)
        self.assertEqual(len(self.followed), 1)
        sim, follow = self.followed[0]
        self.assertIs(sim, self.case.base.sim)
        self.assertTrue(follow)
        self.assertEqual(self.case.events(), [])

    def test_focus_object(self):
        self.case.ready()
        ok, connection = self.camera("focus_object", CHAIR)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(len(self.focused), 1)
        obj, follow = self.focused[0]
        self.assertIs(obj, self.case.base.objects[CHAIR])
        self.assertFalse(follow)

    def test_unfollow_keeps_the_view_on_her_and_stops_the_follow(self):
        # 2.32.0 (HE14): the User's hand on the controls: the view stays on her Sim, not following it.
        self.case.ready()
        ok, connection = self.camera("unfollow", HER)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1], "CAMERA_OK unfollow %s" % HER)
        sim, follow = self.followed[-1]
        self.assertIs(sim, self.case.base.sim)
        self.assertFalse(follow)
        self.assertEqual(self.case.events(), [])

    def test_one_op_per_gap(self):
        self.case.ready()
        self.assertTrue(self.camera("follow_sim", HER)[0])
        self.now[0] += 1.0
        ok, connection = self.camera("follow_sim", HER)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "CAMERA_REJECT TOO_SOON")
        self.now[0] += 1.0
        ok, connection = self.camera("focus_object", CHAIR)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1], "CAMERA_OK focus_object %s" % CHAIR)

    def test_unknown_target(self):
        self.case.ready()
        ok, connection = self.camera("follow_sim", "404")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "CAMERA_REJECT NO_TARGET")
        ok, connection = self.camera("focus_object", "404")
        self.assertEqual(connection.lines[-1], "CAMERA_REJECT NO_TARGET")
        self.assertEqual(self.followed, [])
        self.assertEqual(self.focused, [])

    def test_not_sampling_refuses(self):
        self.case.base.LedgerWriter.records = [self.case.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        ok, connection = self.camera("follow_sim", HER)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "CAMERA_REJECT NOT_SAMPLING")
        self.assertEqual(self.followed, [])

    def test_cmdbox_shape(self):
        from ashley_e1 import cmdbox
        base = {"v": 1, "id": "e" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
                "issuer": "helper", "command": "camera"}

        def check(args):
            return cmdbox.parse(json.dumps(dict(base, args=args)).encode("utf-8"), 1500, set())[1]

        self.assertIsNone(check({"op": "follow_sim", "target_id": "123"}))
        self.assertIsNone(check({"op": "unfollow", "target_id": "123"}))
        for bad in ({"op": "walls_up", "target_id": "123"},
                    {"op": "follow_sim", "target_id": "12x"},
                    {"op": "follow_sim"},
                    {"op": "follow_sim", "target_id": "123", "extra": "1"}):
            self.assertEqual(check(bad), "BAD_ARGS", bad)

    def test_calibrate_observe_only_refuses_camera(self):
        self.case.ready()
        self.probe._cmd_calibrate()
        ok, connection = self.camera("follow_sim", HER)
        self.assertFalse(ok)
        self.assertEqual(connection.code, "CALIBRATE_OBSERVE_ONLY")
        self.assertEqual(self.followed, [])


if __name__ == "__main__":
    unittest.main()
