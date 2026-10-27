"""2.41.6: the household autostart hook uses a CallbackEvent the game has and fires.

1.128.90.1030 and 1.129.39.1030 (sims4.callback_utils identical) have no HOUSEHOLD_EXIT. The game fires
EXIT_CONTENT_SET_GEN_OR_PROCESS_HOUSEHOLD_EVENTS from EventManagerService.process_events_for_household
(invoke_enter_exit_callbacks); PROCESS_EVENTS_FOR_HOUSEHOLD_EXIT is declared but never invoked."""
import sys
import types
import unittest
from unittest import mock

from test_binding import load_probe

GAME_EVENTS = (
    "AUTONOMY_PING_ENTER", "AUTONOMY_PING_EXIT", "CONTENT_SET_GENERATE_ENTER", "CONTENT_SET_GENERATE_EXIT",
    "ENTER_CONTENT_SET_GEN_OR_PROCESS_HOUSEHOLD_EVENTS", "EXIT_CONTENT_SET_GEN_OR_PROCESS_HOUSEHOLD_EVENTS",
    "POSTURE_GRAPH_BUILD_ENTER", "POSTURE_GRAPH_BUILD_EXIT", "PROCESS_EVENTS_FOR_HOUSEHOLD_ENTER",
    "PROCESS_EVENTS_FOR_HOUSEHOLD_EXIT", "TRANSITION_SEQUENCE_ENTER", "TRANSITION_SEQUENCE_EXIT",
    "TUNING_CODE_RELOAD",
)


class HouseholdHookTests(unittest.TestCase):
    def setUp(self):
        _, self.p, _ = load_probe()
        self.added = []
        event_enum = type("CallbackEvent", (), {name: name for name in GAME_EVENTS})
        self.fake = types.ModuleType("sims4.callback_utils")
        self.fake.CallbackEvent = event_enum
        self.fake.add_callbacks = lambda events, callback: self.added.append(tuple(events))
        sims4 = sys.modules.get("sims4") or types.ModuleType("sims4")
        self.patches = [mock.patch.dict(sys.modules, {"sims4": sims4, "sims4.callback_utils": self.fake}),
                        mock.patch.object(sims4, "callback_utils", self.fake, create=True)]
        for patch in self.patches:
            patch.start()
        self.p._try_arm_zone = lambda source: None

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def test_every_callback_hook_registers_on_the_game_enum(self):
        self.p._register_autostart_hooks()
        for source in ("posture", "household", "transition"):
            with self.subTest(source=source):
                self.assertEqual(self.p._AUTOSTART_HOOKS.get(source), "registered")

    def test_household_hook_uses_the_event_the_game_fires(self):
        self.p._register_autostart_hooks()
        self.assertIn(("EXIT_CONTENT_SET_GEN_OR_PROCESS_HOUSEHOLD_EVENTS",), self.added)
        self.assertNotIn(("PROCESS_EVENTS_FOR_HOUSEHOLD_EXIT",), self.added)


if __name__ == "__main__":
    unittest.main()
