"""D10d automatic inbox start and rejection-result regression tests."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from test_binding import load_probe
from test_d10 import command


class Zone:
    def __init__(self):
        self.callbacks = []

    def register_callback(self, state, callback):
        self.callbacks.append((state, callback))


class AutostartTests(unittest.TestCase):
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

    def require_hooks(self):
        self.assertTrue(hasattr(self.p, '_on_zone_added'), 'C3b zone hook missing')
        self.assertTrue(hasattr(self.p, '_start_inbox_pump'), 'C3b shared start missing')

    def start_zone(self):
        self.initialize(self.manager, self.zone)
        self.assertEqual(len(self.zone.callbacks), 1, 'RUNNING callback not registered')
        self.zone.callbacks[0][1]()

    def test_manager_registration_zero_and_numeric_comment(self):
        self.initialize(self.manager)
        self.assertEqual(len(self.manager_calls), 1, 'manager object-add callback not registered')
        self.assertEqual(self.manager_calls, [(0, self.p._on_zone_added)])
        source = Path(self.p.__file__).read_text()
        self.assertIn('0 is indexed_manager.CallbackTypes.ON_OBJECT_ADD', source)
        self.assertNotIn('getattr(', source)

    def test_existing_zone_immediate_running_registration(self):
        self.initialize(self.manager, self.zone)
        self.assertEqual(len(self.zone.callbacks), 1, 'existing zone not registered immediately')
        self.assertEqual(self.zone.callbacks, [(6, self.p._start_inbox_pump)])
        self.assertEqual(self.calls['alarms'], [])
        self.assertIn('6 is zone_types.ZoneState.RUNNING', Path(self.p.__file__).read_text())

    def test_running_alarm_idempotent_and_second_zone_replaces(self):
        self.start_zone()
        first = self.p._INBOX_HANDLE
        callback = self.zone.callbacks[0][1]
        self.assertTrue(callback())
        self.assertEqual(len(self.calls['alarms']), 1)
        settings = self.calls['alarms'][0][2]
        self.assertEqual((settings['time_span'], settings['repeating'],
                          settings['cross_zone'], settings['use_sleep_time']),
                         (1, True, False, False))
        self.assertIs(settings['callback'], self.p._inbox_tick)
        other = Zone()
        self.manager_calls[0][1](other)
        self.assertEqual(other.callbacks, [(6, callback)])
        self.assertTrue(other.callbacks[0][1]())
        self.assertEqual(self.calls['cancelled'], [first])
        self.assertEqual(len(self.calls['alarms']), 2)
        self.assertIsNot(self.p._INBOX_HANDLE, first)
        self.assertTrue(callback())
        self.assertEqual(len(self.calls['alarms']), 2)

    def test_fallback_after_auto_start_adds_no_alarm(self):
        self.start_zone()
        handle = self.p._INBOX_HANDLE
        registered = dict((r[0], r[2]) for r in self.calls['registrations'])
        self.assertTrue(registered['ashley_e1.inbox'](_session_id=73))
        self.assertIs(self.p._INBOX_HANDLE, handle)
        self.assertEqual(len(self.calls['alarms']), 1)
        self.assertEqual(self.calls['cancelled'], [])
        self.assertEqual(self.calls['outputs'][-1], ('INBOX ON', 73))

    def test_manager_unavailable_status_bootstrap_and_fallback(self):
        self.initialize()
        self.assertEqual(self.p._inbox_status().get('inbox_autostart'),
                         'MANAGER_UNAVAILABLE', 'missing manager-unavailable status')
        self.assertEqual(self.boot[-1]['inbox_autostart'], 'MANAGER_UNAVAILABLE')
        self.assertTrue(self.p._dispatch_inbox())
        self.assertEqual(self.p._inbox_status()['inbox_autostart'], 'STARTED')

    def test_existing_zone_registered_even_without_manager(self):
        self.initialize(None, self.zone)
        self.assertEqual(len(self.zone.callbacks), 1, 'existing zone skipped without manager')
        self.assertEqual(self.boot[-1]['inbox_autostart'], 'MANAGER_UNAVAILABLE')
        self.assertTrue(self.zone.callbacks[0][1]())
        self.assertEqual(self.p._inbox_status()['inbox_autostart'], 'STARTED')

    def test_not_started_status_and_bootstrap(self):
        self.initialize(self.manager)
        self.assertEqual(self.p._inbox_status().get('inbox_autostart'),
                         'NOT_STARTED', 'missing not-started status')
        self.assertEqual(self.boot[-1]['inbox_autostart'], 'NOT_STARTED')

    def test_started_status_reply_and_bootstrap_summary(self):
        self.start_zone()
        root = Path(self.p._TELEMETRY_ROOT)
        (root/'cmd/inbox/001.json').write_text(json.dumps(command()))
        with mock.patch.object(self.p.time, 'time', return_value=1):
            self.p._inbox_tick()
        reply = json.loads((root/'cmd/outbox'/('a'*32+'.json')).read_bytes())
        self.assertEqual(reply['result']['inbox_autostart'], 'STARTED')
        # Exercise the actual bootstrap writer and schema, not just its call arguments.
        from ashley_e1.writer import bootstrap_from_module_path
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch('ashley_e1.writer.derive_telemetry_root', return_value=directory):
            bootstrap_from_module_path('fake', '2.2.0', self.p.SIMS_BUILD,
                                       self.p._required_import_summary(),
                                       inbox_autostart='STARTED')
            row = json.loads(next(Path(directory).glob('*.jsonl')).read_text())
            self.assertEqual(row['runtime']['inbox_autostart'], 'STARTED')
            self.p.schema.validate_record(row)
            row['runtime']['inbox_autostart'] = 'INVALID'
            with self.assertRaises(ValueError):
                self.p.schema.validate_record(row)

    def test_zone_without_callback_uses_hasattr(self):
        self.require_hooks()
        self.p._on_zone_added(object())
        self.assertEqual(self.calls['alarms'], [])
        source = Path(self.p.__file__).read_text()
        self.assertIn('hasattr(z, "register_callback")', source)

    def test_manager_and_current_zone_exceptions_never_escape(self):
        self.require_hooks()
        self.manager.register_callback = mock.Mock(side_effect=RuntimeError('manager'))
        self.initialize(self.manager, self.zone)
        self.assertEqual(self.zone.callbacks, [])
        self.assertEqual(self.boot[-1]['inbox_autostart'], 'NOT_STARTED')
        self.manager.register_callback = lambda *a: self.manager_calls.append(a)
        self.p._services_module.current_zone = mock.Mock(side_effect=RuntimeError('zone'))
        self.p._INITIALIZED = False
        with mock.patch.object(self.p, 'derive_telemetry_root', return_value=self.p._TELEMETRY_ROOT), \
                mock.patch.object(self.p, 'bootstrap_from_module_path'):
            self.p.initialize_probe()
        self.assertEqual(len(self.manager_calls), 1)
        self.p._services_module.get_zone_manager = mock.Mock(side_effect=RuntimeError('getter'))
        self.p._INITIALIZED = False
        with mock.patch.object(self.p, 'derive_telemetry_root', return_value=self.p._TELEMETRY_ROOT), \
                mock.patch.object(self.p, 'bootstrap_from_module_path'):
            self.p.initialize_probe()

    def test_zone_callback_and_hasattr_exceptions_never_escape(self):
        self.require_hooks()
        zone = Zone()
        zone.register_callback = mock.Mock(side_effect=RuntimeError('callback'))
        self.p._on_zone_added(zone)
        self.assertEqual(self.calls['alarms'], [])

        class BrokenZone:
            @property
            def register_callback(self):
                raise RuntimeError('hasattr')

        self.p._on_zone_added(BrokenZone())
        self.assertEqual(self.calls['alarms'], [])

    def test_start_directory_alarm_and_cancel_exceptions_never_escape(self):
        self.require_hooks()
        with mock.patch.object(self.p.os, 'makedirs', side_effect=OSError('mkdir')):
            self.assertFalse(self.p._start_inbox_pump())
        self.assertIsNone(self.p._INBOX_HANDLE)
        with mock.patch.object(self.p.alarms, 'add_alarm_real_time', side_effect=RuntimeError('alarm')):
            self.assertFalse(self.p._start_inbox_pump())
        self.assertIsNone(self.p._INBOX_HANDLE)
        self.start_zone()
        handle = self.p._INBOX_HANDLE
        self.p._on_zone_added(Zone())
        with mock.patch.object(self.p.alarms, 'cancel_alarm', side_effect=RuntimeError('cancel')):
            self.assertFalse(self.p._start_inbox_pump())
            self.assertFalse(self.p._dispatch_inbox())
        self.assertIs(self.p._INBOX_HANDLE, handle)
        self.assertEqual(len(self.calls['alarms']), 1)


class RejectionTests(unittest.TestCase):
    def test_expired_non_status_result_false_empty_lines(self):
        _, p, calls = load_probe()
        self.assertTrue(p._dispatch_inbox())
        root = Path(p._TELEMETRY_ROOT)/'cmd'
        (root/'inbox/001.json').write_text(json.dumps(command('start', expires_at_ms=999)))
        with mock.patch.object(p.time, 'time', return_value=1), \
                mock.patch.object(p, '_dispatch_start') as start:
            p._inbox_tick()
            start.assert_not_called()
        reply = json.loads((root/'outbox'/('a'*32+'.json')).read_bytes())
        self.assertEqual(reply['code'], 'EXPIRED')
        self.assertEqual(reply['status'], 'REJECTED')
        self.assertEqual(reply['result'], {'ok': False, 'lines': []},
                         'rejected non-status result must be false/empty-lines')


class StatusRegressionTests(unittest.TestCase):
    def test_console_status_read_only_unarmed_shared_dispatch_cheat_output(self):
        _, p, calls = load_probe()
        registered = dict((r[0], r[2]) for r in calls['registrations'])
        self.assertEqual(len(registered), 10)
        self.assertIs(registered['ashley_e1.status'], p._dispatch_status)
        before = p.get_status()
        with mock.patch.object(p._commands_module, 'output') as noop, \
                mock.patch.object(p, '_dispatch_status', wraps=p._dispatch_status) as status:
            self.assertTrue(registered['ashley_e1.status'](_session_id=81))
            collector = p._InboxReply('agent:coder')
            self.assertTrue(p._inbox_dispatch(command(), collector))
            status.assert_called_once_with(_session_id=collector)
            noop.assert_not_called()
        self.assertEqual(p.get_status(), before)
        self.assertEqual(before['state'], 'UNARMED')
        self.assertEqual(calls['outputs'], [('state: UNARMED inbox: off', 81)])
        self.assertEqual(collector.lines, ['state: UNARMED inbox: off'])
        self.assertEqual(calls['alarms'], [])
        self.assertIsNone(p._WRITER)
