"""D11-1 autostart-hook contract tests; fakes only, no live game."""
import json
from pathlib import Path
import types
import unittest
from unittest import mock

from test_binding import load_probe
from test_d10 import command


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


class InboxTickErrorTests(unittest.TestCase):
    def setUp(self):
        _, self.p, _ = load_probe()
        self.root = Path(self.p._TELEMETRY_ROOT) / 'cmd'
        self.p._start_inbox_pump()

    def queue(self, command_id='a' * 32):
        path = self.root / 'inbox' / (command_id + '.json')
        path.write_text(json.dumps(command(id=command_id)), encoding='utf-8')
        return path

    def tick(self):
        try:
            with mock.patch.object(self.p.time, 'time', return_value=1):
                self.p._inbox_tick()
        except Exception as error:
            self.fail('tick raised %r' % (error,))

    def assert_completed(self, path):
        self.assertFalse(path.exists())
        self.assertFalse(Path(str(path) + '.taken').exists())
        self.assertTrue((self.root / 'done' / path.name).exists())

    def test_emit_error_is_replied_and_completed(self):
        path = self.queue()
        self.p._WRITER = object()
        self.p._WRITER_IDLE = False
        with mock.patch.object(self.p, '_emit', side_effect=RuntimeError('writer')):
            self.tick()
        self.assertEqual(self.p._inbox_status().get('inbox_errors'), 1)
        self.assert_completed(path)
        reply = json.loads((self.root / 'outbox' / path.name).read_bytes())
        self.assertEqual(reply['status'], 'ERROR')

    def test_reply_write_error_is_completed(self):
        path = self.queue()
        with mock.patch.object(self.p, 'write_command_reply',
                               side_effect=[RuntimeError('reply'), None]):
            self.tick()
        self.assertEqual(self.p._inbox_status().get('inbox_errors'), 1)
        self.assert_completed(path)

    def test_status_reports_error_count(self):
        self.assertEqual(self.p._inbox_status().get('inbox_errors'), 0)
        path = self.queue()
        self.tick()
        reply = json.loads((self.root / 'outbox' / path.name).read_bytes())
        self.assertEqual(reply['result'].get('inbox_errors'), 0)
        path = self.queue('b' * 32)
        with mock.patch.object(self.p, 'write_command_reply',
                               side_effect=RuntimeError('reply')):
            self.tick()
        self.assertEqual(self.p._inbox_status().get('inbox_errors'), 1)
        path = self.queue('c' * 32)
        self.tick()
        reply = json.loads((self.root / 'outbox' / path.name).read_bytes())
        self.assertEqual(reply['result'].get('inbox_errors'), 1)
        self.p._STATE_RESET()
        self.assertEqual(self.p._inbox_status().get('inbox_errors'), 0)


if __name__ == '__main__':
    unittest.main()


class AutostartValuesTests(unittest.TestCase):
    def test_versions_are_250(self):
        package, probe, _ = load_probe()
        self.assertEqual(package.E1_PROBE_VERSION, "2.34.0")
        self.assertEqual(probe.schema.PROBE_VERSION, "2.34.0")

    def test_closed_values_include_legacy_and_reject_unknown(self):
        _, probe, _ = load_probe()
        schema = probe.schema
        runtime = dict(python_version="3.13", perf_counter=True,
                       required_imports=dict.fromkeys(schema.REQUIRED_IMPORT_KEYS, True))
        for value in CLOSED_AUTOSTART + ("STARTED",):
            with self.subTest(value=value):
                schema._validate_load_disabled_runtime(dict(runtime, inbox_autostart=value))
        with self.assertRaises(schema.SchemaError):
            schema._validate_load_disabled_runtime(dict(runtime, inbox_autostart="ZONE:bogus"))

    def test_status_includes_autostart_and_errors(self):
        _, probe, _ = load_probe()
        self.assertIn("inbox_autostart", probe._inbox_status())
        self.assertIn("inbox_errors", probe._inbox_status())

    def test_never_emits_legacy_started(self):
        for path in ("import", "zone", "console", "manager"):
            with self.subTest(path=path):
                _, probe, calls = load_probe()
                def check():
                    self.assertNotEqual(probe._INBOX_AUTOSTART, "STARTED")
                    self.assertNotEqual(probe._inbox_status()["inbox_autostart"], "STARTED")
                check()
                zone = Zone()
                manager_callbacks = []
                manager = types.SimpleNamespace(
                    register_callback=lambda *args: manager_callbacks.append(args))
                probe._services_module.get_zone_manager = lambda: manager
                probe._services_module.current_zone = lambda: None
                probe._INITIALIZED = False
                with mock.patch.object(probe, 'derive_telemetry_root',
                                       return_value=probe._TELEMETRY_ROOT), \
                        mock.patch.object(probe, 'bootstrap_from_module_path'):
                    probe.initialize_probe()
                check()
                if path != "manager":
                    probe._services_module.current_zone = lambda: zone
                if path in ("import", "zone"):
                    probe._try_arm_zone("import" if path == "import" else "tuning")
                    check()
                if path == "manager":
                    manager_callbacks[0][1](zone)
                    check()
                if path == "console":
                    registered = dict((r[0], r[2]) for r in calls['registrations'])
                    registered['ashley_e1.inbox'](_session_id=73)
                else:
                    zone.callbacks[0][1]()
                check()
                expected = "CONSOLE" if path == "console" else "ZONE:" + (
                    "manager" if path == "manager" else ("import" if path == "import" else "tuning"))
                self.assertEqual(probe._INBOX_AUTOSTART, expected)
