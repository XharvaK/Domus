"""W13 R2 (probe 2.40.0, Brief R): the reach fixes of the second audit (REACH2-1..11, SEAM2-12, the guest cap's detail),
then the cage rulings that touch reach (Q-5, Q-a, Q-g, Q-d). Each rule has its own test.

Fakes only. The game's objects are replaced by invented ones; the event money is a fake household fund that the fake
game manager charges the way the game does (cost plus hire, all or nothing)."""
import types
import unittest

import test_e2
from test_2160_act import ACT
import test_w13_p1
from test_w13_p1 import _patched, _Plain

from ashley_e1 import reach  # noqa: E402
from ashley_e1 import schema  # noqa: E402

BODY_ID = 118245043779534861


class _Funds(object):
    """A household's funds (invented): try_remove takes all of an amount or nothing; add records count_as_earnings."""

    def __init__(self, amount):
        self.amount = amount
        self.adds = []

    def try_remove(self, amount, reason, sim, require_full_amount=False):
        if self.amount < amount:
            return False
        self.amount -= amount
        return True

    def add(self, amount, reason, sim, tags=None, count_as_earnings=True):
        self.amount += amount
        self.adds.append((amount, count_as_earnings))


class _GuestList(object):
    """A guest list (invented): its hire cost is read by get_hire_cost, which may be unreadable."""

    def __init__(self, hire=40, unreadable=False):
        self.hire = hire
        self.unreadable = unreadable

    def get_hire_cost(self):
        if self.unreadable:
            raise RuntimeError("no hire cost")
        return self.hire


def _game_manager(funds, charge, made):
    """The zone's situation manager (invented, game-shaped): it takes `charge` from the funds, as the game does before it
    makes the event, and returns the new situation's id, or None when it made none (after the charge)."""
    def create_situation(situation, guest_list, user_facing=True, zone_id=None, scheduled_time=None):
        funds.try_remove(charge, "game", None, require_full_amount=True)
        return 909 if made else None
    return types.SimpleNamespace(create_situation=create_situation)


class R2Tests(unittest.TestCase):
    """The act, the verbs and the event through the probe's inbox, with the fakes of test_w13_p1."""
    ready = test_w13_p1.ReachActTests.ready
    send = test_w13_p1.ReachActTests.send
    act = test_w13_p1.ReachActTests.act
    act_events = test_w13_p1.ReachActTests.act_events

    def setUp(self):
        test_w13_p1.ReachActTests.setUp(self)
        self.funds = _Funds(1000)
        households = types.SimpleNamespace(funds=self.funds)
        sim = self.base.sim
        body = types.SimpleNamespace(id=BODY_ID, is_selectable=True, household=households,
                                     get_sim_instance=lambda allow_hidden_flags=None: sim)
        self.base.services.sim_info_manager = lambda: types.SimpleNamespace(get_all=lambda: [body])
        self.saved_events = set(getattr(self.probe, "_KNOWN_EVENTS", ()))

    def tearDown(self):
        if hasattr(self.probe, "_KNOWN_EVENTS"):
            self.probe._KNOWN_EVENTS.clear()
            self.probe._KNOWN_EVENTS.update(self.saved_events)
        self.probe._E2._go = None
        test_w13_p1.ReachActTests.tearDown(self)

    def event_send(self, situation_id="9", guests=(), start="now"):
        return self.send("event", {"act_id": ACT, "situation_id": situation_id, "guests": list(guests), "start": start})

    def event_patches(self, manager=None, hire=40, cost=250, money_read=True, refund=None, guests=None, situation=None):
        """The event's game calls, patched: the situation and its cost, the guest list with its hire cost, the zone's
        manager, the funds read, and a refund that records what it gave back."""
        e2 = self.probe.e2_actuator
        def give_back(household, amount, sim, reason):
            self.funds.add(amount, reason, sim, count_as_earnings=False)
            return True

        return [
            _patched(e2, "situation_type", lambda guid: situation if situation is not None else object()),
            _patched(e2, "now_absolute_minutes", lambda: 1000),
            _patched(e2, "situation_cost", lambda s: cost),
            _patched(e2, "default_job", lambda s: "job"),
            _patched(e2, "event_guest_list", lambda host, guest_ids, job: guests or _GuestList(hire)),
            _patched(e2, "refund", refund or give_back),
            _patched(self.base.services, "current_zone_id", lambda: 1),
            _patched(self.base.services, "get_zone_situation_manager",
                     lambda zone: manager if manager is not None else _game_manager(self.funds, 0, True)),
            _patched(self.probe.observers, "household_money",
                     lambda info: self.funds.amount if money_read else None),
        ]

    def run_with(self, patches, sending):
        """Enters the patches, runs the sending callable, and leaves them."""
        for patch in patches:
            patch.__enter__()
        try:
            return sending()
        finally:
            for patch in reversed(patches):
                patch.__exit__(None, None, None)

    # ----------------------------------------------------------- REACH2-1 / T5: the event's money
    def test_the_game_takes_the_event_price_once_and_the_probe_takes_nothing_itself(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 290, True))
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertTrue(ok)
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("FINISHED", "CREATED"))
        self.assertEqual(last["result"], {"cost": 290, "funds": 710, "start_min": 1000})
        self.assertEqual(self.funds.amount, 710)
        self.assertEqual(self.funds.adds, [])

    def test_an_event_the_game_takes_for_but_does_not_make_gives_the_money_back_unearned(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 290, False))
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "refunded 290"))
        self.assertEqual(self.funds.amount, 1000)
        self.assertEqual(self.funds.adds, [(290, False)])

    def test_an_event_not_made_and_nothing_taken_is_refused_as_create(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, False))
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "create"))
        self.assertEqual(self.funds.adds, [])

    def test_a_refund_that_fails_after_a_charge_with_no_event_is_said_on_the_refusal(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 290, False),
                                     refund=lambda household, amount, sim, reason: False)
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "refund failed"))

    def test_the_price_is_cost_plus_hire_and_is_checked_before_anything_is_accepted(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        self.funds.amount = 280
        made = []
        patches = self.event_patches(manager=types.SimpleNamespace(
            create_situation=lambda *args, **kwargs: made.append(args) or 909), hire=40, cost=250)
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NO_FUNDS")
        self.assertEqual(self.act_events("ACCEPTED"), [])
        self.assertEqual(made, [])
        self.assertEqual(self.funds.amount, 280)

    def test_an_unread_hire_cost_is_refused_as_cost_unread_before_accepting(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(guests=_GuestList(unreadable=True))
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "cost unread"))
        self.assertEqual(self.act_events("ACCEPTED"), [])

    def test_hire_cost_reads_the_guest_list_or_is_none(self):
        e2 = self.probe.e2_actuator
        self.assertEqual(e2.hire_cost(_GuestList(40)), 40)
        self.assertIsNone(e2.hire_cost(_GuestList(unreadable=True)))
        self.assertIsNone(e2.hire_cost(object()))

    def test_money_that_cannot_be_read_is_refused_as_funds_unread(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(money_read=False)
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "funds unread"))
        self.assertEqual(self.act_events("ACCEPTED"), [])

    def test_a_free_event_the_game_makes_reports_no_cost(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True), hire=0, cost=0)
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertTrue(ok)
        self.assertEqual(self.act_events()[-1]["result"]["cost"], 0)

    # ----------------------------------------------------------- REACH2-4: an event while a trip is pending
    def test_an_event_while_a_trip_is_pending_is_refused_as_travel_pending(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        self.probe._E2._go = {"act_id": "earlier", "zone_id": "66", "at": 0.0}
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True))
        ok, _connection = self.run_with(patches, self.event_send)
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "TRAVEL_PENDING")
        self.assertEqual(self.act_events("ACCEPTED"), [])
        self.assertEqual(self.probe._E2._go["act_id"], "earlier")

    # ----------------------------------------------------------- REACH2-5: a verb stops when its row fell back
    def test_a_trip_stops_when_its_accepted_row_is_refused(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        travelled = []
        real = self.probe._E2._event

        def refuse_accepted(kind, payload):
            return payload.get("phase") != "ACCEPTED" and real(kind, payload)

        with _patched(self.probe._E2, "_event", refuse_accepted), \
                _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: travelled.append(zone_id) or True):
            ok, _connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.assertFalse(ok)
        self.assertEqual(travelled, [])
        self.assertIsNone(self.probe._E2._go)
        self.assertEqual(self.act_events()[-1]["phase"], "UNKNOWN")

    def test_a_trip_that_cannot_write_its_pushed_row_is_not_tracked(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        real = self.probe._E2._event

        def refuse_pushed(kind, payload):
            return payload.get("phase") != "PUSHED" and real(kind, payload)

        with _patched(self.probe._E2, "_event", refuse_pushed), \
                _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: True), \
                _patched(self.base.services, "current_zone_id", lambda: 1):
            ok, _connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        with _patched(self.base.services, "current_zone_id", lambda: 55):
            self.probe._E2.tick_verbs()
        self.assertFalse(ok)
        self.assertIsNone(self.probe._E2._go)
        self.assertEqual(self.act_events()[-1]["phase"], "UNKNOWN")

    def test_a_refused_act_row_returns_false_after_its_fallback(self):
        self.ready()
        real = self.probe._E2._event

        def refuse_finished(kind, payload):
            return payload.get("phase") != "FINISHED" and real(kind, payload)

        with _patched(self.probe._E2, "_event", refuse_finished):
            ok = self.probe._E2._act_event_safe(ACT, "FINISHED", code="CREATED", object_id=None, guid64=None,
                                                result={"cost": 1})
        self.assertFalse(ok)
        self.assertEqual(self.act_events()[-1]["phase"], "UNKNOWN")

    # ----------------------------------------------------------- REACH2-3: a pending trip closes without sampling
    def test_the_inbox_tick_closes_a_trip_that_never_arrives(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        with _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: True), \
                _patched(self.base.services, "current_zone_id", lambda: 1):
            self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.probe._E2._go["at"] -= 301.0
        with _patched(self.probe, "_INBOX_HANDLE", object()), \
                _patched(self.probe, "_inbox_tick_body", lambda: None), \
                _patched(self.probe, "_supervise_sampling", lambda: None), \
                _patched(self.base.services, "current_zone_id", lambda: 1):
            self.probe._inbox_tick()
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "TRAVEL_UNSEEN"))
        self.assertIsNone(self.probe._E2._go)

    def test_arming_closes_a_pending_trip_and_clears_it(self):
        self.ready()
        self.probe._E2._go = {"act_id": ACT, "zone_id": "55", "at": 0.0}
        with _patched(self.base.services, "current_zone_id", lambda: 1):
            self.probe._E2.on_arm()
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "TRAVEL_UNSEEN"))
        self.assertIsNone(self.probe._E2._go)

    # ----------------------------------------------------------- SEAM2-12: a go that raises after its PUSHED row
    def test_a_go_that_raises_after_its_pushed_row_writes_no_arrival(self):
        self.ready()
        self.probe._KNOWN_ZONES.add("55")
        replies = []

        def say(connection, text):
            replies.append(text)
            if text.startswith("ACT_PUSHED"):
                raise RuntimeError("reply lost")

        with _patched(self.probe._E2, "_say", say), \
                _patched(self.probe.e2_actuator, "travel", lambda sim_id, zone_id: True):
            ok, _connection = self.send("go", {"act_id": ACT, "zone_id": "55"})
        self.assertFalse(ok)
        self.assertIsNone(self.probe._E2._go)
        with _patched(self.base.services, "current_zone_id", lambda: 55):
            self.probe._E2.tick_verbs()
        self.assertEqual([row["phase"] for row in self.act_events()], ["ACCEPTED", "PUSHED", "UNKNOWN"])
        self.assertEqual(self.act_events()[-1]["code"], "E2_EXCEPTION:RuntimeError")

    # ----------------------------------------------------------- REACH2-6 / SEAM2-13: a Sim named with a pie variant
    def test_a_sim_named_with_a_pie_variant_is_refused_not_dropped(self):
        self.ready()
        ok, _connection = self.act(variant=0, sim_id="123")
        self.assertFalse(ok)
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "NOT_A_SIM_ACT")
        self.assertEqual(self.pushed, [])

    # ----------------------------------------------------------- T4: the guest cap's detail
    def test_too_many_guests_is_refused_with_the_cap_in_the_detail(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True))
        connection = self.probe._InboxReply("helper")

        def sending():
            return self.probe._E2.cmd_event(ACT, "9", ["1"] * 65, "now", connection, known_events=("9",))

        ok = self.run_with(patches, sending)
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "too many guests (at most 64)"))
        self.assertEqual(self.act_events("ACCEPTED"), [])

    # ----------------------------------------------------------- REACH2-10: ASCII digits only
    def test_an_id_with_non_ascii_digits_is_not_an_id(self):
        self.assertIsNone(reach._id("٢"))
        self.assertFalse(schema._is_digits("٢"))
        self.assertEqual(reach._id("12"), "12")
        self.assertTrue(schema._is_digits("12"))

    # ----------------------------------------------------------- REACH2-8: the list validators' names
    def test_the_place_list_validator_has_its_own_name(self):
        self.assertIs(schema.LIST_ITEM_VALIDATORS["places"], schema._validate_place_item)
        schema._validate_place_item({"zone_id": "55", "kind": "home", "lot_name": None, "venue": None,
                                     "household_id": None})
        with self.assertRaises(schema.SchemaError):
            schema._validate_place_item({"zone_id": "x", "kind": "home", "lot_name": None, "venue": None,
                                         "household_id": None})


class _Small(object):
    """An event type that takes few guests (invented): its tuned max_participants is 3, its cost is 0."""
    max_participants = 3
    cost = 0
    guid64 = 9100


class R2LimitTests(unittest.TestCase):
    """2.40.0 (W13 R2, Q-d): the event's limits. A start up to 99 days ahead; the wire takes up to 64 guests; the probe
    refuses more guests than the event type's max_participants allows, and the wire bound when it is unreadable."""

    def test_a_start_may_be_up_to_99_days_ahead(self):
        self.assertEqual(reach.start_minute(99, 9, 0, 600, 3), (3 + 99) * 1440 + 540)
        self.assertIsNone(reach.start_minute(100, 9, 0, 600, 3))
        self.assertIsNone(reach.start_minute(-1, 9, 0, 600, 3))

    def test_the_wire_takes_a_start_up_to_99_days_and_up_to_64_guests(self):
        start = {"day_offset": 99, "hour": 9, "minute": 30}
        args = {"act_id": ACT, "situation_id": "9", "guests": [], "start": start}
        self.assertIsNone(test_w13_p1._parse("event", args)[1])
        self.assertEqual(test_w13_p1._parse("event", dict(args, start=dict(start, day_offset=100)))[1], "BAD_ARGS")
        self.assertIsNone(test_w13_p1._parse("event", dict(args, guests=["1"] * 64, start="now"))[1])
        self.assertEqual(test_w13_p1._parse("event", dict(args, guests=["1"] * 65, start="now"))[1], "BAD_ARGS")

    def test_the_event_type_s_max_participants_is_read_or_none(self):
        self.assertEqual(test_w13_p1.ActorActuatorTests._actuator(self).guest_cap(_Small), 3)
        self.assertIsNone(test_w13_p1.ActorActuatorTests._actuator(self).guest_cap(object()))


class R2CapTests(unittest.TestCase):
    """The guest cap of an event through the inbox, with the event fakes of R2Tests (its helpers, shared)."""
    setUp = R2Tests.setUp
    tearDown = R2Tests.tearDown
    ready = R2Tests.ready
    send = R2Tests.send
    event_send = R2Tests.event_send
    event_patches = R2Tests.event_patches
    run_with = R2Tests.run_with
    act_events = R2Tests.act_events

    def test_a_guest_list_longer_than_the_event_type_takes_is_refused_with_its_cap(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True), situation=_Small, cost=0, hire=0)
        ok, _connection = self.run_with(patches, lambda: self.event_send(guests=["1", "2", "3", "4"]))
        self.assertFalse(ok)
        refusal = self.act_events("REJECTED")[-1]
        self.assertEqual((refusal["code"], refusal["detail"]), ("CREATE_FAILED", "too many guests (at most 3)"))
        self.assertEqual(self.act_events("ACCEPTED"), [])

    def test_a_guest_list_at_the_event_type_s_cap_is_accepted(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True), situation=_Small, cost=0, hire=0)
        ok, _connection = self.run_with(patches, lambda: self.event_send(guests=["1", "2", "3"]))
        self.assertTrue(ok)
        self.assertEqual(self.act_events()[-1]["code"], "CREATED")

    def test_an_unreadable_cap_leaves_only_the_wire_bound_of_64(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        patches = self.event_patches(manager=_game_manager(self.funds, 0, True), cost=0, hire=0)
        ok, _connection = self.run_with(patches, lambda: self.event_send(guests=[str(n) for n in range(2, 19)]))
        self.assertTrue(ok)
        self.assertEqual(self.act_events()[-1]["code"], "CREATED")
