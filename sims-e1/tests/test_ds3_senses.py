"""DS3: company, place and moodlet blueprints, through the real poll_once."""
import os
import sys
import types
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    package = types.ModuleType("ashley_e1")
    package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = package

from test_binding import load_probe
from test_ds1_presence import FakeEntry, FakeSim
from test_ds1_senses import FakeBuffs, FakeSimInfo, FakeTracker


class _Wrapper(object):
    """TunableLocalizedStringFactory._Wrapper: the key is a plain attribute."""

    def __init__(self, key):
        self._string_id = key

    def __call__(self, *args):
        raise AssertionError("the probe reads the key; it never builds the string")


class Mood_Uncomfortable(object):
    pass


class Buff_Hungry(object):
    """A tuned buff blueprint (class attributes, as tuning loads them)."""
    mood_weight = 2
    mood_type = Mood_Uncomfortable
    visible = True
    buff_name = _Wrapper(0xc4338c38)


class Buff_HiddenTracker(object):
    mood_weight = 0
    mood_type = None
    visible = False
    buff_name = None


class Buff(object):
    """An active buff on 1.128 is an instance of the base Buff class; type(entry) is
    always "Buff" (live 2.11.5 rows) and its tuned data sits on tuning_blueprint."""
    mood_weight = 0

    def __init__(self, guid, blueprint):
        self.guid64 = guid
        self.tuning_blueprint = blueprint


class LabInfo(FakeSimInfo):
    """A SimInfo: has get_sim_instance (select_lab_body uses it)."""

    def __init__(self, sim_id, sim, buffs, first_name, last_name, household_id="hh1"):
        FakeSimInfo.__init__(self, FakeTracker(), buffs)
        self.id = sim_id
        self.household_id = household_id
        self.first_name = first_name
        self.last_name = last_name
        self.is_selectable = True
        self._sim = sim
        sim.sim_info = self

    def get_sim_instance(self, allow_hidden_flags=None):
        return self._sim


class OtherInfo(object):
    def __init__(self, sim_id, sim, first_name, household_id="hh2"):
        self.id = sim_id
        self.household_id = household_id
        self.first_name = first_name
        self.last_name = "Goth"
        self.is_selectable = False
        self._sim = sim
        sim.sim_info = self

    def get_sim_instance(self, allow_hidden_flags=None):
        return self._sim


class Manager(object):
    def __init__(self, infos):
        self._infos = infos

    def get_all(self):
        return list(self._infos)

    def instanced_sims_on_active_lot_gen(self, allow_hidden_flags=None,
                                         include_spawn_point=None):
        for info in self._infos:
            yield info._sim


class _Now(object):
    def absolute_ticks(self):
        return 5000

    def __str__(self):
        return "13:10:04.200 day:3 week:0"


class PollOnceTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        services = sys.modules["services"]
        self.body = FakeSim("100", level=0, at=(2.0, 3.0))
        self.body.si_state = []
        self.body.queue = []
        buffs = FakeBuffs([Buff(901, Buff_HiddenTracker), Buff(902, Buff_Hungry)])
        self.lab = LabInfo(100, self.body, buffs, "E1", "Proband")
        lab_sim = self.body
        far = FakeSim("300", level=0, at=(12.0, 3.0))
        far.si_state = [FakeEntry(31, "<class 'tv-watch-comedy'>", None,
                                  source="InteractionSource.AUTONOMY")]
        far.queue = []
        near = FakeSim("200", level=0, at=(3.0, 3.0))
        near.si_state = [FakeEntry(21, "<class 'sim-stand'>", None,
                                   source="InteractionSource.POSTURE_GRAPH"),
                         FakeEntry(22, "<class 'social_Chat'>", lab_sim,
                                   source="InteractionSource.AUTONOMY")]
        near.queue = []
        self.near = OtherInfo(200, near, "Bella")
        self.far = OtherInfo(300, far, "Mortimer")
        manager = Manager([self.lab, self.far, self.near])
        services.sim_info_manager = lambda: manager
        services.active_household = lambda: types.SimpleNamespace(id="hh1")
        services.time_service = lambda: types.SimpleNamespace(sim_now=_Now())
        services.game_clock_service = lambda: types.SimpleNamespace(
            clock_speed=types.SimpleNamespace(name="NORMAL"))
        services.get_persistence_service = lambda: types.SimpleNamespace(
            get_save_slot_proto_guid=lambda: 11,
            get_save_slot_proto_buff=lambda: types.SimpleNamespace(slot_id=12))
        services.current_zone_id = lambda: 777
        services.active_lot_id = lambda: 888
        self.probe.observers.get_room_id = (
            lambda zone_id, position, level: 3 if position.x < 5 else 4)

    def row(self):
        row = self.probe.observers.poll_once("00000000-0000-4000-8000-000000000063", "LAB_E1")
        self.probe.schema.validate_record(row)
        return row

    def test_place_is_filled(self):
        """DS3: zone, lot, room and position were null in every live row."""
        self.assertEqual(self.row()["zone"], {
            "zone_id": "777", "lot_id": "888", "room": "3",
            "position": {"x": 2.0, "y": 0.0, "z": 3.0, "level": 0}})

    def test_company_body_first_then_nearest(self):
        """D37: instanced_sims_on_active_lot_gen yields Sims; presence was always empty."""
        presence = self.row()["presence"]
        self.assertEqual([item["id"] for item in presence], ["100", "200", "300"])
        body, near, far = presence
        self.assertTrue(body["is_body"])
        self.assertEqual(body["name"], "E1 Proband")
        self.assertEqual(near["name"], "Bella Goth")
        self.assertEqual(near["distance_m"], 1.0)
        self.assertEqual(near["room"], "3")
        self.assertEqual(near["doing"], "<class 'social_Chat'>")
        self.assertEqual(near["doing_target"], "100")
        self.assertEqual(far["room"], "4")
        self.assertEqual(far["doing"], "<class 'tv-watch-comedy'>")
        self.assertFalse(near["active_household"])

    def test_social_runs_when_someone_is_here(self):
        """Social was gated on presence, so it never ran either."""
        social = self.row()["social"]
        self.assertEqual([(item["actor_id"], item["target_id"]) for item in social],
                         [("200", "100")])

    def test_moodlets_read_their_blueprint(self):
        """DS3: tuning_name was always "Buff" and every weight w:0."""
        signals = self.row()["sim_signals"]
        self.assertEqual(signals[0], {
            "kind": "MOODLET", "tuning_id": "902", "tuning_name": "Buff_Hungry",
            "game_text": None, "magnitude": "w:2", "consequences": None,
            "native_override": None, "text_key": str(0xc4338c38),
            "mood_type": "Mood_Uncomfortable", "visible": True})
        self.assertEqual(signals[1]["tuning_name"], "Buff_HiddenTracker")
        self.assertIs(signals[1]["visible"], False)

    def test_alone_has_no_social_and_only_the_body(self):
        services = sys.modules["services"]
        manager = Manager([self.lab])
        services.sim_info_manager = lambda: manager
        row = self.row()
        self.assertEqual([item["id"] for item in row["presence"]], ["100"])
        self.assertEqual(row["social"], [])

    def test_room_lookup_failure_is_null_not_an_error(self):
        def broken(*args):
            raise RuntimeError("no room")
        self.probe.observers.get_room_id = broken
        row = self.row()
        self.assertIsNone(row["zone"]["room"])
        self.assertEqual(row["presence"][1]["room"], None)


class StringKeyTests(unittest.TestCase):
    def test_factory_and_built_string(self):
        _, probe, _ = load_probe()
        key = probe.observers._string_key
        self.assertEqual(key(_Wrapper(5)), "5")
        self.assertEqual(key(types.SimpleNamespace(hash=7)), "7")
        self.assertIsNone(key(None))
        self.assertIsNone(key(_Wrapper(0)))
        self.assertIsNone(key(types.SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
