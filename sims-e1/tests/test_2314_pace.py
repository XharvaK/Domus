"""2.31.0 (W3p, DOMUS_DEEP_DESIGN §5a, §5): her needs drain at the helper's pace, and an optional slower clock.

Fakes only: commodities that record every call, a clock class whose attribute the probe may set, a zone and a
clock service. Invented ids; the motive guids are the probe's own table."""
import json
import os
import types
import unittest
from unittest import mock

from test_binding import load_probe

HELPER = "helper"
MOTIVE_GUIDS = (16656, 16654, 16652, 16657, 16655, 16658)
OTHER_GUID = 999


class _Commodity(object):
    """A motive (or another commodity) with the game's decay-rate modifier list and call record."""
    def __init__(self, guid, base=0.1):
        self.guid64 = guid
        self.base = base
        self.modifiers = []
        self.calls = []

    def add_decay_rate_modifier(self, value):
        self.calls.append(("add", value))
        self.modifiers.append(value)

    def remove_decay_rate_modifier(self, value):
        self.calls.append(("remove", value))
        if value in self.modifiers:
            self.modifiers.remove(value)

    def send_commodity_progress_msg(self):
        self.calls.append(("send",))

    def clear_decay_rate_modifiers(self):
        raise AssertionError("the probe never clears every modifier")

    def get_decay_rate(self, use_decay_modifier=True):
        product = 1.0
        if use_decay_modifier:
            for value in self.modifiers:
                product *= value
        return self.base * product

    def applied(self, value):
        return [call for call in self.calls if call[0] == "add" and call[1] == value]


class _Tracker(object):
    def __init__(self, commodities):
        self.commodities = list(commodities)

    def get_all_commodities(self):
        return iter(list(self.commodities))


class _Zone(object):
    is_zone_running = True


class _ClockService(object):
    def __init__(self, clock):
        self.clock = clock
        self.syncs = 0
        self.scale = 1.0

    def _sync_clock_and_broadcast_gameclock(self):
        self.syncs += 1

    def current_clock_speed_scale(self):
        return self.scale


class _Connection(object):
    def __init__(self, issuer):
        self.issuer = issuer
        self.lines = []
        self.code = None


class PaceFixture(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import e2_control, observers, schema, cmdbox
        self.e2c, self.observers, self.schema, self.cmdbox = e2_control, observers, schema, cmdbox
        self.clock_module = types.SimpleNamespace(GameClock=type("GameClock", (), {"NORMAL_SPEED_MULTIPLIER": 1}))
        self.date = types.SimpleNamespace(REAL_MILLISECONDS_PER_SIM_SECOND=25)
        self.zone = _Zone()
        self.clock_service = _ClockService(self.clock_module.GameClock)
        self.motives = [_Commodity(guid) for guid in MOTIVE_GUIDS]
        self.other = _Commodity(OTHER_GUID)
        self.tracker = _Tracker(self.motives + [self.other])
        self.sim_info = types.SimpleNamespace(id=4242, commodity_tracker=self.tracker)
        self.services = types.SimpleNamespace(
            current_zone=lambda: self.zone, game_clock_service=lambda: self.clock_service,
            sim_info_manager=lambda: types.SimpleNamespace(get_all=lambda: [self.sim_info]))
        self.state = ["SAMPLING"]
        self.rows = []
        self._patch(e2_control, "game_clock", self.clock_module)
        self._patch(e2_control, "date_and_time", self.date)
        self._patch(e2_control, "services", self.services)
        self._patch(observers, "select_lab_body", lambda infos, flags: (self.sim_info, object()))
        self.control = self.new_control()

    def _patch(self, owner, name, value):
        patcher = mock.patch.object(owner, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_control(self):
        return self.e2c.E2Control(
            emit=lambda row: self.rows.append(row) or True,
            get_state=lambda: self.state[0],
            get_session_id=lambda: "0" * 32,
            get_armed_snapshot=lambda: {"guid": "2773024768", "slot_id": "2", "sim_id": "4242"},
            get_writer=lambda: None,
            output=lambda text, connection: None)

    def observation(self):
        return {"event_kind": "presence_snapshot", "body": {"sim_id": "4242"},
                "save": {"save_slot_guid": "2773024768", "slot_id": "2"},
                "game": {"ticks": 1000}}

    def tick(self):
        self.control.lineage_class = self.control.lineage_class or "CONTINUES_LAST_SAVE"
        return self.control.pace_row(self.observation())

    def command(self, need, slow, issuer=HELPER):
        connection = _Connection(issuer)
        return self.control.cmd_pace(need, slow, connection), connection

    def speed_events(self, phase):
        return [row["e2"] for row in self.rows if row.get("event_kind") == "speed_event"
                and row["e2"].get("phase") == phase]


class DrainTests(PaceFixture):
    def test_each_motive_is_slowed_once_across_ticks(self):
        self.assertTrue(self.command(0.5, 1.0)[0])
        for _ in range(4):
            self.tick()
        for commodity in self.motives:
            with self.subTest(guid=commodity.guid64):
                self.assertEqual(commodity.modifiers, [0.5])
                self.assertEqual(len(commodity.applied(0.5)), 1)
        self.assertEqual(self.other.modifiers, [])
        block = self.tick()
        self.assertEqual(block["motives_modified"], 6)
        self.assertEqual(block["need_drain"], 0.5)
        self.assertEqual(block["drain_measured"], 0.5)

    def test_a_rebuilt_tracker_gets_the_modifier_once_on_its_new_motives(self):
        self.command(0.5, 1.0)
        self.tick()
        old = self.motives
        self.motives = [_Commodity(guid) for guid in MOTIVE_GUIDS]
        self.tracker.commodities = self.motives
        self.tick()
        self.tick()
        for commodity in old:
            self.assertEqual([call[0] for call in commodity.calls if call[0] == "remove"], [])
        for commodity in self.motives:
            self.assertEqual(commodity.modifiers, [0.5])
            self.assertEqual(len(commodity.applied(0.5)), 1)

    def test_disarm_stop_and_not_sampling_remove_the_modifier(self):
        self.command(0.5, 1.0)
        self.tick()
        self.control.on_stop("STOP")
        for commodity in self.motives:
            self.assertEqual(commodity.modifiers, [])
            self.assertIn(("remove", 0.5), commodity.calls)
        self.state[0] = "ARMED"
        self.assertEqual(self.tick()["motives_modified"], 0)
        self.state[0] = "ARMED"
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)
        self.state[0] = "SAMPLING"
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[0.5]] * 6)
        self.control.on_disarm()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)

    def test_a_changed_factor_removes_the_old_one_then_applies_the_new(self):
        self.command(0.5, 1.0)
        self.tick()
        self.command(0.25, 1.0)
        self.tick()
        motive = self.motives[0]
        self.assertEqual([call for call in motive.calls if call[0] in ("add", "remove")],
                         [("add", 0.5), ("remove", 0.5), ("add", 0.25)])
        self.assertEqual(motive.modifiers, [0.25])
        self.assertEqual(self.tick()["drain_measured"], 0.25)

    def test_full_pace_applies_nothing_and_undoes_what_was_applied(self):
        self.command(1.0, 1.0)
        self.tick()
        self.assertEqual([m.calls for m in self.motives], [[]] * 6)
        self.command(0.5, 1.0)
        self.tick()
        self.command(1.0, 1.0)
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)
        self.assertIsNone(self.tick()["drain_measured"])

    def test_a_body_switch_or_a_zone_that_is_not_running_takes_it_off(self):
        self.command(0.5, 1.0)
        self.tick()
        self.control.lineage_class = "BODY_MISMATCH"
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)
        self.control.lineage_class = "CONTINUES_LAST_SAVE"
        self.tick()
        self.zone.is_zone_running = False
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)

    def test_a_motive_the_tracker_cannot_be_read_takes_nothing_new_and_undoes_the_old(self):
        self.command(0.5, 1.0)
        self.tick()
        self.sim_info.commodity_tracker = None
        self.tick()
        self.assertEqual([m.modifiers for m in self.motives], [[]] * 6)

    def test_clear_is_never_called_and_the_source_never_names_it(self):
        self.command(0.5, 1.0)
        self.tick()
        self.control.on_stop("STOP")
        path = os.path.join(os.path.dirname(self.e2c.__file__), "e2_control.py")
        with open(path, encoding="utf-8") as handle:
            self.assertNotIn("clear_decay_rate_modifiers", handle.read())
        for commodity in self.motives:
            self.assertFalse([call for call in commodity.calls if call[0] == "clear"])

    def test_an_unreadable_motive_read_raises_nothing_into_the_tick(self):
        self.sim_info.commodity_tracker = None
        self.command(0.5, 1.0)
        self.tick()
        self.assertEqual(self.tick()["motives_modified"], 0)


class ClockTests(PaceFixture):
    def test_a_clock_another_mod_owns_is_refused_and_never_touched(self):
        self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER = 1.2
        self.control = self.new_control()
        self.assertTrue(self.control._clock_foreign)
        self.assertTrue(self.command(1.0, 0.5)[0])
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 1.2)
        self.assertEqual(self.clock_service.syncs, 0)
        self.assertEqual(len(self.speed_events("CLOCK_FOREIGN")), 1)
        block = self.tick()
        self.assertTrue(block["clock_foreign"])
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 1.2)

    def test_a_clock_with_another_milliseconds_per_second_is_foreign_too(self):
        self.date.REAL_MILLISECONDS_PER_SIM_SECOND = 30
        self.control = self.new_control()
        self.assertTrue(self.control._clock_foreign)

    def test_the_clock_is_asserted_while_sampling_and_restored_when_not(self):
        self.assertFalse(self.control._clock_foreign)
        self.command(1.0, 0.5)
        self.tick()
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 0.5)
        self.assertEqual(self.clock_service.syncs, 1)
        self.tick()
        self.assertEqual(self.clock_service.syncs, 1)
        self.state[0] = "ARMED"
        self.tick()
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 1)
        self.assertEqual(self.clock_service.syncs, 2)

    def test_slow_time_back_to_one_restores_the_clock(self):
        self.command(1.0, 0.5)
        self.tick()
        self.command(1.0, 1.0)
        self.tick()
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 1)

    def test_stop_restores_the_clock_the_probe_slowed(self):
        self.command(1.0, 0.4)
        self.tick()
        self.control.on_stop("STOP")
        self.assertEqual(self.clock_module.GameClock.NORMAL_SPEED_MULTIPLIER, 1)

    def test_the_report_carries_the_wanted_factors_and_what_the_game_multiplies_by(self):
        self.command(0.5, 0.4)
        self.clock_service.scale = 0.4
        block = self.tick()
        self.assertEqual(block, {"need_drain": 0.5, "motives_modified": 6, "drain_measured": 0.5,
                                 "slow_time": 0.4, "clock_scale": 0.4, "clock_foreign": False})
        self.clock_service.scale = None
        self.assertIsNone(self.tick()["clock_scale"])


class CommandTests(PaceFixture):
    def test_only_the_helper_may_send_pace(self):
        ok, connection = self.command(0.5, 0.5, issuer="console")
        self.assertFalse(ok)
        self.assertEqual(connection.code, "BAD_ISSUER")
        self.assertEqual(self.tick()["need_drain"], 1.0)

    def test_values_outside_the_factor_range_or_not_numbers_are_refused(self):
        for need, slow in ((True, 0.5), (0.2, 0.5), (1.5, 0.5), (0.5, False), (float("nan"), 0.5),
                           ("0.5", 0.5), (0.5, None)):
            with self.subTest(need=need, slow=slow):
                ok, connection = self.command(need, slow)
                self.assertFalse(ok)
                self.assertEqual(connection.code, "BAD_ARGS")

    def test_the_last_values_hold_for_the_session(self):
        self.assertTrue(self.command(0.25, 0.25)[0])
        self.control.on_stop("STOP")
        block = self.tick()
        self.assertEqual((block["need_drain"], block["slow_time"]), (0.25, 0.25))

    def test_cmdbox_pace_shapes(self):
        base = {"v": 1, "id": "c" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
                "issuer": "helper", "command": "pace"}

        def check(args):
            return self.cmdbox.parse(json.dumps(dict(base, args=args)).encode("utf-8"), 1500, set())

        for good in ({"need_drain": 0.5, "slow_time": 1.0}, {"need_drain": 0.25, "slow_time": 0.25},
                     {"need_drain": 1, "slow_time": 1}):
            with self.subTest(good=good):
                self.assertIsNone(check(good)[1])
        for bad in ({"need_drain": 0.2, "slow_time": 1.0}, {"need_drain": 0.5, "slow_time": 1.01},
                    {"need_drain": True, "slow_time": 1.0}, {"need_drain": "0.5", "slow_time": 1.0},
                    {"need_drain": 0.5}, {"need_drain": 0.5, "slow_time": 1.0, "extra": 1}):
            with self.subTest(bad=bad):
                self.assertEqual(check(bad)[1], "BAD_ARGS")
        self.assertIn("pace", self.cmdbox.COMMANDS)
        self.assertIn("pace", self.schema.COMMANDS)

    def test_the_probe_dispatches_pace_to_the_helper_only(self):
        from ashley_e1 import probe
        probe_connection = probe._InboxReply(HELPER)
        self.assertTrue(probe._inbox_dispatch({"command": "pace", "args": {"need_drain": 0.5, "slow_time": 1.0}},
                                              probe_connection))
        self.assertEqual(probe_connection.lines[-1], "PACE_OK need_drain 0.5 slow_time 1")
        refused = probe._InboxReply("console")
        self.assertFalse(probe._inbox_dispatch({"command": "pace", "args": {"need_drain": 0.5, "slow_time": 1.0}},
                                               refused))
        self.assertEqual(refused.code, "BAD_ISSUER")


class ProbeRowTests(unittest.TestCase):
    """The probe's observation rows carry the block, validated by the schema, from a real poll."""

    def setUp(self):
        from test_e2 import ControlFlowTests
        self.base = ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        # One zone object for the whole test: the probe tells a stale tick by the zone's identity.
        self.zone = _Zone()
        self.base.services.current_zone = lambda: self.zone
        self.commodities = [_Commodity(guid) for guid in MOTIVE_GUIDS]
        info = self.base.services.sim_info_manager().get_all()[0]
        info.commodity_tracker = _Tracker(self.commodities)

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def start(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()

    def test_an_observation_carries_the_applied_pace_and_validates(self):
        from ashley_e1 import schema
        self.start()
        connection = self.probe._InboxReply(HELPER)
        self.assertTrue(self.probe._inbox_dispatch({"command": "pace", "args": {"need_drain": 0.5,
                                                                              "slow_time": 1.0}}, connection))
        self.base.tick()
        rows = self.base.rows("presence_snapshot")
        block = rows[-1]["pace"]
        self.assertEqual(block["need_drain"], 0.5)
        self.assertEqual(block["motives_modified"], 6)
        self.assertEqual([m.modifiers for m in self.commodities], [[0.5]] * 6)
        schema.validate_record(rows[-1])

    def test_the_schema_refuses_a_pace_block_out_of_bounds_or_off_an_observation(self):
        from ashley_e1 import schema
        self.start()
        row = self.base.rows("presence_snapshot")[-1]
        for block in (dict(row["pace"], need_drain=0.1), dict(row["pace"], slow_time=1.5),
                      dict(row["pace"], clock_foreign="no"), dict(row["pace"], motives_modified=99)):
            with self.subTest(block=block):
                with self.assertRaises(schema.SchemaError):
                    schema.validate_record(dict(row, pace=block))
        session = self.base.rows("session_open")[-1]
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(dict(session, pace=row["pace"]))

    def test_a_probe_without_the_pace_command_shows_normal_pace(self):
        self.start()
        block = self.base.rows("presence_snapshot")[-1]["pace"]
        self.assertEqual(block["need_drain"], 1.0)
        self.assertEqual(block["motives_modified"], 0)
        self.assertEqual([m.modifiers for m in self.commodities], [[]] * 6)


if __name__ == "__main__":
    unittest.main()
