"""W14 (probe, Worker D): the near part says it is one (S1: "near": true on a near part, no key on a whole menu, every part
of a near part says so), and the game's clock is read as whole minutes (D2: a float clock makes a planned event; "clock"
only when the read fails).
Fakes only. The game's objects are replaced by invented ones; the clock is a fake."""
import math
import types
import unittest

import test_e2
from test_2160_act import ACT
from test_w13_p1 import _patched

from ashley_e1 import act_menu  # noqa: E402
from ashley_e1 import schema  # noqa: E402


def _phone_job(object_id, guid, name):
    return {"object_id": str(object_id), "definition_id": None, "class": "phone", "distance_m": None,
            "same_room": None, "room": None, "phone": True, "on_lot": True, "guid64": str(guid), "name": name,
            "text_key": None, "needs_sim": None}


class NearFlagTests(unittest.TestCase):
    def _build(self, jobs):
        build = act_menu.MenuBuild(jobs, lambda job: True, budget_ms=1000.0, max_per_chunk=100)
        for _ in range(8):
            build.step()
        return build

    def _row(self, payload):
        return schema.make_record("act_menu", telemetry_session_id="s" * 32, wall_timestamp_ms=1, monotonic_ns=1,
                                  e2=payload)

    def test_a_near_part_carries_near_true_and_a_whole_menu_carries_no_near_key(self):
        build = self._build([_phone_job(300, 10, "CallPickFriend")])
        whole = build.payload(1, "4")
        near = build.payload(1, "4", near=True)
        self.assertNotIn("near", whole)
        self.assertIs(near.get("near"), True)

    def test_every_part_of_a_near_part_says_it_is_near(self):
        jobs = [_phone_job(300 + index, 10 + index, "Call%d" % index) for index in range(act_menu.MENU_PART_OBJECTS + 3)]
        payload = self._build(jobs).payload(1, "4", near=True)
        rows = act_menu.parts(payload)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.get("near") is True for row in rows))
        self.assertTrue(all("near" not in row for row in act_menu.parts(self._build(jobs).payload(1, "4"))))

    def test_the_schema_takes_a_near_part_and_refuses_a_near_key_that_is_not_true(self):
        build = self._build([_phone_job(300, 10, "CallPickFriend")])
        for row in act_menu.parts(build.payload(1, "4", near=True)):
            schema.validate_record(self._row(row))
        for row in act_menu.parts(build.payload(1, "4")):
            schema.validate_record(self._row(row))
        bad = dict(act_menu.parts(build.payload(1, "4", near=True))[0], near=False)
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(self._row(bad))
        extra = dict(act_menu.parts(build.payload(1, "4"))[0], near=True, other=1)
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(self._row(extra))


class ClockTests(unittest.TestCase):
    """e2_actuator.now_absolute_minutes: the game gives a float; the whole minute (floor) is kept."""

    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.actuator = self.base.probe.e2_actuator

    def _clock(self, value):
        class _Now(object):
            def absolute_minutes(self_inner):
                if isinstance(value, Exception):
                    raise value
                return value
        return lambda: types.SimpleNamespace(sim_now=_Now())

    def test_a_whole_minute_is_kept(self):
        with _patched(self.base.services, "time_service", self._clock(2 * 1440 + 600)):
            self.assertEqual(self.actuator.now_absolute_minutes(), 2 * 1440 + 600)

    def test_a_float_minute_is_floored_to_a_whole_minute(self):
        with _patched(self.base.services, "time_service", self._clock(2 * 1440 + 600.75)):
            self.assertEqual(self.actuator.now_absolute_minutes(), 2 * 1440 + 600)
        with _patched(self.base.services, "time_service", self._clock(1000.0)):
            value = self.actuator.now_absolute_minutes()
        self.assertEqual(value, 1000)
        self.assertIs(type(value), int)

    def test_a_clock_that_is_not_a_finite_number_is_unread(self):
        for value in (math.nan, math.inf, -math.inf, "1000", None):
            with _patched(self.base.services, "time_service", self._clock(value)):
                self.assertIsNone(self.actuator.now_absolute_minutes(), value)

    def test_a_failed_read_is_unread(self):
        with _patched(self.base.services, "time_service", self._clock(RuntimeError("no clock"))):
            self.assertIsNone(self.actuator.now_absolute_minutes())


class FloatClockEventTests(unittest.TestCase):
    """A planned event with a float game clock is made (the real clock read); "clock" only when the read fails."""

    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.saved_zones = set(self.probe._KNOWN_ZONES)

    def tearDown(self):
        self.probe._KNOWN_ZONES.clear()
        self.probe._KNOWN_ZONES.update(self.saved_zones)
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def ready(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()

    def send(self, command, args):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": command, "args": args}, connection)
        return ok, connection

    def act_events(self, phase=None):
        return [row for row in self.base.e2("act_event") if phase is None or row["phase"] == phase]

    def _clock_object(self, value):
        class _Now(object):
            def absolute_minutes(self_inner):
                if isinstance(value, Exception):
                    raise value
                return value
        return types.SimpleNamespace(sim_now=_Now())

    def _event(self, clock_value):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        situation = types.SimpleNamespace(name="party")
        created = []
        with _patched(self.base.services, "time_service", lambda: self._clock_object(clock_value)), \
                _patched(self.probe.e2_actuator, "situation_type", lambda guid: situation), \
                _patched(self.probe.e2_actuator, "situation_cost", lambda s: 0), \
                _patched(self.probe.e2_actuator, "default_job", lambda s: "job"), \
                _patched(self.probe.e2_actuator, "event_guest_list",
                         lambda host, guests, job: types.SimpleNamespace(guests=guests, get_hire_cost=lambda: 0)), \
                _patched(self.probe.e2_actuator, "create_event",
                         lambda zone, s, guest_list, when: created.append(when) or "909"), \
                _patched(self.probe.observers, "household_money", lambda info: 500):
            ok, _connection = self.send("event", {"act_id": ACT, "situation_id": "9", "guests": ["4"], "start": "now"})
        return ok, created

    def test_a_float_clock_makes_a_planned_event(self):
        ok, created = self._event(2 * 1440 + 600.5)
        self.assertTrue(ok)
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("FINISHED", "CREATED"))
        self.assertEqual(last["result"]["start_min"], 2 * 1440 + 600)
        self.assertEqual(len(created), 1)

    def test_an_unread_clock_is_refused_as_clock(self):
        ok, created = self._event(RuntimeError("no clock"))
        self.assertFalse(ok)
        last = self.act_events("REJECTED")[-1]
        self.assertEqual((last["code"], last["detail"]), ("CREATE_FAILED", "clock"))
        self.assertEqual(created, [])
