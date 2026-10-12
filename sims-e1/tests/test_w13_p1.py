"""W13-P1 (probe 2.40.0): her reach. The discovery record's shape, the lists her view counts (people, places, events:
parts, the 60-second check, the digest, the zone load and lists_now), the picker that takes the Sim she names (needs_sim,
act.sim_id, SIM_NEEDED, SIM_NOT_CHOOSABLE with its step), go and event with their phases and codes, a text for her, and
an incoming call held by its caller.

Fakes only. The game's calls are replaced by invented objects; the clock is a fake."""
import json
import os
import sys
import types
import unittest

import test_e2
from test_2160_act import GUID, ACT
from test_e2 import CHAIR

# The package is imported without its probe (test_schema's way): the pure modules need no game stubs. The probe itself is
# loaded by test_e2's setUp (load_probe), which installs them.
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    _package = types.ModuleType("ashley_e1")
    _package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = _package

from ashley_e1 import cmdbox  # noqa: E402
from ashley_e1 import act_menu  # noqa: E402
from ashley_e1 import reach  # noqa: E402
from ashley_e1 import schema  # noqa: E402


class _Clock(object):
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


class _Emitter(object):
    """Records each list row; fails the kinds it is told to refuse."""

    def __init__(self, ok=True):
        self.rows = []
        self.ok = ok

    def __call__(self, kind, row):
        self.rows.append((kind, row))
        return self.ok


def _raw(command, args):
    return json.dumps({"v": 1, "id": "a" * 32, "issued_at_ms": 1000, "expires_at_ms": 5000,
                       "issuer": "helper", "command": command, "args": args}).encode("utf-8")


def _parse(command, args):
    return cmdbox.parse(_raw(command, args), 2000, set())


class ListItemTests(unittest.TestCase):
    def test_a_person_keeps_ids_and_cuts_labels_and_tracks(self):
        item = reach.person_item({"sim_id": 123, "first_name": "Ana\x07 Example", "last_name": None,
                                  "labels": ["L1", "L2", "L3", "L4", "L5"], "tracks": {"T%d" % i: i for i in range(6)},
                                  "household_id": 9, "has_home": True, "on_lot": False, "waiting": True})
        self.assertEqual(item["sim_id"], "123")
        self.assertEqual(item["first_name"], "Ana Example")
        self.assertIsNone(item["last_name"])
        self.assertEqual(item["labels"], ["L1", "L2", "L3", "L4"])
        self.assertEqual(len(item["tracks"]), reach.TRACKS_PER_PERSON)
        self.assertEqual((item["has_home"], item["on_lot"], item["waiting"]), (True, False, True))

    def test_a_person_without_an_id_or_with_a_bool_id_is_left_out(self):
        self.assertIsNone(reach.person_item({"first_name": "Ana Example"}))
        self.assertIsNone(reach.person_item({"sim_id": True}))
        self.assertIsNone(reach.person_item({"sim_id": "12a"}))

    def test_an_unknown_flag_is_none_not_a_guess(self):
        item = reach.person_item({"sim_id": 5, "has_home": "yes", "on_lot": 1})
        self.assertIsNone(item["has_home"])
        self.assertIsNone(item["on_lot"])

    def test_a_place_needs_a_zone_and_a_known_kind(self):
        self.assertEqual(reach.place_item({"zone_id": 77, "kind": "home", "lot_name": "Test Lot"})["zone_id"], "77")
        self.assertIsNone(reach.place_item({"zone_id": 77, "kind": "garden"}))
        self.assertIsNone(reach.place_item({"kind": "home"}))

    def test_an_event_cost_is_an_int_or_none(self):
        self.assertEqual(reach.event_item({"situation_id": 4, "cost": 250, "schedulable": True})["cost"], 250)
        self.assertIsNone(reach.event_item({"situation_id": 4, "cost": "250"})["cost"])
        self.assertIsNone(reach.event_item({"situation_id": 4, "cost": True})["cost"])

    def test_clean_items_are_unique_by_id_and_capped(self):
        entries = [{"sim_id": 1 + (i // 2)} for i in range(400)]
        items = reach.clean_items("people", entries)
        self.assertEqual(len(items), reach.PEOPLE_MAX)
        self.assertEqual(len(set(item["sim_id"] for item in items)), reach.PEOPLE_MAX)

    def test_none_entries_are_unreadable_and_stay_unwritten(self):
        self.assertIsNone(reach.clean_items("people", None))

    def test_parts_hold_at_most_128_items_and_an_empty_list_is_one_part(self):
        parts = reach.split_parts([{"n": i} for i in range(300)])
        self.assertEqual([len(part) for part in parts], [128, 128, 44])
        self.assertEqual(reach.split_parts([]), [[]])

    def test_the_digest_is_the_same_for_the_same_items_in_any_key_order(self):
        self.assertEqual(reach.digest([{"a": 1, "b": 2}]), reach.digest([{"b": 2, "a": 1}]))
        self.assertNotEqual(reach.digest([{"a": 1}]), reach.digest([{"a": 2}]))


class ListWriterTests(unittest.TestCase):
    def _readers(self, people=None):
        state = {"people": [{"sim_id": 1}] if people is None else people}
        readers = {"people": lambda: state["people"], "events": lambda: [{"situation_id": 9}]}
        return state, readers

    def test_a_list_is_written_when_it_is_first_read_and_not_again_while_unchanged(self):
        clock = _Clock(0.0)
        emit = _Emitter()
        writer = reach.ListWriter(emit, clock=clock)
        state, readers = self._readers()
        self.assertEqual(writer.tick(readers), ["people", "events"])
        self.assertEqual(len(emit.rows), 2)
        clock.now = 61.0
        self.assertEqual(writer.tick(readers), [])
        self.assertEqual(len(emit.rows), 2)

    def test_a_list_is_read_at_most_once_every_sixty_seconds(self):
        clock = _Clock(0.0)
        reads = []
        writer = reach.ListWriter(_Emitter(), clock=clock)
        readers = {"people": lambda: reads.append(clock.now) or [{"sim_id": 1}]}
        writer.tick(readers)
        clock.now = 30.0
        writer.tick(readers)
        clock.now = 60.0
        writer.tick(readers)
        self.assertEqual(reads, [0.0, 60.0])

    def test_a_change_is_written_with_the_next_revision(self):
        clock = _Clock(0.0)
        emit = _Emitter()
        writer = reach.ListWriter(emit, clock=clock)
        state, readers = self._readers()
        writer.tick(readers)
        state["people"] = [{"sim_id": 1}, {"sim_id": 2}]
        clock.now = 120.0
        self.assertEqual(writer.tick(readers), ["people"])
        revs = [row["list_rev"] for kind, row in emit.rows if kind == "people"]
        self.assertEqual(revs, [1, 2])
        self.assertEqual(emit.rows[-1][1]["count"], 2)

    def test_a_forced_tick_reads_every_list_now(self):
        clock = _Clock(0.0)
        writer = reach.ListWriter(_Emitter(), clock=clock)
        state, readers = self._readers()
        writer.tick(readers)
        clock.now = 5.0
        self.assertEqual(writer.tick(readers, force=True), [])
        state["people"] = [{"sim_id": 3}]
        self.assertEqual(writer.tick(readers, force=True), ["people"])

    def test_an_unreadable_list_writes_nothing_and_is_read_again(self):
        clock = _Clock(0.0)
        emit = _Emitter()
        writer = reach.ListWriter(emit, clock=clock)
        writer.tick({"people": lambda: None})
        self.assertEqual(emit.rows, [])
        clock.now = 61.0
        self.assertEqual(writer.tick({"people": lambda: [{"sim_id": 1}]}), ["people"])

    def test_a_refused_row_keeps_the_list_unwritten_until_the_next_read(self):
        clock = _Clock(0.0)
        emit = _Emitter(ok=False)
        writer = reach.ListWriter(emit, clock=clock)
        self.assertEqual(writer.tick({"people": lambda: [{"sim_id": 1}]}), [])
        emit.ok = True
        clock.now = 61.0
        self.assertEqual(writer.tick({"people": lambda: [{"sim_id": 1}]}), ["people"])

    def test_a_new_zone_keeps_the_digests_and_restarts_the_check_clock(self):
        clock = _Clock(0.0)
        emit = _Emitter()
        writer = reach.ListWriter(emit, clock=clock)
        readers = {"people": lambda: [{"sim_id": 1}]}
        writer.tick(readers)
        writer.new_zone()
        self.assertEqual(writer.tick(readers), [])
        self.assertEqual(len(emit.rows), 1)


class DiscoveryAndPhoneTests(unittest.TestCase):
    def test_a_discovery_record_keeps_its_known_sections_and_drops_the_largest_over_budget(self):
        big = [{"name": "x" * 200, "n": i} for i in range(400)]
        kept = reach.discovery_sections({"save": {"slot_ok": True}, "pickers": big, "unknown": 1})
        self.assertNotIn("unknown", kept)
        self.assertNotIn("pickers", kept)
        self.assertEqual(kept["dropped"], ["pickers"])
        self.assertEqual(kept["save"], {"slot_ok": True})

    def test_a_picker_row_names_ids_and_flags_only(self):
        row = reach.picker_row("PickFriend", 42, 1, "SimFilter", ["include_actor_sim", "", None], 4.5,
                               {123: "ok", None: "hidden", 456: None})
        self.assertEqual(row["guid64"], "42")
        self.assertIsNone(row["radius"])
        self.assertEqual(row["flags"], ["include_actor_sim"])
        self.assertEqual([step["sim_id"] for step in row["steps"]], ["123", "456"])
        self.assertIsNone(row["steps"][1]["step"])

    def test_a_phone_event_is_a_text_or_a_call(self):
        self.assertEqual(reach.phone_event("text", 77, 88), {"kind": "text", "from_sim_id": "77", "notifies": "88"})
        self.assertEqual(reach.phone_event("call", None, None)["kind"], "call")
        self.assertIsNone(reach.phone_event("email", 77, None))

    def test_a_work_end_is_a_minute_of_the_day(self):
        self.assertEqual(reach.work_end_minute((17, 0)), 1020)
        self.assertIsNone(reach.work_end_minute((24, 0)))
        self.assertIsNone(reach.work_end_minute((None, 5)))

    def test_a_start_is_absolute_and_never_in_the_past(self):
        day = 3
        now_min = 600
        self.assertEqual(reach.start_minute(0, 11, 0, now_min, day), day * 1440 + 660)
        self.assertEqual(reach.start_minute(1, 9, 30, now_min, day), (day + 1) * 1440 + 570)
        self.assertIsNone(reach.start_minute(0, 9, 0, now_min, day))
        self.assertIsNone(reach.start_minute(2, 9, 0, now_min, day))
        self.assertIsNone(reach.start_minute(0, 25, 0, now_min, day))

    def test_guest_ids_are_digits_and_at_most_the_limit(self):
        self.assertEqual(reach.sim_ids(["1", "22"], 16), ["1", "22"])
        self.assertIsNone(reach.sim_ids(["1", "x"], 16))
        self.assertIsNone(reach.sim_ids(["1"] * 17, 16))


class SchemaTests(unittest.TestCase):
    def _e2_row(self, kind, payload):
        return schema.make_record(kind, telemetry_session_id="s" * 32, wall_timestamp_ms=1, monotonic_ns=1,
                                  e2=payload)

    def test_a_list_row_validates(self):
        payload = {"kind": "people", "list_rev": 1, "part": 0, "parts": 1, "digest": "a" * 64, "count": 1,
                   "items": [{"sim_id": "1"}]}
        schema.validate_record(self._e2_row("lists", payload))

    def test_a_discovery_row_validates(self):
        payload = {"discovery_rev": 1, "sections": {"save": {"slot_ok": True}}}
        schema.validate_record(self._e2_row("discovery", payload))

    def test_a_phone_row_validates(self):
        schema.validate_record(self._e2_row("phone", {"kind": "text", "from_sim_id": "7", "notifies": None}))

    def test_a_list_kind_outside_the_vocabulary_is_refused(self):
        payload = {"kind": "rooms", "list_rev": 1, "part": 0, "parts": 1, "digest": "a" * 64, "count": 0, "items": []}
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(self._e2_row("lists", payload))

    def test_an_act_result_is_plain_facts_and_bounded(self):
        act = {"act_id": ACT, "phase": "FINISHED", "code": "ARRIVED", "object_id": None, "guid64": None,
               "result": {"zone_id": "55"}}
        row = self._e2_row("act_event", dict(dict.fromkeys(schema.E2_PAYLOAD_KEYS["act_event"]), **act))
        schema.validate_record(row)
        act["result"] = {"words": "x" * 600}
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(self._e2_row("act_event", dict(dict.fromkeys(schema.E2_PAYLOAD_KEYS["act_event"]), **act)))

    def test_a_waiting_visitor_is_an_optional_flag_on_a_situation(self):
        schema._validate_situations([{"situation": "s", "role": "r"}, {"situation": "s", "role": "r", "waiting": True}])
        with self.assertRaises(schema.SchemaError):
            schema._validate_situations([{"situation": "s", "role": "r", "waiting": "yes"}])

    def test_a_phone_kind_outside_the_vocabulary_is_refused(self):
        with self.assertRaises(schema.SchemaError):
            schema._validate_reach("phone", {"kind": "rooms", "from_sim_id": None, "notifies": None})

    def test_a_menu_act_may_carry_needs_sim(self):
        self.assertIn("needs_sim", schema.MENU_ACT_OPTIONAL_KEYS)


class CommandWireTests(unittest.TestCase):
    def test_an_act_may_name_a_sim(self):
        cmd, reason = _parse("act", {"act_id": ACT, "object_id": "12", "guid64": "34", "sim_id": "56"})
        self.assertIsNone(reason)
        self.assertEqual(cmd["args"]["sim_id"], "56")
        cmd, reason = _parse("act", {"act_id": ACT, "object_id": "12", "guid64": "34", "sim_id": "five"})
        self.assertEqual(reason, "BAD_ARGS")

    def test_go_takes_an_act_and_a_zone(self):
        self.assertIsNone(_parse("go", {"act_id": ACT, "zone_id": "55"})[1])
        self.assertEqual(_parse("go", {"act_id": ACT})[1], "BAD_ARGS")
        self.assertEqual(_parse("go", {"act_id": ACT, "zone_id": "x"})[1], "BAD_ARGS")

    def test_event_takes_a_situation_guests_and_a_start(self):
        self.assertIsNone(_parse("event", {"act_id": ACT, "situation_id": "9", "guests": ["1", "2"],
                                           "start": "now"})[1])
        start = {"day_offset": 1, "hour": 9, "minute": 30}
        self.assertIsNone(_parse("event", {"act_id": ACT, "situation_id": "9", "guests": [], "start": start})[1])
        bad = dict(start, day_offset=2)
        self.assertEqual(_parse("event", {"act_id": ACT, "situation_id": "9", "guests": [], "start": bad})[1],
                         "BAD_ARGS")
        self.assertEqual(_parse("event", {"act_id": ACT, "situation_id": "9", "guests": ["1"] * 17,
                                          "start": "now"})[1], "BAD_ARGS")

    def test_lists_now_takes_no_arguments(self):
        self.assertIsNone(_parse("lists_now", {})[1])
        self.assertEqual(_parse("lists_now", {"x": 1})[1], "BAD_ARGS")

    def test_the_new_commands_are_in_the_closed_vocabulary(self):
        for name in ("go", "event", "lists_now"):
            self.assertIn(name, cmdbox.COMMANDS)
            self.assertIn(name, schema.COMMANDS)


class MenuFlagTests(unittest.TestCase):
    def _build(self, jobs):
        build = act_menu.MenuBuild(jobs, lambda job: True, budget_ms=1000.0, max_per_chunk=100)
        for _ in range(4):
            build.step()
        return build.payload(1, "4")

    def test_a_picker_act_carries_needs_sim_and_no_other_act_does(self):
        jobs = [{"object_id": "300", "definition_id": None, "class": "phone", "distance_m": None, "same_room": None,
                 "room": None, "phone": True, "on_lot": True, "guid64": "10", "name": "CallPickFriend",
                 "text_key": None, "needs_sim": True},
                {"object_id": "300", "definition_id": None, "class": "phone", "distance_m": None, "same_room": None,
                 "room": None, "phone": True, "on_lot": True, "guid64": "11", "name": "CallNobody",
                 "text_key": None, "needs_sim": None}]
        payload = self._build(jobs)
        acts = payload["objects"][0]["acts"]
        self.assertEqual(acts[0].get("needs_sim"), True)
        self.assertNotIn("needs_sim", acts[1])
        for act in acts:
            self.assertTrue(set(act) - set(schema.MENU_ACT_OPTIONAL_KEYS) == set(schema.MENU_ACT_KEYS))


class _PickerClass(object):
    """A Sim picker, as the game's picker classes are named in the class chain (fake)."""


class SimPickerInteraction(_PickerClass):
    pass


class PickFriend(SimPickerInteraction):
    __name__ = "CallPickFriendSuperInteraction"
    guid64 = int(GUID)
    allow_user_directed = True


class CallPieMenu(object):
    __name__ = "CallPieMenu"
    guid64 = 4001
    allow_user_directed = True


class CallSimPieMenu(SimPickerInteraction):
    __name__ = "CallSimPieMenu"
    guid64 = 4002
    allow_user_directed = True


class ActorSims(object):
    def __init__(self, sim_id):
        self.id = sim_id


class ActorActuatorTests(unittest.TestCase):
    def _actuator(self):
        """The probe's actuator module, loaded with the game stubs (test_e2's setUp loads the probe)."""
        base = test_e2.ControlFlowTests()
        base.setUp()
        return base.probe.e2_actuator

    def test_a_sim_picker_is_read_down_the_class_chain(self):
        e2_actuator = self._actuator()
        self.assertTrue(e2_actuator.needs_sim(PickFriend))
        self.assertFalse(e2_actuator.needs_sim(CallPieMenu))

    def test_a_phone_pie_menu_is_listed_only_when_it_asks_for_a_sim(self):
        e2_actuator = self._actuator()
        self.assertEqual(e2_actuator.phone_act_excluded(CallPieMenu), "pie_picker")
        self.assertIsNone(e2_actuator.phone_act_excluded(CallSimPieMenu))

    def test_the_picker_takes_the_sim_she_named(self):
        e2_actuator = self._actuator()
        info = ActorSims(123)
        self.assertEqual(e2_actuator.picker_parameters(info, "123"),
                         {"picked_item_ids": frozenset({123}), "included_override": [info]})
        self.assertIsNone(e2_actuator.picker_parameters(None, "123"))


class ReachActTests(unittest.TestCase):
    """The act and the verbs through the probe's inbox, with the fakes of test_e2 (a Sim, a chair, a clock)."""

    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.base.objects[CHAIR] = _Offer(CHAIR, [PickFriend])
        self.pushed = []
        self.tested = []
        sim = self.base.sim
        original = sim.push_super_affordance

        def push(affordance, target, context, **kwargs):
            self.pushed.append(kwargs)
            return original(affordance, target, context)

        def test(affordance, target, context, **kwargs):
            self.tested.append(kwargs)
            return True

        sim.push_super_affordance = push
        sim.test_super_affordance = test
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

    def act(self, **extra):
        args = {"act_id": ACT, "object_id": CHAIR, "guid64": GUID}
        args.update(extra)
        return self.send("act", args)

    def act_events(self, phase=None):
        return [row for row in self.base.e2("act_event") if phase is None or row["phase"] == phase]

    def test_a_picker_act_without_a_sim_asks_for_one(self):
        self.ready()
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT SIM_NEEDED")
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "SIM_NEEDED")
        self.assertEqual(self.pushed, [])

    def test_a_picker_takes_the_sim_she_named_as_its_parameters(self):
        self.ready()
        info = ActorSims(123)
        with _patched(self.probe.e2_actuator, "sim_info_for", lambda sim_id: info), \
                _patched(self.probe.observers, "read_picker_steps", lambda her, sims: {"123": "ok"}), \
                _patched(self.probe.observers, "her_sim_info", lambda: None):
            ok, connection = self.act(sim_id="123")
        self.assertTrue(ok)
        self.assertEqual(self.pushed, [{"picked_item_ids": frozenset({123}), "included_override": [info]}])
        self.assertEqual(self.act_events()[-1]["phase"], "PUSHED")

    def test_a_sim_the_picker_cannot_choose_is_refused_with_its_step(self):
        self.ready()
        info = ActorSims(123)
        with _patched(self.probe.e2_actuator, "sim_info_for", lambda sim_id: info), \
                _patched(self.probe.observers, "read_picker_steps", lambda her, sims: {"123": "hidden"}), \
                _patched(self.probe.observers, "her_sim_info", lambda: None):
            ok, connection = self.act(sim_id="123")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT SIM_NOT_CHOOSABLE")
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("SIM_NOT_CHOOSABLE", "step hidden"))
        self.assertEqual(self.pushed, [])

    def test_a_sim_given_to_an_act_that_is_not_a_picker_is_refused(self):
        self.ready()
        self.base.objects[CHAIR] = _Offer(CHAIR, [_Plain])
        ok, _connection = self.act(guid64=str(_Plain.guid64), sim_id="123")
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NOT_A_SIM_ACT")

    def test_a_trip_to_a_place_she_does_not_know_is_refused(self):
        self.ready()
        ok, connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NO_ZONE")

    def test_a_trip_is_asked_then_finished_once_she_is_in_the_zone(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        travelled = []
        with _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: travelled.append((sim_id, zone_id)) or True), \
                _patched(self.base.services, "current_zone_id", lambda: 1):
            ok, connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.assertTrue(ok)
        self.assertEqual(connection.lines[-1], "ACT_PUSHED %s travel" % ACT)
        self.assertEqual([row["phase"] for row in self.act_events()], ["ACCEPTED", "PUSHED"])
        with _patched(self.base.services, "current_zone_id", lambda: 55):
            self.probe._E2.tick_verbs()
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"], last["result"]), ("FINISHED", "ARRIVED", {"zone_id": "55"}))
        self.assertEqual(len(travelled), 1)

    def test_a_trip_that_never_arrives_is_unknown_after_five_minutes(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        with _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: True), \
                _patched(self.base.services, "current_zone_id", lambda: 1):
            self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.probe._E2._go["at"] -= 301.0
        with _patched(self.base.services, "current_zone_id", lambda: 1):
            self.probe._E2.tick_verbs()
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "TRAVEL_UNSEEN"))

    def test_a_planned_event_is_created_for_her_and_its_facts_are_written(self):
        self.ready()
        situation = types.SimpleNamespace(name="party")
        created = []
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: situation), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 2 * 1440 + 600), \
                _patched(self.probe.e2_actuator, "situation_cost", lambda s: 0), \
                _patched(self.probe.e2_actuator, "default_job", lambda s: "job"), \
                _patched(self.probe.e2_actuator, "event_guest_list", lambda host, guests, job: ("list", guests)), \
                _patched(self.probe.e2_actuator, "create_event", lambda zone, s, guest_list, when: created.append((zone, guest_list, when)) or "909"), \
                _patched(self.probe.observers, "household_money", lambda info: 500):
            ok, connection = self.send("event", {"act_id": ACT, "situation_id": "9", "guests": ["4"], "start": "now"})
        self.assertTrue(ok)
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("FINISHED", "CREATED"))
        self.assertEqual(last["result"], {"cost": 0, "funds": 500, "start_min": 2 * 1440 + 600})
        self.assertEqual(created[0][1], ("list", ["4"]))

    def test_an_event_her_household_cannot_pay_for_is_refused(self):
        self.ready()
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: object()), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000), \
                _patched(self.probe.e2_actuator, "situation_cost", lambda s: 300), \
                _patched(self.probe.observers, "household_money", lambda info: 100):
            ok, _connection = self.send("event", {"act_id": ACT, "situation_id": "9", "guests": [], "start": "now"})
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NO_FUNDS")

    def test_a_failed_creation_gives_the_money_back(self):
        self.ready()
        refunds = []
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: object()), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000), \
                _patched(self.probe.e2_actuator, "situation_cost", lambda s: 300), \
                _patched(self.probe.e2_actuator, "default_job", lambda s: "job"), \
                _patched(self.probe.e2_actuator, "event_guest_list", lambda *args: "list"), \
                _patched(self.probe.e2_actuator, "charge", lambda household, amount, sim, reason: True), \
                _patched(self.probe.e2_actuator, "create_event", lambda *args: None), \
                _patched(self.probe.e2_actuator, "refund", lambda household, amount, sim, reason: refunds.append(amount) or True), \
                _patched(self.probe.observers, "household_money", lambda info: 1000):
            ok, _connection = self.send("event", {"act_id": ACT, "situation_id": "9", "guests": [], "start": "now"})
        self.assertFalse(ok)
        self.assertEqual(refunds, [300])
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "CREATE_FAILED")

    def test_a_text_for_her_is_written_as_a_phone_row(self):
        self.ready()
        op = types.SimpleNamespace(sim_id=999)
        with _patched(self.probe.observers, "her_sim_info", lambda: None):
            self.probe._E2.note_phone(op)
        rows = self.base.e2("phone")
        self.assertEqual(rows[-1]["kind"], "text")
        self.assertEqual(rows[-1]["from_sim_id"], "999")

    def test_a_call_from_another_sim_is_held_for_her(self):
        caller = types.SimpleNamespace(target_sim_id=77)
        with _patched(self.probe.observers, "active_sim_id", lambda: "5"):
            self.assertTrue(self.probe._E2._ring_for_her(caller))
        with _patched(self.probe.observers, "active_sim_id", lambda: "77"):
            self.assertFalse(self.probe._E2._ring_for_her(caller))

    def test_lists_now_asks_for_a_fresh_read(self):
        self.assertTrue(self.probe.request_lists_now())
        self.assertTrue(self.probe._LISTS_FORCE)
        self.probe._LISTS_FORCE = False


class _Offer(object):
    def __init__(self, object_id, affordances):
        self.id = int(object_id)
        self._affordances = affordances

    def super_affordances(self, context=None):
        for item in self._affordances:
            yield item


class _Plain(object):
    __name__ = "ReadBook"
    guid64 = 4250
    allow_user_directed = True


class _patched(object):
    """Replaces one attribute for the length of a with block (restored even when the block raises)."""

    def __init__(self, owner, name, value):
        self.owner = owner
        self.name = name
        self.value = value

    def __enter__(self):
        self.saved = self.owner.__dict__[self.name] if self.name in self.owner.__dict__ else None
        self.had = self.name in self.owner.__dict__
        setattr(self.owner, self.name, self.value)
        return self.value

    def __exit__(self, *exc):
        if self.had:
            setattr(self.owner, self.name, self.saved)
        else:
            delattr(self.owner, self.name)
        return False


class Bit_Example_Friend(object):
    """A relationship bit (invented)."""


_Bit = Bit_Example_Friend


class _Target(object):
    id = 55
    first_name = "Ana"
    last_name = "Example"
    household_id = 9

    def get_sim_instance(self):
        return None


class _Tracker(object):
    def get_target_sim_infos(self):
        return [_Target()]

    def get_all_bits(self, target_id):
        return [_Bit] if target_id == 55 else []

    def is_hidden(self, target_id):
        return False


class _Her(object):
    id = 1
    household_id = 9
    relationship_tracker = _Tracker()


class _Home(object):
    home_zone_id = 77


class _Work(object):
    def hour(self):
        return 17

    def minute(self):
        return 30


class _Career(object):
    _current_work_end = _Work()


class ObserverReadTests(unittest.TestCase):
    """The game's reads, with invented game objects: each reader gives its record's shape, and none raises."""

    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers

    def ready(self):
        """Armed and sampling, so the probe's rows carry a telemetry session."""
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.base.probe._cmd_arm("HOME"))
        self.assertTrue(self.base.probe._cmd_start())
        self.base.tick()

    def test_people_are_her_relationships_with_their_bits_and_home(self):
        services = self.base.services
        with _patched(services, "household_manager", lambda: types.SimpleNamespace(get=lambda hid: _Home())):
            people = self.observers.read_people(_Her(), waiting=set())
        self.assertEqual(len(people), 1)
        self.assertEqual(reach.person_item(people[0])["sim_id"], "55")
        self.assertEqual(people[0]["labels"], ["Bit_Example_Friend"])
        self.assertEqual((people[0]["has_home"], people[0]["on_lot"], people[0]["waiting"]), (True, False, False))
        self.assertEqual(people[0]["first_name"], "Ana")
        self.assertIsNone(self.observers.read_people(None))

    def test_places_are_her_home_and_the_homes_of_the_households_she_knows(self):
        services = self.base.services
        with _patched(services, "household_manager", lambda: types.SimpleNamespace(get=lambda hid: _Home())):
            places = self.observers.read_places(_Her(), [{"household_id": 9}, {"household_id": 12}])
        self.assertEqual([(place["zone_id"], place["kind"]) for place in places], [("77", "home"), ("77", "household")])
        self.assertEqual(places[1]["household_id"], "12")

    def test_events_are_the_user_facing_situation_types_with_cost(self):
        typed = types.SimpleNamespace(creation_ui_option=1, guid64=9001, cost=250)
        hidden = types.SimpleNamespace(creation_ui_option=0, guid64=9002, cost=10)
        manager = types.SimpleNamespace(types={1: typed, 2: hidden})
        services = self.base.services
        with _patched(services, "get_instance_manager", lambda kind: manager), \
                _patched(self.observers, "ResourceTypes", types.SimpleNamespace(SITUATION=1)):
            events = self.observers.read_events()
        self.assertEqual(events, [{"situation_id": 9001, "name_key": None, "cost": 250, "schedulable": None}])

    def test_a_work_session_ends_at_a_minute_of_the_day(self):
        self.assertEqual(self.observers.work_until_min(_Career()), 17 * 60 + 30)
        self.assertIsNone(self.observers.work_until_min(object()))

    def test_a_visitor_waiting_is_a_waiting_role(self):
        self.assertTrue(self.observers.waiting_role("RoleState_WaitingToBeGreeted"))
        self.assertFalse(self.observers.waiting_role("RoleState_Host"))
        self.assertFalse(self.observers.waiting_role(None))

    def test_the_save_section_never_names_the_slot(self):
        persistence = types.SimpleNamespace(
            get_save_slot_proto_buff=lambda: types.SimpleNamespace(slot_id=2, slot_name="Test Slot"),
            is_save_locked=lambda: False)
        with _patched(self.base.services, "get_persistence_service", lambda: persistence):
            section = self.observers.read_save_discovery()
        self.assertEqual(section, {"slot_ok": True, "slot_named": True, "cooldown_s": None, "locked": False})

    def test_the_discovery_record_keeps_what_was_read(self):
        with _patched(self.base.services, "get_persistence_service", lambda: None), \
                _patched(self.observers, "read_events", lambda: None):
            record = self.observers.read_discovery(None, [{"name": "P"}], None)
        self.assertEqual(record["pickers"], [{"name": "P"}])
        self.assertNotIn("phone_tests", record)
        self.assertNotIn("situations", record)

    def test_a_tick_writes_the_lists_and_the_discovery_once_per_zone(self):
        self.ready()
        rows = []
        writer = reach.ListWriter(self.base.probe._lists_emit, clock=_Clock(0.0))
        writer_patch = _patched(self.base.probe, "_LISTS", writer)
        with writer_patch, \
                _patched(self.base.probe, "_LISTS_ZONE", object()), \
                _patched(self.base.probe, "_DISCOVERY_ZONE", object()), \
                _patched(self.base.probe._E2, "_zone_running", lambda: True), \
                _patched(self.base.probe, "_write_discovery", lambda: rows.append("discovery")), \
                _patched(self.observers, "read_people", lambda info: [{"sim_id": 55}]), \
                _patched(self.observers, "read_places", lambda info, people: []), \
                _patched(self.observers, "read_events", lambda: []), \
                _patched(self.observers, "her_sim_info", lambda: _Her()):
            self.base.probe._reach_tick({"event_kind": "presence_snapshot"})
            self.base.probe._reach_tick({"event_kind": "presence_snapshot"})
        self.assertEqual(rows, ["discovery"])
        kinds = [row["kind"] for row in self.base.e2("lists")]
        self.assertEqual(kinds, ["people", "places", "events"])
        self.assertEqual([row["list_rev"] for row in self.base.e2("lists")], [1, 1, 1])

    def test_a_pending_lists_now_is_read_at_the_next_tick(self):
        with _patched(self.base.probe, "_LISTS", reach.ListWriter(lambda kind, row: True, clock=_Clock(0.0))), \
                _patched(self.base.probe, "_LISTS_ZONE", object()), \
                _patched(self.base.probe, "_DISCOVERY_ZONE", object()), \
                _patched(self.base.probe, "_write_discovery", lambda: None), \
                _patched(self.base.probe._E2, "_zone_running", lambda: True), \
                _patched(self.observers, "read_people", lambda info: []), \
                _patched(self.observers, "read_places", lambda info, people: []), \
                _patched(self.observers, "read_events", lambda: None), \
                _patched(self.observers, "her_sim_info", lambda: _Her()):
            self.base.probe.request_lists_now()
            self.base.probe._reach_tick({"event_kind": "presence_snapshot"})
            self.assertFalse(self.base.probe._LISTS_FORCE)


class _Shape(SimPickerInteraction):
    """A phone Sim picker, as the discovery reads it (its tuned minimum, radius and include flags)."""
    __name__ = "CallPickFriendSuperInteraction"
    guid64 = int(GUID)
    allow_user_directed = True
    min_selectable = 1
    radius = 4.0
    include_actor_sim = True


class PhoneDiscoveryTests(unittest.TestCase):
    def test_a_phone_picker_and_each_phone_test_are_read(self):
        base = test_e2.ControlFlowTests()
        base.setUp()
        actuator = base.probe.e2_actuator
        base.sim.test_super_affordance = lambda affordance, target, context: False
        pickers, tests = actuator.phone_discovery(base.sim, [_Shape], [])
        self.assertEqual(pickers[0]["guid64"], GUID)
        self.assertEqual(pickers[0]["min_required"], 1)
        self.assertEqual(pickers[0]["flags"], ["include_actor_sim"])
        self.assertEqual(tests[0]["guid64"], GUID)
        self.assertEqual(tests[0]["reason"], "False")
        self.assertIsNone(tests[0]["tooltip_key"])


if __name__ == "__main__":
    unittest.main()
