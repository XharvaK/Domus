"""2.32.0 (PR10, PR11): build or buy mode and a fire on the lot are facts of the game block, each None when the
game cannot give it. An act the game refuses during a fire, or in build mode, is named so (FIRE_REFUSED,
BUILD_MODE_REFUSED), not as a generic game refusal.

Invented data only. Built on the body fixtures of test_2313."""
import types
import unittest

from test_2313_body_zone import _BodyBase
from test_2160_act import GUID


class BuildAndFireReadTests(_BodyBase):
    def test_build_mode_and_fire_are_read_as_bools_and_none_when_unreadable(self):
        services = self.base.services
        services.current_zone = lambda: types.SimpleNamespace(is_in_build_buy=True)
        self.assertIs(self.probe.observers.build_mode(), True)
        services.current_zone = lambda: types.SimpleNamespace(is_in_build_buy="yes")
        self.assertIsNone(self.probe.observers.build_mode())

        def no_zone():
            raise RuntimeError("no zone")
        services.current_zone = no_zone
        self.assertIsNone(self.probe.observers.build_mode())

        services.get_fire_service = lambda: types.SimpleNamespace(fire_is_active=lambda: False)
        self.assertIs(self.probe.observers.fire_active(), False)
        services.get_fire_service = lambda: types.SimpleNamespace()
        self.assertIsNone(self.probe.observers.fire_active())

    def test_a_refusal_during_a_fire_is_named_fire_refused(self):
        self.ready()
        self.base.services.get_fire_service = lambda: types.SimpleNamespace(fire_is_active=lambda: True)
        self.probe.e2_actuator.preflight_test = lambda sim, obj, affordance, context: (False, "blocked", None)
        ok, connection = self.act(guid64=GUID)
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "FIRE_REFUSED")
        self.assertEqual(self.base.pushes, [])

    def test_a_refusal_in_build_mode_is_named_build_mode_refused(self):
        self.ready()
        self.base.services.get_fire_service = lambda: types.SimpleNamespace(fire_is_active=lambda: False)
        self.base.services.current_zone = lambda: types.SimpleNamespace(is_in_build_buy=True)
        self.probe.e2_actuator.preflight_test = lambda sim, obj, affordance, context: (False, "blocked", None)
        ok, connection = self.act(guid64=GUID)
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "BUILD_MODE_REFUSED")

    def test_an_ordinary_refusal_stays_a_game_refusal(self):
        self.ready()
        self.base.services.get_fire_service = lambda: types.SimpleNamespace(fire_is_active=lambda: False)
        self.base.services.current_zone = lambda: types.SimpleNamespace(is_in_build_buy=False)
        self.probe.e2_actuator.preflight_test = lambda sim, obj, affordance, context: (False, "blocked", None)
        ok, connection = self.act(guid64=GUID)
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "GAME_REFUSED")


if __name__ == "__main__":
    unittest.main()
