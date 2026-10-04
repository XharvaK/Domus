"""DA6D food routes, food scan, and hunger trials. Fakes only."""
import json
import os
import unittest

from test_da6a_trial import _Offer
from test_da6c import Hosted
from test_e2 import CHAIR, _load_pure

SCRIPT = "InteractionSource.SCRIPT_WITH_USER_INTENT"


class Picker(object):
    pass


class AutonomousPickerSuperInteraction(Picker):
    pass


class StartCraftingAutonomouslySuperInteraction(AutonomousPickerSuperInteraction):
    pass


class StartCraftingOrderAutonomouslySuperInteraction(StartCraftingAutonomouslySuperInteraction):
    pass


class ObjectPickerInteraction(Picker):
    pass


class AutonomousObjectPickerInteraction(ObjectPickerInteraction):
    pass


class fridge_GrabSnackAutonomously(StartCraftingAutonomouslySuperInteraction):
    guid64 = 13397
    allow_user_directed = 0
    allow_autonomous = 1
    favorite_recipe = None
    auto_pick = None

    @classmethod
    def use_pie_menu(cls):
        return False

    @classmethod
    def picker_rows_gen(cls, inst, target, context):
        yield _RecipeRow(recipe_CookPasta, 5, True, 10, 1)
        yield _BoomRow()


class fridge_CookAutonomously(StartCraftingAutonomouslySuperInteraction):
    guid64 = 13388


class catering_StartCraftingOrderAutonomously(StartCraftingOrderAutonomouslySuperInteraction):
    guid64 = 50


class fridge_GrabLeftover(ObjectPickerInteraction):
    guid64 = 60


class sell_items_picker(ObjectPickerInteraction):
    guid64 = 70


class fridge_HaveMeal(ObjectPickerInteraction):
    guid64 = 77672
    favorite_recipe = None
    auto_pick = None
    use_pie_menu = None
    allow_user_directed = 1
    allow_autonomous = 0


class recipe_CookPasta(object):
    pass


class _RecipeRow(object):
    def __init__(self, tag, recipe_id, is_enable, price, skill_level):
        self.tag = tag
        self.recipe_id = recipe_id
        self.is_enable = is_enable
        self.price = price
        self.skill_level = skill_level


class _BoomRow(object):
    tag = recipe_CookPasta
    recipe_id = 9

    @property
    def is_enable(self):
        raise RuntimeError("menu")

    price = 1
    skill_level = 0


class _Raise(object):
    def __get__(self, obj, owner):
        raise RuntimeError("scan")


class _Unreadable(object):
    guid64 = 13388
    favorite_recipe = None
    auto_pick = _Raise()


class FoodRouteTests(unittest.TestCase):
    def setUp(self):
        _load_pure()
        from ashley_e1 import e2_actuator
        self.actuator = e2_actuator

    def test_routes_and_picker_exclusion(self):
        act = self.actuator
        self.assertEqual(act.food_route(fridge_GrabSnackAutonomously), "auto_craft")
        self.assertEqual(act.food_route(fridge_CookAutonomously), "auto_craft")
        self.assertIsNone(act.food_route(catering_StartCraftingOrderAutonomously))
        self.assertEqual(act.food_route(AutonomousObjectPickerInteraction), "auto_pick")
        self.assertEqual(act.food_route(fridge_GrabLeftover), "auto_pick")
        self.assertIsNone(act.food_route(sell_items_picker))
        self.assertIsNone(act.excluded(fridge_GrabSnackAutonomously))
        self.assertIsNone(act.excluded(fridge_GrabLeftover))
        self.assertEqual(act.excluded(fridge_HaveMeal), "picker")
        self.assertEqual(act.excluded(sell_items_picker), "picker")
        self.assertEqual(act.excluded(catering_StartCraftingOrderAutonomously), "picker")


class _Fridge(object):
    _super_affordances = (
        fridge_GrabSnackAutonomously, fridge_HaveMeal, _Unreadable, sell_items_picker)

    def __init__(self, object_id):
        self.id = int(object_id)


class FoodScanTests(Hosted):
    def test_scan_header_menu_error_and_footer(self):
        self.ready()
        self.assertTrue(self.probe._start_inbox_pump("import"))
        fridge = _Fridge(CHAIR)
        manager = type("M", (), {"_objects": {fridge.id: fridge}})()
        self.probe._services_module.object_manager = lambda: manager
        connection = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch({"command": "food_scan", "args": {}}, connection))
        scan = self.probe._FOOD
        self.assertTrue(os.path.isfile(scan.partial))
        while scan.state == "running":
            self.probe._food_tick()
        with open(scan.out_path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(rows[0]["kind"], "food_header")
        self.assertEqual(rows[-1]["kind"], "food_footer")
        body = [row for row in rows if row["kind"] == "food_affordance"]
        by_name = {row.get("name"): row for row in body if row.get("name")}
        self.assertEqual(by_name["fridge_GrabSnackAutonomously"]["food_route"], "auto_craft")
        self.assertIsNone(by_name["fridge_GrabSnackAutonomously"]["excluded"])
        self.assertEqual(by_name["fridge_HaveMeal"]["excluded"], "picker")
        self.assertTrue(any(row.get("error") for row in body))
        menu = [row for row in rows if row["kind"] == "food_menu"]
        self.assertEqual(menu[0]["recipe_name"], "recipe_CookPasta")
        self.assertNotEqual(menu[0].get("recipe_name"), "localized")
        self.assertTrue(menu[0]["is_enable"])
        self.assertEqual(menu[0]["price"], 10)
        self.assertTrue(any(row.get("error") for row in menu))
        self.assertGreater(rows[-1]["errors"], 0)
        self.assertFalse(os.path.isfile(scan.partial))


class FoodTrialTests(Hosted):
    def _clock(self):
        self._mono = 5_000_000_000

        def now():
            return self._mono

        self.probe.observers._monotonic_ns = now
        self.probe.e2_control.time.perf_counter_ns = now

    def _advance(self, seconds):
        self._mono += int(seconds * 1e9)

    def _hunger(self, value):
        self.probe.observers.read_motives = lambda *_a, **_k: [
            {"id": "hunger", "value": value, "band": "ok", "age_ticks": 0}]

    def _offer(self):
        self.base.objects[CHAIR] = _Offer(CHAIR, [fridge_GrabSnackAutonomously])

    def _push(self):
        self.ready()
        self._clock()
        self._hunger(10)
        self.base.ticks = 1000
        self.base.tick()
        self.base.ticks = 1100
        self.base.tick()
        self.base.ticks = 5000
        self._offer()
        self.assertTrue(self.trial(guid64="13397")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        self.assertEqual(experiment.card["card_class"], "need")
        self.assertEqual(experiment.card["motive"], "hunger")
        self.assertGreaterEqual(len(experiment.control_rows), 2)
        self.assertEqual(experiment.window_seconds, 600.0)
        return experiment

    def _child(self, iid):
        from test_da6a_trial import _running
        item = _running(iid, SCRIPT)
        item.cancels = []

        def cancel(finishing_type, cancel_reason_msg=None):
            item.cancels.append((finishing_type, cancel_reason_msg))

        item.cancel = cancel
        return item

    def test_pass_when_hunger_rises_with_a_child_running(self):
        experiment = self._push()
        parent = self._child(777)
        child = self._child(862)
        self.base.sim.si_state = [parent, child]
        self._hunger(10)
        self.base.ticks = 5000
        self.base.tick()
        self._hunger(40)
        steps = 0
        while not experiment.closed and steps < 200:
            self._advance(4)
            self.base.ticks += 1
            self.base.tick()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertEqual(experiment.verdict, "PASS")
        verdict = [row for row in self.e2() if row["phase"] == "VERDICT"][-1]
        self.assertIn("route=auto_craft", verdict["detail"])
        self.assertIn("hunger=10->40", verdict["detail"])
        self.assertIn("862", experiment.children)

    def test_unknown_when_hunger_stays_flat(self):
        experiment = self._push()
        self.base.sim.si_state = [self._child(777)]
        self._mono = 5_000_000_000 + int(600e9)
        self.probe.observers._monotonic_ns = lambda: self._mono
        self.probe.e2_control.time.perf_counter_ns = lambda: self._mono
        self.base.ticks = 8000
        self.base.tick()
        self.assertEqual(experiment.verdict, "OUTCOME_UNKNOWN")
        verdict = [row for row in self.e2() if row["phase"] == "VERDICT"][-1]
        self.assertIn("hunger=", verdict["detail"])
        self.assertNotIn("hunger=10->40", verdict["detail"])

    def test_cleanup_leaves_a_rising_family_and_cancels_a_queued_push(self):
        experiment = self._push()
        pushed = experiment.interaction_ref
        child = self._child(862)
        self.base.sim.queue = [pushed]
        self.base.sim.si_state = [child]
        self._hunger(10)
        self.base.tick()
        self._hunger(20)
        self._mono = 5_000_000_000 + int(700e9)
        self.probe.observers._monotonic_ns = lambda: self._mono
        self.probe.e2_control.time.perf_counter_ns = lambda: self._mono
        self.base.tick()
        cleanup = [row for row in self.e2() if row["phase"] == "TRIAL_CLEANUP"][-1]
        self.assertEqual(cleanup["detail"], "food_left_running")
        self.assertTrue(pushed.cancels)
        self.assertEqual(child.cancels, [])

        self.base.sim.queue = []
        self.base.sim.si_state = []
        self.probe._cmd_disarm()
        self.base.LedgerWriter.instances[-1].finish()
        experiment = self._push()
        pushed = experiment.interaction_ref
        child = self._child(862)
        self.base.sim.si_state = [pushed, child]
        self._hunger(10)
        self.base.tick()
        self._hunger(25)
        self._mono = 5_000_000_000 + int(700e9)
        self.probe.observers._monotonic_ns = lambda: self._mono
        self.probe.e2_control.time.perf_counter_ns = lambda: self._mono
        self.base.tick()
        cleanup = [row for row in self.e2() if row["phase"] == "TRIAL_CLEANUP"][-1]
        self.assertEqual(cleanup["detail"], "food_left_running")
        self.assertEqual(pushed.cancels, [])
        self.assertEqual(child.cancels, [])


if __name__ == "__main__":
    unittest.main()
