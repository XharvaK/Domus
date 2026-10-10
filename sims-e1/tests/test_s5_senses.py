"""S5 (schema 7): relationships with present Sims, moodlet reason and time left, object
events, and the S1 extras. Game-shaped fakes, built from the 1.128 bytecode."""
import json
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

import test_ds3_senses as ds3
from test_binding import load_probe
from test_ds3_senses import _Wrapper
from test_ds1_senses import CreatingTrackers, stat_component_of


class LTR_Friendship_Main(object):
    pass


class LTR_Romance_Main(object):
    pass


class RelBit_Friends(object):
    visible = True
    display_name = _Wrapper(0x1111)


class RelBit_HasMet(object):
    visible = False
    display_name = _Wrapper(0x2222)


class _TrackTracker(object):
    def should_suppress_calculations(self):
        return True


def _track(value):
    return types.SimpleNamespace(_value=value, _last_update=4000, _tracker=_TrackTracker())


class _Relationship(object):
    def __init__(self):
        self._bi_directional_relationship_data = types.SimpleNamespace(
            _track_tracker=types.SimpleNamespace(_statistics={
                LTR_Romance_Main: _track(-3.0), LTR_Friendship_Main: _track(35.25)}),
            _bits={RelBit_Friends: object(), RelBit_HasMet: object()})

    def get_track_score(self, *args, **kwargs):
        raise AssertionError("the value getter is never called")


class _RelService(object):
    def __init__(self, relationships):
        self._relationships = relationships

    def get_relationship_score(self, *args, **kwargs):
        raise AssertionError("get_relationship_score can create a relationship")

    def _find_relationship(self, *args, **kwargs):
        raise AssertionError("_find_relationship can create a relationship")


class RelationshipTests(unittest.TestCase):
    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        services = sys.modules["services"]
        self.service = _RelService({(100, 200): _Relationship()})
        services.relationship_service = lambda: self.service

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_company_carries_the_relationship_as_the_game_holds_it(self):
        row = self.row()
        body, near, far = row["presence"]
        self.assertIsNone(body["relationship"])
        self.assertEqual(near["relationship"], {
            "known": True,
            "tracks": [{"track": "LTR_Friendship_Main", "value": 35.2},
                       {"track": "LTR_Romance_Main", "value": -3.0}],
            "labels": [{"label": "RelBit_Friends", "text_key": str(0x1111)}],
            # 2.15.0: this fake has no per-side data, so what she knows is unreadable.
            "knows": None, "sentiments": []})
        self.assertEqual(far["relationship"], {
            "known": False, "tracks": [], "labels": [],
            "knows": {"traits": [], "careers": None, "relationship_status": False,
                      "romantic_preference": False, "net_worth": None},
            "sentiments": []})

    def test_key_is_smaller_id_first_whichever_side_asks(self):
        observers = self.probe.observers
        self.assertTrue(observers.relationship_between("200", "100")["known"])
        self.assertTrue(observers.relationship_between("100", "200")["known"])

    def test_unreadable_service_is_none_not_an_error(self):
        sys.modules["services"].relationship_service = lambda: None
        self.assertIsNone(self.probe.observers.relationship_between("100", "200"))
        self.row()  # still validates


class _TimedCommodity(object):
    convergence_value = 0.0
    _last_update = 5000 - 1500 * 30  # 30 game minutes ago

    def _calculate_minutes_until_value_is_reached_through_decay(self, target):
        return 120.0


class Buff_Nauseous(object):
    mood_weight = 2
    mood_type = None
    visible = True
    buff_name = _Wrapper(0x3333)


class _TimedBuff(object):
    def __init__(self, owning, reason):
        self.guid64 = 77
        self.tuning_blueprint = Buff_Nauseous
        self._temporary_commodity_info = object()
        self._owning_commodity = owning
        self.buff_reason = reason

    @property
    def commodity(self):
        raise AssertionError("the commodity property can create a commodity (a store)")


class MoodletTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()

    def test_reason_and_minutes_left(self):
        owning = type("commodity_Buff_Nauseous", (object,), {})
        sim_info = CreatingTrackers()
        sim_info.get_component = stat_component_of(commodity={owning: _TimedCommodity()})
        reason = types.SimpleNamespace(hash=0xABC)
        row = self.probe.observers._describe_buff(_TimedBuff(owning, reason), sim_info, 5000)
        self.assertEqual((row["reason_key"], row["minutes_left"]), (str(0xABC), 90.0))

    def test_untimed_moodlet_has_no_minutes(self):
        buff = ds3.Buff(902, ds3.Buff_Hungry)
        row = self.probe.observers._describe_buff(buff, None, 5000)
        self.assertEqual((row["reason_key"], row["minutes_left"]), (None, None))


class _Obj(CreatingTrackers):
    is_sim = False

    def __init__(self, oid, x, states=None, cls_name="object_Food_PlateFork_Multi"):
        self.id = oid
        self.position = types.SimpleNamespace(x=x, y=0.0, z=0.0)
        self.level = 0
        self.definition = types.SimpleNamespace(id=555)
        self.state_component = types.SimpleNamespace(_states=dict(states or {}))
        self.__class__ = type(cls_name, (_Obj,), {})


class Freshness(object):
    pass


class Freshness_Fresh(object):
    pass


class Freshness_Spoiled(object):
    pass


class ObjectEventTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        self.observers = self.probe.observers
        self.observers._OBJECTS_PREV.update(zone=None, wall_ms=None, classes=None, near={})
        self.objects = {}
        manager = types.SimpleNamespace(_objects=self.objects)
        sys.modules["services"].object_manager = lambda: manager

    def read(self, wall_ms, zone="7"):
        return self.observers.read_object_events(zone, {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0},
                                                 wall_ms)

    def test_baseline_then_created_destroyed_and_near_state_changes(self):
        self.objects[1] = _Obj(1, 1.0, {Freshness: Freshness_Fresh})
        self.objects[2] = _Obj(2, 30.0, {Freshness: Freshness_Fresh}, "object_sinkPedC")
        self.objects[4] = _Obj(4, 12.0, {Freshness: Freshness_Fresh})
        first = self.read(1000)
        self.assertTrue(first["baseline"])
        self.assertEqual(first["created"] + first["destroyed"] + first["changed"], [])
        self.objects[1].state_component._states[Freshness] = Freshness_Spoiled
        self.objects[4].state_component._states[Freshness] = Freshness_Spoiled  # far: unseen
        del self.objects[2]
        self.objects[3] = _Obj(3, 2.0)
        second = self.read(2000)
        self.assertFalse(second["baseline"])
        self.assertEqual(second["created"], [{"object_id": "3",
                                              "class": "object_Food_PlateFork_Multi",
                                              "definition_id": "555"}])
        self.assertEqual(second["destroyed"], [{"object_id": "2", "class": "object_sinkPedC"}])
        self.assertEqual(second["changed"], [{"object_id": "1",
                                              "class": "object_Food_PlateFork_Multi",
                                              "state": "Freshness", "from": "Freshness_Fresh",
                                              "to": "Freshness_Spoiled"}])

    def test_a_pause_or_zone_change_starts_a_new_baseline(self):
        self.objects[1] = _Obj(1, 1.0)
        self.read(1000)
        self.objects[2] = _Obj(2, 1.0)
        self.assertTrue(self.read(60000)["baseline"])
        self.objects[3] = _Obj(3, 1.0)
        self.assertTrue(self.read(61000, zone="8")["baseline"])
        self.objects[4] = _Obj(4, 1.0)
        self.assertEqual([c["object_id"] for c in self.read(62000, zone="8")["created"]], ["4"])

    def test_events_are_capped_and_flagged(self):
        self.read(1000)
        for oid in range(10, 30):
            self.objects[oid] = _Obj(oid, 50.0)
        events = self.read(2000)
        self.assertEqual(len(events["created"]), 8)
        self.assertTrue(events["truncated"])


class SchemaTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        self.schema = self.probe.schema

    def _row(self, **payload):
        return self.schema.make_record(
            "presence_snapshot", telemetry_session_id="00000000-0000-4000-8000-000000000063",
            wall_timestamp_ms=1, monotonic_ns=1, observation_complete=True,
            attestation=self.schema.attestation("LAB_E1"),
            save={"save_slot_guid": "1", "slot_id": "2"},
            body={"sim_id": "3", "instantiated": True, "is_selectable": True,
                  "is_selected": None, "posture": None}, **payload)

    def test_objects_only_on_schema_7_observations(self):
        events = {"baseline": False, "created": [], "destroyed": [],
                  "changed": [{"object_id": "1", "class": "c", "state": "s", "from": None,
                               "to": "t"}], "truncated": False, "near_conditions": []}
        row = self._row()
        row["objects"] = events
        self.schema.validate_record(row)
        old = dict(row, schema_version=6)
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_record(old)
        other = self.schema.make_record("session_checkpoint",
                                        telemetry_session_id=row["telemetry_session_id"],
                                        checkpoint_reason="PERIODIC_60S")
        other["objects"] = None
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_record(other)
        bad = dict(row, objects=dict(events, changed=[{"object_id": "1"}]))
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_record(bad)

    def test_worst_case_with_objects_fits_and_keeps_social(self):
        from test_ds1_schema import full_presence, full_self, full_signal
        from ashley_e1 import snapshot
        entry = {"entry_key": "k", "interaction_id": "1", "affordance_id": "2",
                 "affordance_text": "t" * 160, "target_id": "3", "source_raw": "s",
                 "source_norm": "UNKNOWN", "source_confidence": "UNKNOWN",
                 "present": True, "membership": "QUEUED"}
        row = self._row(presence=[full_presence(i) for i in range(8)],
                        social=[dict(entry, actor_id="4") for _ in range(4)],
                        sim_signals=[full_signal() for _ in range(16)])
        row["self"] = full_self()
        long = "x" * 128
        row["objects"] = {"baseline": False, "truncated": False, "near_conditions": [],
                          "created": [{"object_id": "9" * 20, "class": long,
                                       "definition_id": "9" * 20}] * 8,
                          "destroyed": [{"object_id": "9" * 20, "class": long}] * 8,
                          "changed": [{"object_id": "9" * 20, "class": long, "state": long,
                                       "from": long, "to": long}] * 8}
        row = snapshot.apply_size_budget(row)
        self.schema.validate_record(row)
        self.assertLessEqual(len(self.schema.serialize_record(row)), 48 * 1024)
        self.assertEqual(len(row["social"]), 4)
        self.assertTrue(row["objects"]["truncated"])


class _Handler(object):
    def __init__(self, sim_id):
        self.sim = types.SimpleNamespace(id=sim_id)


class _Tag(object):
    def __init__(self, name):
        self.name = name


class _Decaying(object):
    _value = 120.0
    _last_update = 0
    convergence_value = -100.0

    class _tracker(object):
        @staticmethod
        def should_suppress_calculations():
            return False

    def _get_change_rate_without_decay(self):
        return -0.25

    def get_decay_rate(self):
        return 0.0

    def _calculate_minutes_until_value_is_reached_through_decay(self, target):
        return None


class commodity_freshness(object):
    pass


class SituationExtrasTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        self.probe.observers.get_room_id = lambda zone, position, level: 3

    def test_tags_users_and_rates(self):
        obj = _Obj(5, 1.0)
        obj.definition = types.SimpleNamespace(id=1, build_buy_tags=[_Tag("Func_Food"),
                                                                      _Tag("Func_Food")])
        obj._reservation_handlers = [_Handler(100)]
        obj.parts = [types.SimpleNamespace(_reservation_handlers=[_Handler(200)])]
        obj.get_component = stat_component_of(commodity={commodity_freshness: _Decaying()})
        row = self.probe.situation.object_fact(obj, 1500 * 10)
        self.assertEqual(row["tags"], ["Func_Food"])
        self.assertEqual((row["in_use"], row["used_by"]), (True, ["100", "200"]))
        self.assertEqual(row["rates"], {"commodity_freshness": -0.25})
        json.dumps(row)


if __name__ == "__main__":
    unittest.main()
