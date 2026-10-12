"""R3 repair wave (probe, sims-e1). Each class pins one item of the third audit:

- the menu's seams: a partial whole (R1), the zone of each part (R2), the death type of a BODY_GONE record (R3);
- the build: a zone or a room change restarts the build in progress (PROBE3-1, PROBE3-2); the near part is written at the
  first job that is not near, near objects of other rooms are tested first (PROBE3-3); a near part is written when empty
  (PROBE3-16); a different level is never near (PROBE3-11); a near part of another zone is never written (PROBE3-13);
- class words of live names (PROBE3-5); the event's exception and money reads (PROBE3-6, PROBE3-9); a late sale and a
  buy's read-back (PROBE3-7, PROBE3-8); the name exclusions (PROBE3-10, CONTRA3-2, CONTRA3-3); the guard rules (PROBE3-14).

Names are invented ("Test Chair", object ids 11 to 13); no game text is written here."""
import importlib.util
import os
import types
import unittest

from test_binding import load_probe
import test_2371_menu_speed as menu_tests
import test_2160_act as acts
import test_2400_home as home_tests
import test_w13_fix_reach
import test_w13_p1

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
SPEC = importlib.util.spec_from_file_location("e1_check_guards_r3", os.path.join(TOOLS, "check_guards.py"))
guards = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guards)


def _finished(menu, jobs, runner=lambda job: True, **extra):
    build = menu.MenuBuild(jobs, runner, budget_ms=1e9, max_per_chunk=10000, **extra)
    while not build.done:
        build.step()
    return build


def _job(object_id, same_room=False, distance=None, phone=None, other_level=False, room="4", on_lot=True):
    value = {"object_id": object_id, "definition_id": "7", "class": "object_thing", "distance_m": distance,
             "same_room": same_room, "room": room, "guid64": "77", "name": "act_77", "text_key": None,
             "person": False, "on_lot": on_lot, "other_level": other_level}
    if phone:
        value["phone"] = True
    return value


class MenuRulesTests(unittest.TestCase):
    """The pure menu rules: near, the order of the build, the hand-over of the near part, the zone field."""

    def setUp(self):
        load_probe()
        from ashley_e1 import act_menu
        self.menu = act_menu

    def test_a_different_level_is_never_near_even_at_one_metre_or_in_her_room(self):
        self.assertFalse(self.menu.is_near(_job("11", distance=1.0, other_level=True)))
        self.assertFalse(self.menu.is_near(_job("11", same_room=True, other_level=True)))
        self.assertTrue(self.menu.is_near(_job("11", distance=4.0)))
        self.assertFalse(self.menu.is_near(_job("11", distance=4.1)))
        self.assertTrue(self.menu.is_near(_job("11", phone=True, other_level=True)))

    def test_the_build_tests_near_objects_of_other_rooms_before_the_far_ones(self):
        """PROBE3-3: an object 3 m away in another room is in the near part (it is tested before the far one)."""
        items = [{"object_id": "21", "room": "5", "same_room": False, "on_lot": True, "distance_m": 9.0},
                 {"object_id": "22", "room": "5", "same_room": False, "on_lot": True, "distance_m": 3.0},
                 {"object_id": "23", "room": "4", "same_room": True, "on_lot": True, "distance_m": 1.0}]
        picked = [item["object_id"] for item, _acts in self.menu.pick(items, lambda item: ["act"])]
        self.assertEqual(picked, ["23", "22", "21"])

    def test_the_near_part_is_handed_over_only_after_every_near_job_is_tested(self):
        """PROBE3-3: the hand-over fires at the first job that is not near. A near job of another room behind a far one
        would be missed; in the order the build now uses, it is in the hand-over."""
        handed = []

        def on_near(build):
            handed.append([item["object_id"] for item in build.payload(1, "4", near=True)["objects"]])
        jobs = [_job("23", same_room=True, distance=1.0), _job("22", distance=3.0, room="5"),
                _job("21", distance=9.0, room="5")]
        _finished(self.menu, jobs, on_near=on_near)
        self.assertEqual(handed, [["23", "22"]])

    def test_an_empty_near_part_is_still_handed_over_when_nothing_is_near(self):
        """PROBE3-16: the hand-over fires when the first far job comes, even with no near object (the part is empty)."""
        handed = []
        _finished(self.menu, [_job("21", distance=9.0, room="5")],
                  on_near=lambda build: handed.append(build.payload(1, "4", near=True)["objects"]))
        self.assertEqual(handed, [[]])

    def test_zone_text_is_a_string_of_digits_or_none(self):
        self.assertEqual(self.menu.zone_text(123), "123")
        self.assertEqual(self.menu.zone_text(0), "0")
        for bad in (None, True, -1, "12", 1.5):
            with self.subTest(bad=bad):
                self.assertIsNone(self.menu.zone_text(bad))

    def test_every_menu_part_carries_its_zone_and_none_leaves_the_key_out(self):
        build = _finished(self.menu, [_job("11", same_room=True, distance=1.0)])
        whole = build.payload(1, "4", zone_id=4567)
        self.assertEqual(whole["zone_id"], "4567")
        near = build.payload(2, "4", near=True, zone_id=4567)
        self.assertEqual((near["zone_id"], near["near"]), ("4567", True))
        self.assertNotIn("zone_id", build.payload(1, "4"))
        self.assertTrue(all(part["zone_id"] == "4567" for part in self.menu.parts(whole)))


class MenuSchemaTests(unittest.TestCase):
    """R1, R2, R3 on the schema: a partial whole, a zone id, a death type."""

    def setUp(self):
        load_probe()
        from ashley_e1 import act_menu, schema
        self.menu, self.schema = act_menu, schema
        build = _finished(act_menu, [_job("11", same_room=True, distance=1.0)])
        self.payload = build.payload(1, "4", zone_id=123)

    def check(self, payload, kind="act_menu"):
        self.schema._validate_e2({"event_kind": kind, "telemetry_session_id": "1", "e2": payload})

    def test_a_partial_whole_is_valid_and_never_with_near(self):
        part = dict(self.menu.parts(self.payload)[0], partial=True)
        self.check(part)
        with self.assertRaises(self.schema.SchemaError):
            self.check(dict(part, near=True))
        with self.assertRaises(self.schema.SchemaError):
            self.check(dict(part, partial=False))

    def test_a_zone_id_is_a_string_of_digits_when_present(self):
        part = self.menu.parts(self.payload)[0]
        self.assertEqual(part["zone_id"], "123")
        self.check(part)
        for bad in ("12a", "", 123, True):
            with self.subTest(bad=bad):
                with self.assertRaises(self.schema.SchemaError):
                    self.check(dict(part, zone_id=bad))
        # A part with no zone (a row before R2) is still valid.
        without = dict(part)
        del without["zone_id"]
        self.check(without)

    def test_a_death_type_is_a_name_of_up_to_forty_characters_when_present(self):
        record = {"record": "BODY_GONE", "guid": None, "slot_id": None, "sim_id": None, "ticks": None,
                  "loaded_from_slot_id": None, "lineage_class": "BODY_GONE", "session_uuid": None, "reason": "DEAD"}
        self.check(record, kind="lineage_event")
        self.check(dict(record, death_type="TEST_DEATH"), kind="lineage_event")
        self.check(dict(record, death_type="x" * 40), kind="lineage_event")
        for bad in ("x" * 41, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(self.schema.SchemaError):
                    self.check(dict(record, death_type=bad), kind="lineage_event")


class ClassWordTests(unittest.TestCase):
    """PROBE3-5: live class names (underscores and digit runs end a word; the kind follows "object")."""

    def setUp(self):
        load_probe()
        from ashley_e1 import e2_trial, home, e2_actuator
        self.trial, self.home, self.actuator = e2_trial, home, e2_actuator

    def test_underscores_and_digit_runs_end_a_word(self):
        self.assertEqual(self.trial.class_words("object_toiletFC_01"), ["object", "toilet", "fc"])
        self.assertEqual(self.trial.class_words("object_stairsSpiral"), ["object", "stairs", "spiral"])

    def test_the_kind_is_the_word_after_object_or_the_last_word_of_another_name(self):
        kind = self.trial.kind_word
        self.assertEqual(kind("object_toiletFC_01"), "toilet")
        self.assertEqual(kind("object_door"), "door")
        self.assertEqual(kind("object_light_wall"), "light")
        self.assertEqual(kind("FrontDoor"), "door")
        self.assertEqual(kind(""), "")

    def test_build_items_by_their_kind_word(self):
        for name in ("object_door", "object_wall", "object_window", "object_fence_wood", "object_stairsSpiral",
                     "object_floorTile", "Door", "Terrain"):
            with self.subTest(name=name):
                self.assertTrue(self.home.is_build_class(name))
        for name in ("object_light_wall", "object_light_floor", "object_mirror_wall", "object_plant_non_gardening",
                     "object_fridgeHIGH_01", "WallLight", "IndoorPlant"):
            with self.subTest(name=name):
                self.assertFalse(self.home.is_build_class(name))

    def test_routes_by_their_kind_word(self):
        self.assertEqual(self.home.route_kind("object_toiletFC_01", False), "toilet")
        self.assertEqual(self.home.route_kind("object_bedSingleFC_01", False), "bed")
        self.assertEqual(self.home.route_kind("object_fridgeHIGH_01", False), "fridge")
        self.assertIsNone(self.home.route_kind("object_sinkCounterFC_01", False))
        self.assertIsNone(self.home.route_kind("object_door", False))
        self.assertEqual(self.home.route_kind("object_door", True), "door")

    def test_a_portal_by_its_kind_word(self):
        for name in ("object_door", "object_door_double", "object_gate", "FrontDoor"):
            with self.subTest(name=name):
                self.assertTrue(self.actuator.is_portal(type(name, (object,), {})()))
        self.assertFalse(self.actuator.is_portal(type("object_light_wall", (object,), {})()))
        self.assertFalse(self.actuator.is_portal(type("object_mirror_wall", (object,), {})()))


class ExclusionListTests(unittest.TestCase):
    """PROBE3-10 and CONTRA3-2, CONTRA3-3: the name exclusions are cheat, debug, test and tutorial acts, and travel."""

    def setUp(self):
        load_probe()
        from ashley_e1 import e2_trial, e2_actuator, probe
        self.trial, self.actuator, self.probe = e2_trial, e2_actuator, probe

    def test_the_deny_name_list_is_cheat_debug_test_tutorial_and_travel(self):
        self.assertEqual(self.trial.DENY_NAME_PARTS,
                         ("debug", "cheat", "testing", "tutorial", "travel", "goto", "go_to", "leave"))

    def test_the_social_list_is_the_same_kinds_with_vacation_as_a_trip(self):
        self.assertEqual(self.trial.SOCIAL_DENY_PARTS,
                         ("debug", "cheat", "cheats", "cheating", "testing", "tutorial", "travel", "traveling",
                          "travelling", "vacation"))

    def test_the_phone_lists_hold_testers_and_trips_only(self):
        self.assertEqual(self.actuator.PHONE_DENY_PARTS,
                         ("debug", "cheat", "cheats", "cheating", "testing", "tutorial"))
        self.assertEqual(self.actuator.PHONE_TRAVEL_PARTS, ("travel", "goto", "visitlot", "mappicker", "vacation"))

    def test_the_pie_flags_are_cheat_and_debug_only(self):
        self.assertEqual(self.actuator.PIE_HIDDEN_FLAGS, ("cheat", "debug"))
        automated = type("Test_Automated_Choice", (object,), {"automation": True, "cheat": False, "debug": False})
        self.assertFalse(self.probe._menu_hidden(automated))
        flagged = type("Test_Debug_Choice", (object,), {"automation": False, "cheat": False, "debug": True})
        self.assertTrue(self.probe._menu_hidden(flagged))

    def test_a_name_with_an_autonomous_or_npc_or_phone_word_is_not_denied(self):
        for name in ("Autonomous_Call", "Phone_NPC_Call", "PhoneCall", "GoHere"):
            with self.subTest(name=name):
                self.assertIsNone(self.trial.denied_name(name))
                self.assertIsNone(self.trial.denied_part(name, self.trial.SOCIAL_DENY_PARTS))
                self.assertIsNone(self.trial.denied_part(name, self.actuator.PHONE_DENY_PARTS))


class GuardRuleTests(unittest.TestCase):
    """PROBE3-14: the funds credit, the guest add and the cancel are guarded."""

    def test_a_funds_credit_is_e2_actuator_only(self):
        for source in ("def f(household):\n    funds_of(household).add(5, 'x')\n",
                       "def f(household):\n    household.funds.add(5, 'x')\n"):
            with self.subTest(source=source):
                self.assertTrue(guards.scan_text(source, "probe.py"))
                self.assertEqual(guards.scan_text(source, "e2_actuator.py"), [])
        self.assertEqual(guards.scan_text("def f(funds):\n    funds_add(funds, 5, None)\n", "probe.py"), [])

    def test_a_guest_is_added_by_the_actuator_only(self):
        source = "def f(guest_list, info):\n    guest_list.add_guest_info(info)\n"
        self.assertTrue(guards.scan_text(source, "home.py"))
        self.assertEqual(guards.scan_text(source, "e2_actuator.py"), [])

    def test_the_interaction_cancel_is_e2_control_only(self):
        source = "def cmd_cancel(interaction):\n    interaction.cancel_user('Test cancel')\n"
        self.assertEqual(guards.scan_text(source, "e2_control.py"), [])
        self.assertEqual(len(guards.scan_text(source, "probe.py")), 1)


class DeathTypeTests(unittest.TestCase):
    """R3: the game's death type name, read from sim_info.death_tracker.death_type, rides on the BODY_GONE record."""

    def setUp(self):
        load_probe()
        from ashley_e1 import observers
        self.observers = observers

    def test_the_death_type_name_is_read_and_left_out_when_unread_or_too_long(self):
        named = types.SimpleNamespace(death_tracker=types.SimpleNamespace(
            death_type=types.SimpleNamespace(name="TEST_DEATH")))
        self.assertEqual(self.observers.death_type_name(named), "TEST_DEATH")
        self.assertIsNone(self.observers.death_type_name(types.SimpleNamespace(death_tracker=None)))
        self.assertIsNone(self.observers.death_type_name(types.SimpleNamespace(
            death_tracker=types.SimpleNamespace(death_type=types.SimpleNamespace(name="x" * 41)))))

    def test_body_life_names_the_death_type_of_her_sim_info(self):
        info = types.SimpleNamespace(id=77, is_dead=True, death_tracker=types.SimpleNamespace(
            death_type=types.SimpleNamespace(name="TEST_DEATH")))
        services = types.SimpleNamespace(sim_info_manager=lambda: types.SimpleNamespace(get_all=lambda: [info]))
        original = self.observers.services
        self.observers.services = services
        self.addCleanup(setattr, self.observers, "services", original)
        life = self.observers.body_life(self.observers._info_id(info))
        self.assertEqual(life["death_type"], "TEST_DEATH")
        self.assertIs(life["dead"], True)


class ZoneAndRoomMenuTests(unittest.TestCase):
    """The probe's menu build in the harness of test_2371 (two objects: 11 two metres away, 12 thirty metres away)."""

    setUp = menu_tests.W10MenuTests.setUp
    tearDown = menu_tests.W10MenuTests.tearDown
    build_at = menu_tests.W10MenuTests.build_at
    menus = menu_tests.W10MenuTests.menus

    def start_build(self, zone=None):
        """A build that has not stepped yet (budget 0), as if a build were in progress."""
        jobs, _room = self.probe._menu_jobs(self.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=0.0, far=self.probe._MENU_FAR,
                                              reach=self.probe._menu_reach)
        self.probe._MENU, self.probe._MENU_ZONE = build, self.zone["current"] if zone is None else zone
        self.probe._MENU_STARTED_S, self.probe._MENU_ROOM = self.clock["s"], "4"
        return build

    def test_a_zone_change_drops_the_build_in_progress_and_the_new_zone_builds_at_once(self):
        """PROBE3-1: the old zone's build is not stepped or written; the new zone's build starts on this tick."""
        self.zone["current"] = 123
        old = self.start_build()
        last = {"menu_rev": 0, "objects": []}
        self.probe._MENU_LAST = last
        self.zone["current"] = 456
        self.probe._menu_tick(self.row)
        self.assertIsNot(self.probe._MENU, old)
        self.assertEqual(self.probe._MENU_ZONE, 456)
        self.assertIs(self.probe._MENU_LAST, last)  # the last menu is kept; only the build in progress is dropped

    def test_a_room_change_restarts_the_build_in_progress(self):
        """PROBE3-2: her new room gets a new build; the near part comes from the new order."""
        self.start_build()
        self.probe._menu_tick(self.row)  # her room is known from this tick on (the first move is the next one)
        old = self.probe._MENU
        self.probe._menu_tick(dict(self.row, zone=dict(self.row["zone"], room="5")))
        self.assertIsNot(self.probe._MENU, old)
        self.assertEqual(self.probe._MENU_ROOM, "5")

    def test_a_near_part_of_a_build_of_another_zone_is_never_written(self):
        """PROBE3-13: a build made in zone 123 writes no near part once she is in zone 456."""
        self.zone["current"] = 123
        build = _finished(self.probe.act_menu, self.probe._menu_jobs(self.row)[0], self.probe._menu_test)
        self.zone["current"] = 456
        before = len(self.base.e2("act_menu"))
        self.probe._menu_near_part(build, 123)
        self.assertEqual(len(self.base.e2("act_menu")), before)
        self.probe._menu_near_now()  # the last build (none in this zone) writes nothing either
        self.assertEqual(len(self.base.e2("act_menu")), before)

    def test_the_partial_part_is_marked_partial_and_carries_its_zone(self):
        """R1, R2: the first build's menu so far is a partial whole: partial true, no near, the zone id."""
        self.zone["current"] = 123
        self.probe._MENU_ZONE = 123
        build = _finished(self.probe.act_menu, self.probe._menu_jobs(self.row)[0], self.probe._menu_test)
        before = len(self.base.e2("act_menu"))
        self.probe._menu_partial_part(build)
        parts = self.base.e2("act_menu")[before:]
        self.assertTrue(parts)
        for part in parts:
            self.assertIs(part["partial"], True)
            self.assertNotIn("near", part)
            self.assertEqual(part["zone_id"], "123")

    def test_a_whole_and_a_near_part_carry_the_zone_of_the_build(self):
        """R2: the finished whole and the near part of a build in zone 123 say so."""
        self.zone["current"] = 123
        self.build_at(100.0)
        for menu in self.menus():
            self.assertEqual(menu["zone_id"], "123")
            self.assertNotIn("partial", menu)

    def test_an_empty_near_part_is_written_when_nothing_is_near(self):
        """PROBE3-16: nothing near her (the one object is 30 m away): an empty near part is written."""
        self.things = [acts._Thing(12, 30.0, [acts.ReadBook])]
        self.build_at(100.0)
        near = [menu for menu in self.menus() if menu.get("near")]
        self.assertEqual([(menu["objects"], menu["parts"]) for menu in near], [([], 1)])

    def test_an_object_on_another_level_is_not_near_her(self):
        """PROBE3-11: an object one floor up, two metres away, is not near; its job says so."""
        upstairs = acts._Thing(13, 1.0, [acts.ReadBook])
        upstairs.level = 1
        self.things = [upstairs]
        self.rooms = {13: "6"}
        jobs = list(self.probe._menu_jobs(self.row)[0])
        self.assertTrue(jobs)
        self.assertTrue(all(job["other_level"] is True for job in jobs))
        self.probe._MENU_BODY = (self.row["zone"]["position"], "4")
        refresh = self.probe._near_refresh(dict(jobs[0], obj=upstairs))
        self.assertIs(refresh["other_level"], True)
        self.assertFalse(self.probe.act_menu.is_near(dict(jobs[0], **refresh)))


class RefundAndCreateTests(unittest.TestCase):
    """PROBE3-6, PROBE3-9: a refund is read back; an event's exception is not "no event"."""

    def setUp(self):
        load_probe()
        from ashley_e1 import e2_actuator
        self.actuator = e2_actuator
        original = e2_actuator.services
        self.addCleanup(setattr, e2_actuator, "services", original)

    class Funds(object):
        def __init__(self, money, silent=False):
            self.money, self.silent = money, silent

        def add(self, amount, reason, sim=None, tags=None, count_as_earnings=True):
            if not self.silent:
                self.money += amount

    def test_a_refund_is_true_only_when_the_money_went_up_by_the_amount(self):
        funds = self.Funds(100)
        self.assertTrue(self.actuator.refund(types.SimpleNamespace(funds=funds), 50, None, "Test refund"))
        self.assertEqual(funds.money, 150)
        silent = self.Funds(100, silent=True)
        self.assertFalse(self.actuator.refund(types.SimpleNamespace(funds=silent), 50, None, "Test refund"))
        self.assertEqual(silent.money, 100)

    def test_an_event_whose_manager_raises_raises_and_is_not_taken_for_no_event(self):
        def raising(zone_id):
            raise RuntimeError("Test manager")
        self.actuator.services = types.SimpleNamespace(get_zone_situation_manager=raising)
        with self.assertRaises(RuntimeError):
            self.actuator.create_event(7, object(), None)

    def test_no_event_is_none_and_an_event_is_its_id(self):
        manager = types.SimpleNamespace(create_situation=lambda *args, **kwargs: None)
        self.actuator.services = types.SimpleNamespace(get_zone_situation_manager=lambda zone_id: manager)
        self.assertIsNone(self.actuator.create_event(7, object(), None))
        manager.create_situation = lambda *args, **kwargs: 77
        self.assertEqual(self.actuator.create_event(7, object(), None), "77")


class EventCommandTests(unittest.TestCase):
    """PROBE3-6 at the verb: an event whose create raises is UNKNOWN and no money comes back; an unread money after a
    made-nothing call is UNKNOWN. The event verb's harness (test_w13_fix_reach) is borrowed, not inherited."""
    setUp = test_w13_fix_reach.FixActTests.setUp
    tearDown = test_w13_fix_reach.FixActTests.tearDown
    sending_event = test_w13_fix_reach.FixActTests.sending_event
    ready = test_w13_p1.ReachActTests.ready
    send = test_w13_p1.ReachActTests.send
    act_events = test_w13_p1.ReachActTests.act_events

    def test_a_create_that_raises_is_unknown_and_refunds_nothing(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        refunds = []
        money = iter([1000, 750])
        with test_w13_p1._patched(self.probe.e2_actuator, "situation_type", lambda guid: test_w13_fix_reach._Situation),                 test_w13_p1._patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000),                 test_w13_p1._patched(self.probe.e2_actuator, "default_job", lambda s: "job"),                 test_w13_p1._patched(self.probe.e2_actuator, "event_guest_list", lambda *args: test_w13_fix_reach._Guests(0)),                 test_w13_p1._patched(self.probe.e2_actuator, "create_event", _raising),                 test_w13_p1._patched(self.probe.e2_actuator, "refund", lambda *args: refunds.append(args) or True),                 test_w13_p1._patched(self.probe.observers, "household_money", lambda info: next(money)):
            ok, _connection = self.sending_event()
        self.assertFalse(ok)
        self.assertEqual(refunds, [])
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "E2_EXCEPTION:RuntimeError"))

    def test_no_event_and_an_unread_wallet_is_unknown_not_rejected(self):
        self.ready()
        self.probe._KNOWN_EVENTS.add("9")
        money = iter([1000, None])
        with test_w13_p1._patched(self.probe.e2_actuator, "situation_type", lambda guid: test_w13_fix_reach._Situation),                 test_w13_p1._patched(self.probe.e2_actuator, "now_absolute_minutes", lambda: 1000),                 test_w13_p1._patched(self.probe.e2_actuator, "default_job", lambda s: "job"),                 test_w13_p1._patched(self.probe.e2_actuator, "event_guest_list", lambda *args: test_w13_fix_reach._Guests(0)),                 test_w13_p1._patched(self.probe.e2_actuator, "create_event", lambda *args: None),                 test_w13_p1._patched(self.probe.e2_actuator, "refund", lambda *args: self.fail("no refund")),                 test_w13_p1._patched(self.probe.observers, "household_money", lambda info: next(money)):
            ok, _connection = self.sending_event()
        self.assertFalse(ok)
        last = self.act_events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "FUNDS_UNREAD"))


def _raising(*args):
    raise RuntimeError("Test manager")


class SettleTests(home_tests.HomeCase):
    """PROBE3-7 and PROBE3-8 in the home harness of test_2400."""

    def setUp(self):
        super(SettleTests, self).setUp()
        self.chair = home_tests.FakeObj("41", value=40)
        self.actuator.objects["41"] = self.chair

    def tick(self, now):
        self.home.tick(self.control, now)

    def test_a_sale_the_game_finishes_late_is_paid_once_when_the_object_is_seen_gone(self):
        self.actuator.removal_queued = True
        self.run_cmd("sell", {"object_id": "41"})
        self.tick(1000.0)
        self.tick(1031.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "SELL_UNCONFIRMED"))
        self.assertIn("may still come", self.control.events[-1]["detail"])
        self.assertEqual(self.actuator.funds.money, 500)
        self.actuator.process_queue()
        self.tick(1040.0)
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "SOLD"))
        self.assertEqual(self.actuator.funds.money, 540)
        self.tick(1041.0)
        self.assertEqual(self.actuator.funds.money, 540)

    def test_a_sale_still_there_after_the_late_window_is_let_go(self):
        self.actuator.removal_queued = True
        self.run_cmd("sell", {"object_id": "41"})
        self.tick(1000.0)
        self.tick(1031.0)
        self.tick(1000.0 + self.home.LATE_SALE_S + 1)
        self.assertEqual(self.home.state_of(self.control).pending_gone, {})
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_charge_that_cannot_be_read_is_refunded_only_when_the_read_back_shows_the_price_fell(self):
        self.actuator.money_hidden_after_charge = True
        self.actuator.removal_queued = True
        self.assertFalse(self.run_cmd("buy", self.args()))
        self.actuator.money_hidden = False  # the money reads again once the removal has settled
        self.actuator.process_queue()
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "CHARGE_UNKNOWN"))
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_charge_that_cannot_be_read_stays_unknown_when_the_read_back_cannot_read_either(self):
        self.actuator.money_hidden_after_charge = True
        self.actuator.removal_queued = True
        self.assertFalse(self.run_cmd("buy", self.args()))
        self.actuator.process_queue()
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "CHARGE_UNKNOWN"))
        self.assertEqual(self.actuator.funds.money, 350)

    def args(self):
        return {"definition_id": "55", "place": home_tests._place("wall", "5")}
