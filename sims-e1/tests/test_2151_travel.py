"""2.15.1, from the 2026-10-05 live trip on 2.15.0: sampling that stays alive across
lots (D43), no rows while a lot loads (D44), the lot first in presence (D45), and no
game settings among her traits (D46)."""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    package = types.ModuleType("ashley_e1")
    package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = package

import test_ds3_senses as ds3
from test_binding import FakeHandle, FakeWriter, load_probe
from test_bounds import clock_row, prepare_manual_writer
from test_ds1_presence import FakeSim
from test_ds1_senses import CreatingTrackers
from test_ds3_senses import OtherInfo, _Wrapper


class _Clock(object):
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class _Sampling(unittest.TestCase):
    def setUp(self):
        _, self.probe, self.calls = load_probe()
        services = sys.modules["services"]
        self.zone = object()
        services.current_zone = lambda: self.zone
        self.clock = _Clock()
        self.probe._now_s = self.clock
        self.assertTrue(self.probe._cmd_arm("LAB_E1_FORK"))
        self.assertTrue(self.probe._dispatch_start())
        self.writer = FakeWriter.instances[-1]
        self.polls = []

        def poll(*args, **kwargs):
            self.polls.append(args)
            raise self.probe.observers.LabIdentityAmbiguous(0)

        self.probe.observers.poll_once = poll

    def sampling_alarms(self):
        return [entry[0] for entry in self.calls["alarms"]
                if entry[2]["callback"] is self.probe._poll_tick]

    def reasons(self):
        return [row.get("checkpoint_reason") or row.get("reason") for row in self.writer.rows]

    def travel(self):
        self.zone = object()


class TravelHomeTests(_Sampling):
    """D43 (live 2.15.0): back home, sampling resumed and stopped a second later."""

    def test_the_old_lots_timer_is_cancelled_and_cannot_stop_sampling(self):
        old = self.sampling_alarms()[0]
        self.travel()
        self.assertTrue(self.probe._resume_sampling_in_zone())
        self.assertIn(old, self.calls["cancelled"])
        self.probe._poll_tick(old)  # the old lot's timer ticks once more
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.reasons(), ["ZONE_RESUMED"])

    def test_no_rows_while_the_next_lot_loads(self):
        """D44: rows from a loading lot showed her off the lot without half her skills."""
        self.travel()
        self.probe._poll_tick(self.sampling_alarms()[0])
        self.assertEqual(self.polls, [])
        self.assertEqual(self.writer.rows, [])
        self.assertEqual(self.probe._STATE, "SAMPLING")

    def test_a_failed_start_is_reported_once_and_retried(self):
        alarms = sys.modules["alarms"]
        working = alarms.add_alarm_real_time

        def refused(*args, **kwargs):
            raise RuntimeError("no time service yet")

        self.probe.alarms.add_alarm_real_time = refused
        self.travel()
        self.assertFalse(self.probe._resume_sampling_in_zone())
        self.assertFalse(self.probe._supervise_sampling())
        self.assertEqual(self.probe._STATE, "ARMED")
        self.assertEqual(self.reasons(), ["ZONE_RESUME_FAILED"])
        self.probe.alarms.add_alarm_real_time = working
        self.assertTrue(self.probe._supervise_sampling())
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.reasons(), ["ZONE_RESUME_FAILED", "ZONE_RESUMED"])
        for row in self.writer.rows:
            self.probe.schema.validate_record(row)

    def test_the_inbox_tick_resumes_a_zone_change_it_has_not_seen(self):
        self.travel()
        self.assertTrue(self.probe._supervise_sampling())
        self.assertIs(self.probe._ALARM_ZONE, self.zone)
        self.assertEqual(self.reasons(), ["ZONE_RESUMED"])

    def test_a_long_loading_screen_is_not_taken_for_a_stall(self):
        self.assertTrue(self.probe._supervise_sampling())  # watching before the trip
        self.travel()
        zone, self.zone = self.zone, None
        for _ in range(20):  # loading: no zone, the watch waits
            self.clock.now += 1
            self.probe._supervise_sampling()
        self.zone = zone
        self.clock.now += 1
        self.assertTrue(self.probe._supervise_sampling())
        for _ in range(3):
            self.clock.now += 1
            self.probe._supervise_sampling()
        self.assertEqual(self.reasons(), ["ZONE_RESUMED"])

    def test_the_inbox_tick_runs_the_watch(self):
        self.travel()
        self.probe._INBOX_HANDLE = FakeHandle()
        self.probe._inbox_tick()
        self.assertEqual(self.reasons(), ["ZONE_RESUMED"])

    def test_the_users_stop_is_never_undone(self):
        self.travel()
        self.assertTrue(self.probe._dispatch_stop())
        self.clock.now += 100
        self.assertFalse(self.probe._supervise_sampling())
        self.assertEqual(self.probe._STATE, "ARMED")


class StallTests(_Sampling):
    def setUp(self):
        _Sampling.setUp(self)
        self.assertTrue(self.probe._supervise_sampling())  # first look

    def look_every_second(self, seconds):
        for _ in range(int(seconds)):
            self.clock.now += 1
            self.probe._supervise_sampling()

    def test_a_sampler_that_stops_ticking_is_restarted(self):
        old = self.sampling_alarms()[0]
        self.look_every_second(11)
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertIn(old, self.calls["cancelled"])
        self.assertEqual(len(self.sampling_alarms()), 2)
        self.assertEqual(self.reasons(), ["SAMPLER_RESTARTED"])
        self.probe.schema.validate_record(self.writer.rows[0])

    def test_restarts_are_spaced(self):
        self.look_every_second(11)
        self.look_every_second(15)
        self.assertEqual(self.reasons(), ["SAMPLER_RESTARTED"])
        self.look_every_second(20)
        self.assertEqual(self.reasons(), ["SAMPLER_RESTARTED", "SAMPLER_RESTARTED"])

    def test_a_ticking_sampler_is_left_alone(self):
        for _ in range(30):
            self.clock.now += 1
            self.probe._poll_tick(self.sampling_alarms()[-1])
            self.probe._supervise_sampling()
        self.assertEqual(len(self.sampling_alarms()), 1)
        self.assertNotIn("SAMPLER_RESTARTED", self.reasons())

    def test_a_pause_of_the_whole_game_is_not_a_stall(self):
        self.clock.now += 60  # neither timer ran: the game itself was held
        self.probe._supervise_sampling()
        self.look_every_second(5)
        self.assertEqual(len(self.sampling_alarms()), 1)


class WriterFlushTests(unittest.TestCase):
    def test_rows_reach_the_disk_while_sampling_is_stopped(self):
        """D43: the guard and checkpoint rows of a stop sat in memory."""
        from ashley_e1 import writer
        with tempfile.TemporaryDirectory() as temp:
            sink = writer.TelemetryWriter(temp, "session-a", "1.0.0", "1.128.90.1030",
                                          autostart=False)
            prepare_manual_writer(sink)
            self.assertTrue(sink._write_physical(b"payload"))
            sink.set_sampling(False)
            sink._last_flush_monotonic = 10.0
            with mock.patch.object(writer.time, "perf_counter", return_value=16.0):
                with mock.patch.object(sink, "_attempt_flush",
                                       wraps=sink._attempt_flush) as flush:
                    self.assertTrue(sink._flush_if_due())
            self.assertEqual(flush.call_count, 1)
            sink._close_stream(reconcile=False)

    def test_the_last_row_before_a_quiet_spell_is_flushed(self):
        """The row that says why sampling stopped is often the last one for a while."""
        import time
        from ashley_e1 import writer
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(writer, "MAX_SAMPLING_FLUSH_INTERVAL_SECONDS", 0.3):
            sink = writer.TelemetryWriter(temp, "session-a", "1.0.0", "1.128.90.1030")
            self.assertTrue(sink.try_put(clock_row(1)))
            self.assertTrue(sink.try_put(clock_row(2)))
            deadline = time.time() + 3.0
            while sink._dirty or sink._queue.unfinished_tasks:
                if time.time() > deadline:
                    break
                time.sleep(0.02)
            flushed = not sink._dirty
            sink.signal_close("DISARM_CLEAN")
            self.assertTrue(sink.wait_idle(5.0))
            self.assertTrue(flushed)


class LotFirstTests(unittest.TestCase):
    """D45 (live 2.15.0): passers-by filled the cap of 8 and every row was incomplete."""

    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        manager = sys.modules["services"].sim_info_manager()
        for index in range(7):  # walkers on the street, nearer than the guest
            sim = FakeSim(str(400 + index), level=0, on_lot=False, at=(2.5, 3.0))
            sim.si_state, sim.queue = [], []
            manager._infos.append(OtherInfo(400 + index, sim, "Walker%d" % index))
        guest = FakeSim("500", level=0, at=(40.0, 3.0))
        guest.si_state, guest.queue = [], []
        manager._infos.append(OtherInfo(500, guest, "Guest"))

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_the_guest_on_the_lot_is_kept_and_the_row_stays_complete(self):
        row = self.row()
        ids = [item["id"] for item in row["presence"]]
        self.assertEqual(ids[:4], ["100", "200", "300", "500"])
        self.assertEqual(len(ids), 8)
        self.assertTrue(row["observation_complete"])
        self.assertNotIn("presence", row["missingness"])
        self.assertEqual(row["missingness"]["presence_nearby"],
                         {"status": "MISSING", "detail": "3 off the lot not listed"})

    def test_a_sim_on_the_lot_left_out_makes_the_row_incomplete(self):
        manager = sys.modules["services"].sim_info_manager()
        for index in range(6):
            sim = FakeSim(str(600 + index), level=0, at=(5.0, 3.0))
            sim.si_state, sim.queue = [], []
            manager._infos.append(OtherInfo(600 + index, sim, "Guest%d" % index))
        row = self.row()
        self.assertFalse(row["observation_complete"])
        self.assertEqual(row["missingness"]["presence"],
                         {"status": "MISSING", "detail": "2 on the lot not listed"})


class trait_Cheerful(object):
    display_name = _Wrapper(0x3001)
    trait_type = 0  # PERSONALITY


class trait_Likes_Music(object):
    display_name = _Wrapper(0x3003)
    trait_type = 22  # LIKE


class trait_GenderOptions_Toilet_Sitting(object):
    display_name = _Wrapper(0x3004)
    trait_type = 8  # GENDER_OPTIONS


class trait_Walkstyle_Default(object):
    display_name = _Wrapper(0x3005)
    trait_type = 2  # WALKSTYLE


class trait_NoType(object):
    display_name = _Wrapper(0x3006)


class SelfTraitTests(unittest.TestCase):
    """D46 (live 2.15.0): gender options and other settings took her 12 trait slots."""

    def test_game_settings_are_not_her_traits(self):
        _, probe, _ = load_probe()
        info = CreatingTrackers()
        info.trait_tracker = types.SimpleNamespace(
            _equipped_traits=[trait_GenderOptions_Toilet_Sitting, trait_Likes_Music,
                              trait_Walkstyle_Default, trait_Cheerful, trait_NoType],
            _equipped_personality_traits=[trait_Cheerful])
        names = [item["trait"] for item in probe.observers.read_self(info)["traits"]]
        self.assertEqual(names, ["trait_Cheerful", "trait_Likes_Music", "trait_NoType"])


if __name__ == "__main__":
    unittest.main()
