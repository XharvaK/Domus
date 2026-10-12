"""W13 fixes, reach half (probe 2.40.0, the P-R brief): the game's own shapes for the cost and display name of an event
type, the event id the game returns, the phone notice and call rows, the picker decided by the game's test, the refund
checked, a trip while another is pending, the rabbit hole, the waiting role, the people's tracks and the household name,
the lists' revisions and parts, the schema's item shapes, the events the probe may create, and the act row fallback.

Fakes only. The game's objects are replaced by invented ones shaped like the game's (a classmethod cost over _cost, a
property display_name over _display_name, an op whose .op holds sim_id and interaction_ids)."""
import types
import unittest

import test_e2
from test_2160_act import ACT
import test_w13_p1
from test_w13_p1 import _patched, _Her, _Clock, ActorSims

from ashley_e1 import reach  # noqa: E402
from ashley_e1 import schema  # noqa: E402
from ashley_e1 import tuned  # noqa: E402


class _Situation(object):
    """An event type as the game shapes it (invented): cost is a classmethod over the tuned _cost; display_name is a
    property over the tuned _display_name, a string factory."""
    _cost = 250
    _display_name = types.SimpleNamespace(_string_id=4444)
    creation_ui_option = 1
    guid64 = 9001

    @classmethod
    def cost(cls):
        return cls._cost

    @property
    def display_name(self):
        return self._display_name


class _Unpriced(object):
    """An event type with no readable cost (invented)."""
    creation_ui_option = 1
    guid64 = 9003


class FixActTests(unittest.TestCase):
    """The verbs and the phone through the probe's inbox, with the act fixtures of test_w13_p1."""
    ready = test_w13_p1.ReachActTests.ready
    send = test_w13_p1.ReachActTests.send
    act = test_w13_p1.ReachActTests.act
    act_events = test_w13_p1.ReachActTests.act_events

    def setUp(self):
        test_w13_p1.ReachActTests.setUp(self)
        self.saved_events = set(getattr(self.probe, "_KNOWN_EVENTS", ()))

    def tearDown(self):
        if hasattr(self.probe, "_KNOWN_EVENTS"):
            self.probe._KNOWN_EVENTS.clear()
            self.probe._KNOWN_EVENTS.update(self.saved_events)
        test_w13_p1.ReachActTests.tearDown(self)

    def sending_event(self, situation_id="9"):
        return self.send("event", {"act_id": ACT, "situation_id": situation_id, "guests": [], "start": "now"})

    def test_an_event_cost_is_read_from_the_game_classmethod_over_its_tuned_value(self):
        self.assertEqual(tuned._class_plain(_Situation, "cost"), 250)
        self.assertIs(tuned._class_plain(_Situation, "display_name"), _Situation._display_name)
        self.assertEqual(self.probe.e2_actuator.situation_cost(_Situation), 250)

    def test_an_unread_cost_is_refused_before_any_charge(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9003")
        charges = []
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: _Unpriced), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000), \
                _patched(self.probe.e2_actuator, "charge", lambda *args: charges.append(args) or True), \
                _patched(self.probe.observers, "household_money", lambda info: 1000):
            ok, _connection = self.sending_event("9003")
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "cost unread"))
        self.assertEqual(charges, [])

    def test_a_created_event_whose_id_is_an_int_is_finished_and_not_refunded(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        refunds = []
        manager = types.SimpleNamespace(create_situation=lambda *args, **kwargs: 909)
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: _Situation), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000), \
                _patched(self.probe.e2_actuator, "default_job", lambda s: "job"), \
                _patched(self.probe.e2_actuator, "event_guest_list", lambda *args: "list"), \
                _patched(self.probe.e2_actuator, "charge", lambda *args: True), \
                _patched(self.probe.e2_actuator, "refund", lambda *args: refunds.append(args) or True), \
                _patched(self.base.services, "current_zone_id", lambda: 1), \
                _patched(self.base.services, "get_zone_situation_manager", lambda zone: manager), \
                _patched(self.probe.observers, "household_money", lambda info: 1000):
            ok, _connection = self.sending_event()
        self.assertTrue(ok)
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("FINISHED", "CREATED"))
        self.assertEqual(refunds, [])

    def test_a_notice_is_written_for_her_phone_only(self):
        self.ready()
        her = types.SimpleNamespace(id=1)
        for_user = types.SimpleNamespace(op=types.SimpleNamespace(sim_id=999, interaction_ids=[4250]))
        for_her = types.SimpleNamespace(op=types.SimpleNamespace(sim_id=1, interaction_ids=[4250, 77]))
        with _patched(self.probe.observers, "her_sim_info", lambda: her):
            self.probe._E2.note_phone(for_user)
            self.assertEqual(self.base.e2("phone"), [])
            self.probe._E2.note_phone(for_her)
        self.assertEqual(self.base.e2("phone")[-1], {"kind": "notice", "from_sim_id": None, "notifies": "4250"})

    def test_a_notice_with_no_interaction_ids_names_no_act(self):
        self.ready()
        her = types.SimpleNamespace(id=1)
        op = types.SimpleNamespace(op=types.SimpleNamespace(sim_id=1, interaction_ids=[]))
        with _patched(self.probe.observers, "her_sim_info", lambda: her):
            self.probe._E2.note_phone(op)
        self.assertEqual(self.base.e2("phone")[-1], {"kind": "notice", "from_sim_id": None, "notifies": None})

    def test_a_held_call_is_written_as_a_call_from_its_caller(self):
        self.ready()
        caller = types.SimpleNamespace(target_sim_id=77)
        self.probe._E2._note_call(caller)
        self.assertEqual(self.base.e2("phone")[-1], {"kind": "call", "from_sim_id": "77", "notifies": None})

    def test_a_phone_row_kind_is_notice_or_call(self):
        schema._validate_reach("phone", {"kind": "notice", "from_sim_id": None, "notifies": "4250"})
        schema._validate_reach("phone", {"kind": "call", "from_sim_id": "77", "notifies": None})
        with self.assertRaises(schema.SchemaError):
            schema._validate_reach("phone", {"kind": "text", "from_sim_id": None, "notifies": None})

    def test_a_picker_is_decided_by_the_games_own_test_not_a_host_step(self):
        self.ready()
        info = ActorSims(123)

        def refused_by_game(affordance, target, context, **kwargs):
            return False

        def must_not_be_read(her, sims):
            raise AssertionError("the host step read is discovery only")

        with _patched(self.probe.e2_actuator, "sim_info_for", lambda sim_id: info), \
                _patched(self.probe.observers, "read_picker_steps", must_not_be_read), \
                _patched(self.probe.e2_actuator, "preflight_test",
                         lambda sim, obj, affordance, context, parameters=None: (False, "Not now", "9876")):
            ok, connection = self.act(sim_id="123")
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("SIM_NOT_CHOOSABLE", "9876"))
        self.assertEqual(connection.lines[-1], "ACT_REJECT SIM_NOT_CHOOSABLE")

    def test_a_picker_the_game_allows_is_pushed_even_when_the_discovery_step_would_say_hidden(self):
        self.ready()
        info = ActorSims(123)
        with _patched(self.probe.e2_actuator, "sim_info_for", lambda sim_id: info), \
                _patched(self.probe.observers, "read_picker_steps", lambda her, sims: {"123": "hidden"}), \
                _patched(self.probe.observers, "her_sim_info", lambda: None):
            ok, _connection = self.act(sim_id="123")
        self.assertTrue(ok)
        self.assertEqual(self.act_events()[-1]["phase"], "PUSHED")

    def test_a_refund_that_fails_is_said_on_the_refusal(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        with _patched(self.probe.e2_actuator, "situation_type", lambda guid: _Situation), \
                _patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000), \
                _patched(self.probe.e2_actuator, "default_job", lambda s: "job"), \
                _patched(self.probe.e2_actuator, "event_guest_list", lambda *args: "list"), \
                _patched(self.probe.e2_actuator, "charge", lambda *args: True), \
                _patched(self.probe.e2_actuator, "create_event", lambda *args: None), \
                _patched(self.probe.e2_actuator, "refund", lambda *args: False), \
                _patched(self.probe.observers, "household_money", lambda info: 1000):
            ok, _connection = self.sending_event()
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "refund failed"))

    def test_a_refund_is_not_counted_as_earnings(self):
        calls = []

        def add(amount, reason, sim, tags=None, count_as_earnings=True):
            calls.append((amount, reason, count_as_earnings))

        household = types.SimpleNamespace(funds=types.SimpleNamespace(add=add))
        self.assertTrue(self.probe.e2_actuator.refund(household, 300, None, "ashley_e2_event"))
        self.assertEqual(calls, [(300, "ashley_e2_event", False)])

        def failing(amount, reason, sim, tags=None, count_as_earnings=True):
            raise RuntimeError("funds gone")

        household = types.SimpleNamespace(funds=types.SimpleNamespace(add=failing))
        self.assertFalse(self.probe.e2_actuator.refund(household, 300, None, "ashley_e2_event"))

    def test_a_trip_while_another_is_pending_is_refused_and_the_pending_one_is_kept(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        pending = {"act_id": "earlier", "zone_id": "66", "at": 0.0}
        self.probe._E2._go = pending
        travelled = []
        try:
            with _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: travelled.append(zone_id) or True):
                ok, _connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
            self.assertFalse(ok)
            self.assertEqual(self.act_events("REJECTED")[-1]["code"], "TRAVEL_PENDING")
            self.assertEqual(travelled, [])
            self.assertIs(self.probe._E2._go, pending)
        finally:
            self.probe._E2._go = None

    def test_a_trip_from_a_rabbit_hole_is_refused_before_the_push(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        rabbit_holes = types.SimpleNamespace(get_head_rabbit_hole_id=lambda sim_id: 5)
        travelled = []
        with _patched(self.base.services, "get_rabbit_hole_service", lambda: rabbit_holes), \
                _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: travelled.append(zone_id) or True):
            ok, _connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "IN_RABBIT_HOLE")
        self.assertEqual(travelled, [])

    def test_a_pregnant_sim_is_not_refused_by_the_host(self):
        sim_info = types.SimpleNamespace(id=1, is_pregnant=True)
        with _patched(self.base.services, "current_zone_id", lambda: 1):
            self.assertIsNone(self.probe._E2._go_refusal(sim_info, "55", {"55"}))

    def test_a_pending_trip_that_raises_is_unknown_with_the_exception_name(self):
        self.ready()
        self.probe._E2._go = {"act_id": ACT, "zone_id": "55", "at": "not a time"}
        with _patched(self.base.services, "current_zone_id", lambda: 1):
            self.probe._E2.tick_verbs()
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "E2_EXCEPTION:TypeError"))
        self.assertIsNone(self.probe._E2._go)

    def test_a_sampler_stop_with_a_trip_pending_is_unknown(self):
        self.ready()
        self.probe._E2._go = {"act_id": ACT, "zone_id": "55", "at": 0.0}
        self.probe._E2.on_stop("STOP")
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "SAMPLER_STOPPED"))
        self.assertIsNone(self.probe._E2._go)

    def test_a_zone_change_keeps_the_pending_trip_for_the_next_sampling_tick(self):
        self.ready()
        pending = {"act_id": ACT, "zone_id": "55", "at": 0.0}
        self.probe._E2._go = pending
        self.probe._E2.on_stop("ZONE_CHANGE")
        self.assertIs(self.probe._E2._go, pending)
        self.probe._E2._go = None

    def test_an_event_id_the_newest_events_list_does_not_offer_is_refused_before_any_charge(self):
        self.ready()
        charges = []
        with _patched(self.probe.e2_actuator, "charge", lambda *args: charges.append(args) or True), \
                _patched(self.probe.observers, "household_money", lambda info: 1000):
            ok, _connection = self.sending_event("9")
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NOT_AN_EVENT")
        self.assertEqual(charges, [])

    def test_a_refused_act_row_falls_back_to_an_unknown_row_without_the_result(self):
        self.ready()
        writes = []
        real = self.probe._E2._event

        def refuse_the_finish(kind, payload):
            writes.append(payload)
            return payload.get("phase") != "FINISHED" and real(kind, payload)

        with _patched(self.probe._E2, "_event", refuse_the_finish):
            ok = self.probe._E2._act_event_safe(ACT, "FINISHED", code="CREATED", object_id=None, guid64=None,
                                                result={"cost": 1})
        self.assertTrue(ok)
        self.assertEqual(writes[-1]["phase"], "UNKNOWN")
        self.assertEqual(writes[-1]["code"], "ROW_INVALID")
        self.assertNotIn("result", writes[-1])
        self.assertEqual(self.act_events()[-1]["phase"], "UNKNOWN")

    def test_a_refused_row_with_no_fallback_still_returns_false(self):
        self.ready()
        with _patched(self.probe._E2, "_event", lambda kind, payload: False):
            self.assertFalse(self.probe._E2._act_event_safe(ACT, "FINISHED", code="CREATED", object_id=None,
                                                            guid64=None))

    def test_a_reach_failure_is_counted_and_guarded_once(self):
        self.ready()
        self.probe._REACH_FAILURES = 0
        self.probe._reach_failed(RuntimeError("x"))
        self.probe._reach_failed(RuntimeError("y"))
        self.assertEqual(self.probe._REACH_FAILURES, 2)
        reasons = [row["reason"] for row in self.base.rows("guard_exhausted")
                   if row.get("reason", "").startswith("E2_REACH_FAILURE")]
        self.assertEqual(reasons, ["E2_REACH_FAILURE:RuntimeError"])
        self.probe._REACH_FAILURES = 0

    def test_a_failed_discovery_write_does_not_mark_the_zone_done(self):
        self.ready()
        zone = object()
        with _patched(self.probe, "_DISCOVERY_ZONE", None), \
                _patched(self.probe, "_LISTS_ZONE", zone), \
                _patched(self.probe, "_current_zone", lambda: zone), \
                _patched(self.probe, "_DISCOVERY_TRIED", None), \
                _patched(self.probe, "_write_discovery", lambda: False), \
                _patched(self.probe._E2, "_zone_running", lambda: True), \
                _patched(self.probe, "_lists_readers", lambda: {}):
            self.probe._reach_tick({"event_kind": "presence_snapshot"})
            self.assertIsNot(self.probe._DISCOVERY_ZONE, zone)


class FixObserverTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers

    def test_a_visitor_who_waits_is_a_waiting_role_and_a_waiter_is_not(self):
        self.assertTrue(self.observers.waiting_role("RoleState_WaitingToBeGreeted"))
        self.assertTrue(self.observers.waiting_role("role_waiting"))
        self.assertFalse(self.observers.waiting_role("RoleState_Waiter"))
        self.assertFalse(self.observers.waiting_role("RoleState_Host"))

    def test_an_event_type_reads_its_name_and_cost_from_the_game_shapes(self):
        manager = types.SimpleNamespace(types={1: _Situation})
        with _patched(self.base.services, "get_instance_manager", lambda kind: manager), \
                _patched(self.observers, "ResourceTypes", types.SimpleNamespace(SITUATION=1)):
            events = self.observers.read_events()
        self.assertEqual(events, [{"situation_id": 9001, "name_key": "4444", "cost": 250, "schedulable": None}])

    def test_people_carry_the_visible_tracks_with_their_values(self):
        class Track_Example_Friendship(object):
            is_visible = True

            def get_value(self):
                return 30

        class Track_Example_Hidden(object):
            is_visible = False

            def get_value(self):
                return 5

        class _Tracks(object):
            def get_target_sim_infos(self):
                return [_Shape_Target()]

            def get_all_bits(self, target_id):
                return []

            def relationship_tracks_gen(self, target_sim_id, track_type=None):
                for track in (Track_Example_Hidden(), Track_Example_Friendship()):
                    yield track

        class _Shape_Target(object):
            id = 55
            first_name = "Ana"
            last_name = "Example"
            household_id = None

            def get_sim_instance(self):
                return None

        her = types.SimpleNamespace(relationship_tracker=_Tracks())
        people = self.observers.read_people(her, waiting=set())
        self.assertEqual(people[0]["tracks"], {"Track_Example_Friendship": 30})

    def test_a_tracks_read_that_fails_is_empty(self):
        class _Broken(object):
            def relationship_tracks_gen(self, target_sim_id, track_type=None):
                raise RuntimeError("no tracks")

        self.assertEqual(self.observers._visible_tracks(_Broken(), 55), {})

    def test_a_home_is_named_by_its_household(self):
        household = types.SimpleNamespace(name="Example Household", home_zone_id=77)
        with _patched(self.base.services, "household_manager", lambda: types.SimpleNamespace(get=lambda hid: household)):
            places = self.observers.read_places(_Her(), [])
            name = self.observers.household_name(9)
        self.assertEqual(name, "Example Household")
        self.assertEqual(places[0]["lot_name"], "Example Household")
        self.assertIsNone(places[0]["venue"])

    def test_discovery_says_what_is_not_read_yet(self):
        with _patched(self.base.services, "get_persistence_service", lambda: None), \
                _patched(self.observers, "read_events", lambda: None):
            record = self.observers.read_discovery(None, None, None)
        self.assertIn("venues", record["unread"])


class FixListTests(unittest.TestCase):
    def test_a_failed_second_part_is_retried_under_the_next_revision(self):
        entries = [{"sim_id": str(1000 + index)} for index in range(129)]
        results = [True, False]
        rows = []

        def emit(kind, row):
            rows.append(row)
            return results.pop(0) if results else True

        writer = reach.ListWriter(emit, clock=_Clock(0.0))
        self.assertFalse(writer.send("people", entries))
        self.assertTrue(writer.send("people", entries))
        self.assertEqual(sorted(set(row["list_rev"] for row in rows[2:])), [2])
        self.assertEqual(len(rows[2:]), 2)

    def test_a_reader_that_raises_does_not_stop_the_other_lists(self):
        written = []

        def raises():
            raise RuntimeError("unreadable")

        writer = reach.ListWriter(lambda kind, row: written.append(kind) or True, clock=_Clock(0.0))
        kinds = writer.tick({"people": raises, "places": lambda: []}, force=True, now=0.0)
        self.assertEqual(kinds, ["places"])
        self.assertEqual(written, ["places"])

    def test_the_byte_size_of_a_part_is_measured_as_it_is_written(self):
        value = ["é" * 10]
        self.assertEqual(reach._bytes(value), len('["' + "\\u00e9" * 10 + '"]'))

    def test_the_known_places_are_kept_only_when_the_whole_list_is_written(self):
        patch = _patched
        base = test_e2.ControlFlowTests()
        base.setUp()
        probe = base.probe
        saved = set(probe._KNOWN_ZONES)
        try:
            probe._KNOWN_ZONES.clear()
            first = {"kind": "places", "part": 0, "parts": 2, "items": [{"zone_id": "55"}]}
            second = {"kind": "places", "part": 1, "parts": 2, "items": [{"zone_id": "66"}]}
            with patch(probe._E2, "_event", lambda kind, payload: True):
                probe._lists_emit("places", first)
            self.assertEqual(probe._KNOWN_ZONES, set())
            with patch(probe._E2, "_event", lambda kind, payload: False):
                probe._lists_emit("places", second)
            self.assertEqual(probe._KNOWN_ZONES, set())
            with patch(probe._E2, "_event", lambda kind, payload: True):
                probe._lists_emit("places", first)
                probe._lists_emit("places", second)
            self.assertEqual(probe._KNOWN_ZONES, {"55", "66"})
        finally:
            probe._KNOWN_ZONES.clear()
            probe._KNOWN_ZONES.update(saved)

    def test_the_known_events_are_the_newest_events_list(self):
        base = test_e2.ControlFlowTests()
        base.setUp()
        probe = base.probe
        patch = _patched
        saved = set(probe._KNOWN_EVENTS)
        try:
            probe._KNOWN_EVENTS.clear()
            with patch(probe._E2, "_event", lambda kind, payload: True):
                probe._lists_emit("events", {"kind": "events", "part": 0, "parts": 1,
                                             "items": [{"situation_id": "9001"}]})
            self.assertEqual(probe._KNOWN_EVENTS, {"9001"})
        finally:
            probe._KNOWN_EVENTS.clear()
            probe._KNOWN_EVENTS.update(saved)

    def test_a_guest_list_names_her_once(self):
        added = []

        class _List(object):
            def __init__(self, invite_only, host, requester):
                self.host = host

            def add_guest_info(self, info):
                added.append(info)

        base = test_e2.ControlFlowTests()
        base.setUp()
        actuator = base.probe.e2_actuator
        with _patched(actuator, "SituationGuestList", _List), \
                _patched(actuator, "SituationGuestInfo",
                         types.SimpleNamespace(construct_from_purpose=lambda sim, job, purpose: sim)), \
                _patched(actuator, "SituationInvitationPurpose", types.SimpleNamespace(INVITED="invited")):
            actuator.event_guest_list(1, ["1", "4"], "job")
        self.assertEqual(added, [1, 4])


class FixSchemaTests(unittest.TestCase):
    def lists_row(self, kind, items):
        return {"kind": kind, "list_rev": 1, "part": 0, "parts": 1, "digest": "a" * 64, "count": len(items),
                "items": items}

    def test_a_person_row_is_checked_for_its_shape(self):
        good = reach.person_item({"sim_id": 55, "first_name": "Ana", "labels": ["Bit_Example"], "tracks": {"T": 3},
                                  "household_id": 9, "has_home": True, "on_lot": False, "waiting": None})
        schema._validate_reach("lists", self.lists_row("people", [good]))
        for bad in ({"nonsense": 1}, dict(good, sim_id="abc"), dict(good, labels="x"), dict(good, tracks={"T": "x"}),
                    dict(good, has_home="yes")):
            with self.assertRaises(schema.SchemaError):
                schema._validate_reach("lists", self.lists_row("people", [bad]))

    def test_a_place_row_is_checked_for_its_kind_and_zone(self):
        good = reach.place_item({"zone_id": 77, "kind": "home", "lot_name": "Example Household"})
        schema._validate_reach("lists", self.lists_row("places", [good]))
        with self.assertRaises(schema.SchemaError):
            schema._validate_reach("lists", self.lists_row("places", [dict(good, kind="castle")]))
        with self.assertRaises(schema.SchemaError):
            schema._validate_reach("lists", self.lists_row("places", [dict(good, zone_id="x7")]))

    def test_an_event_row_is_checked_for_its_cost_and_flags(self):
        good = reach.event_item({"situation_id": 9001, "name_key": "4444", "cost": 250, "schedulable": None})
        schema._validate_reach("lists", self.lists_row("events", [good]))
        for bad in (dict(good, cost="free"), dict(good, schedulable="yes")):
            with self.assertRaises(schema.SchemaError):
                schema._validate_reach("lists", self.lists_row("events", [bad]))

    def test_a_discovery_section_is_a_dict_or_a_list(self):
        schema._validate_reach("discovery", {"discovery_rev": 1, "sections": {"pickers": [], "save": {}}})
        with self.assertRaises(schema.SchemaError):
            schema._validate_reach("discovery", {"discovery_rev": 1, "sections": {"pickers": "NOT A LIST"}})

    def test_the_discovery_unread_section_is_a_list_of_words(self):
        schema._validate_reach("discovery", {"discovery_rev": 1, "sections": {"unread": ["venues"]}})


class FixPhoneDiscoveryTests(unittest.TestCase):
    def test_a_phone_test_that_raises_gives_no_reason_and_keeps_the_record(self):
        base = test_e2.ControlFlowTests()
        base.setUp()
        actuator = base.probe.e2_actuator

        def raises(affordance, target, context, **kwargs):
            raise RuntimeError("the game's test failed")

        base.sim.test_super_affordance = raises
        pickers, tests = actuator.phone_discovery(base.sim, [test_w13_p1._Shape], [])
        self.assertEqual(len(pickers), 1)
        self.assertEqual(len(tests), 1)
        self.assertIsNone(tests[0]["reason"])
        self.assertIsNone(tests[0]["tooltip_key"])


if __name__ == "__main__":
    unittest.main()
