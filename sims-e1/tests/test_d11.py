"""D11-1 autostart-hook contract tests; fakes only, no live game."""
import types
import unittest
from unittest import mock

from test_binding import load_probe


CLOSED_AUTOSTART = (
    "NOT_STARTED", "MANAGER_UNAVAILABLE",
    "ZONE:import", "ZONE:tuning", "ZONE:posture",
    "ZONE:household", "ZONE:transition", "ZONE:manager",
    "CONSOLE",
)


class Zone:
    def __init__(self):
        self.callbacks = []

    def register_callback(self, state, callback):
        self.callbacks.append((state, callback))


class AutostartHookTests(unittest.TestCase):
    def setUp(self):
        _, self.p, self.calls = load_probe()
        self.manager_calls = []
        self.manager = types.SimpleNamespace(
            register_callback=lambda *args: self.manager_calls.append(args))
        self.zone = Zone()
        self.boot = []

    def initialize(self, manager=None, zone=None):
        p = self.p
        p._INITIALIZED = False
        p._services_module.get_zone_manager = lambda: manager
        p._services_module.current_zone = lambda: zone
        root = p._TELEMETRY_ROOT
        with mock.patch.object(p, 'derive_telemetry_root', return_value=root), \
                mock.patch.object(p, 'bootstrap_from_module_path',
                                  side_effect=lambda *a, **k: self.boot.append(k)):
            p.initialize_probe()

    def test_try_arm_zone_exists_and_never_raises(self):
        self.assertTrue(hasattr(self.p, '_try_arm_zone'), '_try_arm_zone missing')
        try:
            self.p._try_arm_zone('import')
        except Exception as error:
            self.fail('_try_arm_zone raised %r' % (error,))

    def test_arming_idempotent_per_zone_and_manager(self):
        self.assertTrue(hasattr(self.p, '_try_arm_zone'), '_try_arm_zone missing')
        self.initialize(self.manager, self.zone)
        zone_count = len(self.zone.callbacks)
        manager_count = len(self.manager_calls)
        self.assertEqual(zone_count, 1, 'zone not armed once')
        self.assertEqual(manager_count, 1, 'manager not armed once')
        self.p._try_arm_zone('import')
        self.p._try_arm_zone('tuning')
        self.assertEqual(len(self.zone.callbacks), zone_count, 'zone armed twice')
        self.assertEqual(len(self.manager_calls), manager_count, 'manager armed twice')

    def test_each_hook_calls_try_arm_with_source_and_failure_recorded(self):
        self.assertTrue(hasattr(self.p, '_try_arm_zone'), '_try_arm_zone missing')
        seen = []
        original = self.p._try_arm_zone
        with mock.patch.object(self.p, '_try_arm_zone',
                               side_effect=lambda source: seen.append(source)):
            self.initialize(self.manager, self.zone)
        for source in ('import', 'tuning', 'posture', 'household', 'transition'):
            with self.subTest(source=source):
                self.assertIn(source, seen, 'hook did not call _try_arm_zone(%s)' % source)
        self.assertTrue(hasattr(self.p, '_AUTOSTART_HOOKS'), 'hook status missing')
        for name in ('tuning', 'posture', 'household', 'transition', 'import'):
            self.assertIn(self.p._AUTOSTART_HOOKS.get(name), ('registered', 'failed'))
        failing = [name for name, value in self.p._AUTOSTART_HOOKS.items()
                   if value == 'failed']
        self.assertTrue(failing, 'fake env should fail at least one hook without raising')

    def test_running_callback_firing_immediately_starts_pump_once(self):
        self.assertTrue(hasattr(self.p, '_try_arm_zone'), '_try_arm_zone missing')

        class ImmediateZone(Zone):
            def register_callback(self, state, callback):
                super().register_callback(state, callback)
                callback()

        immediate = ImmediateZone()
        self.initialize(self.manager, immediate)
        first = self.p._INBOX_HANDLE
        self.assertIsNotNone(first, 'immediate RUNNING did not start pump')
        self.assertIn(self.p._INBOX_AUTOSTART, CLOSED_AUTOSTART)
        self.assertTrue(self.p._INBOX_AUTOSTART.startswith('ZONE:'))
        count = len(self.calls['alarms'])
        immediate.callbacks[0][1]()
        self.assertEqual(len(self.calls['alarms']), count, 'second fire created alarm')

    def test_console_after_auto_start_gives_already_no_second_alarm(self):
        self.assertTrue(hasattr(self.p, '_try_arm_zone'), '_try_arm_zone missing')
        self.initialize(self.manager, self.zone)
        self.zone.callbacks[0][1]()
        handle = self.p._INBOX_HANDLE
        source = self.p._INBOX_AUTOSTART
        self.assertTrue(source.startswith('ZONE:'), 'auto start did not set ZONE source')
        registered = dict((r[0], r[2]) for r in self.calls['registrations'])
        self.assertTrue(registered['ashley_e1.inbox'](_session_id=73))
        self.assertIs(self.p._INBOX_HANDLE, handle, 'console created second alarm')
        self.assertEqual(len(self.calls['alarms']), 1)
        text, connection = self.calls['outputs'][-1]
        self.assertIn('already', text, 'console did not say already')
        self.assertIn(source[5:], text, 'already reply missing source')


if __name__ == '__main__':
    unittest.main()
