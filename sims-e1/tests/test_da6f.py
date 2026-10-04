"""DA6F: the second live session (2.11.1). Fakes only."""
import unittest

from test_e2 import _load_pure


class FoodNameTests(unittest.TestCase):
    def setUp(self):
        _load_pure()
        from ashley_e1 import food
        self.food = food

    def test_word_start_not_substring(self):
        """D21: 401 of 701 live rows were cheats, deaths and create-object."""
        hit = self.food.name_hit
        for name in ("cheat_set_as_head", "death_Hunger", "Knitting_CreateObject_Finished",
                     "splash_Sim_seated", "debugDeathInteraction", "Cheat_AddToFamily"):
            self.assertFalse(hit(name, 1), name)
        for name in ("fridge_GrabSnackAutonomously", "stove_Cook_PieMenu_Dinner_8Servings_Ingredients",
                     "refrigerator_GetLeftovers_Lunch_Picker", "fridge_CookGroupMeal_Autonomously",
                     "sim_DrinkEnergyJuice", "eat_Plate", "fridge_CreateSnackAndConsume_Generic",
                     "BBQMeal"):
            self.assertTrue(hit(name, 1), name)
        self.assertTrue(hit("anything", 13397))

    def test_words(self):
        words = self.food._words
        self.assertEqual(words("stove_Cook_PieMenu_8Servings"),
                         ["stove", "cook", "pie", "menu", "8", "servings"])
        self.assertEqual(words("BBQMeal"), ["bbq", "meal"])
        self.assertEqual(words("toilet-use-sitting"), ["toilet", "use", "sitting"])
        self.assertEqual(words("debugDeathInteraction"), ["debug", "death", "interaction"])
        self.assertEqual(words(""), [])


class ScanProgressTests(unittest.TestCase):
    def setUp(self):
        _load_pure()

    def test_preflight_and_food_report_progress(self):
        """D22: a ten-minute preflight looked stuck; status had no block for it."""
        import tempfile, os
        from ashley_e1 import food, preflight
        folder = tempfile.mkdtemp()
        for module, cls in ((preflight, preflight.PreflightScan), (food, food.FoodScan)):
            scan = cls([{"object_id": "1"}] * 3, os.path.join(folder, module.__name__ + ".jsonl"),
                       lambda job: {"kind": "x"}, max_per_chunk=2)
            self.assertEqual(scan.progress()["state"], "running")
            self.assertEqual(scan.progress()["total"], 3)
            self.assertTrue(scan.progress()["file"].endswith(".partial"))
            scan.step()
            self.assertEqual(scan.progress()["done"], 2)
            scan.step()
            done = scan.progress()
            self.assertEqual((done["state"], done["done"], done["chunks"]), ("done", 3, 2))
            self.assertFalse(done["file"].endswith(".partial"))


from test_da6e import AUTONOMY, BODY_CANCEL, SCRIPT, _Replay, bed_sleep  # noqa: E402
from test_da6a_trial import _Offer, _running  # noqa: E402
from test_e2 import CHAIR  # noqa: E402
from test_da6c import Hosted  # noqa: E402


class LiveSleepReplay(_Replay):
    """412d52ea-2: bed_sleep pushed at energy 24 (relief=energy), energy 26 -> 100 at
    speed 3, she woke at row 1381 (FINISHED NATURAL); the interaction card waited for
    the 180 s window (VERDICT at 1519) and the PASS detail had no energy reading."""

    def test_sleep_closes_after_waking_and_reports_energy(self):
        import types
        self.ready()
        self._clock()
        self._motives(energy=24, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(16):  # live 1331-1346: walking to the bed at energy 24
            self._step()
        for value in range(26, 101, 4):
            self._motives(energy=value, hunger=50)
            self._step(ticks=37000)
        self._motives(energy=100, hunger=48)
        for _ in range(5):
            self._step(ticks=37000)
        # Live 1382-1385: sim-stand BODY_CANCEL_AOP running, idle_Hunger AUTONOMY queued.
        self.base.sim.si_state = [_running(3861, BODY_CANCEL, target=999)]
        self.base.sim.queue = [_running(3863, AUTONOMY, target=999)]
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        steps = 0
        while not experiment.closed and steps < 200:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertLess(steps, 45, "D26: closes after she wakes, not at the window")
        self.assertEqual(experiment.verdict, "PASS", (experiment.ambiguous, experiment.claims,
                         experiment.foreign_roots, experiment.incomplete_rows))
        detail = self._verdict()["detail"]
        self.assertIn("relief=energy energy=24->100->100", detail)


class _RatedCommodity(object):
    """A commodity with the game's pure rate getters (bytecode continuous_statistic)."""

    def __init__(self, guid, value, updated, change=0.0, decay=0.0, convergence=0.0,
                 until=None, suppressed=False):
        self.guid64 = guid
        self._value = value
        self._last_update = updated
        self.min_value = 0
        self.max_value = 100
        self._change = change
        self._decay = decay
        self.convergence_value = convergence
        self._until = until
        self._tracker = type("T", (), {"should_suppress_calculations":
                                        lambda _self: suppressed})()

    def _get_change_rate_without_decay(self):
        return self._change

    def _calculate_minutes_until_value_is_reached_through_decay(self, target):
        return self._until

    def get_decay_rate(self):
        return self._decay

    def get_value(self):
        raise AssertionError("get_value writes the cache")

    def _update_value(self):
        raise AssertionError("_update_value writes the cache")


class CurrentMotiveTests(unittest.TestCase):
    """D25: at speed 3 (sleep, work) rows are ~37000 ticks apart; the cache of a
    need she was not refilling read 47554 ticks old and was stale."""

    def setUp(self):
        _load_pure()
        from ashley_e1 import observers
        self.observers = observers

    def read(self, commodity, now):
        row, fault = self.observers._read_cached_motive(commodity, now)
        self.assertIsNone(fault)
        return row["value"], row["age_ticks"]

    def test_decay_over_a_speed_three_gap(self):
        # hunger 40 at tick 0, -0.5 per sim minute, read 47554 ticks (31.7 min) later.
        hunger = _RatedCommodity(16656, 40.0, 0, change=-0.5)
        self.assertEqual(self.read(hunger, 47554), (24, 0))

    def test_decay_stops_at_convergence(self):
        fun = _RatedCommodity(16655, 60.0, 0, decay=-1.0, convergence=50.0, until=10.0)
        self.assertEqual(self.read(fun, 45000), (50, 0))

    def test_clamped_and_suppressed(self):
        energy = _RatedCommodity(16657, 95.0, 0, change=2.0)
        self.assertEqual(self.read(energy, 30000), (100, 0))
        frozen = _RatedCommodity(16657, 30.0, 0, change=-5.0, suppressed=True)
        self.assertEqual(self.read(frozen, 30000), (30, 0))

    def test_unreadable_rates_keep_the_cache_and_its_age(self):
        class Bare(object):
            guid64 = 16656
            _value = 40.0
            _last_update = 0
            min_value = 0
            max_value = 100
        self.assertEqual(self.read(Bare(), 47554), (40, 47554))



class LiveShortInteractionReplay(_Replay):
    """bf262461-1: shower_Clean ATTRIBUTED at row 205, FINISHED NATURAL at 210 (5 s,
    MAINTAINED_10S false); the verdict waited for the 180 s window."""

    def test_short_natural_finish_closes_early_and_passes(self):
        import types
        self.ready()
        self._clock()
        self._motives(energy=70, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(5):
            self._step()
        self.base.sim.si_state = []
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        steps = 0
        while not experiment.closed and steps < 300:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertLess(steps, 45, "D27: a natural finish settles before the window")
        self.assertEqual(experiment.verdict, "PASS")



class RisenNeedsTests(unittest.TestCase):
    """D28: a trial's verdict names the needs that rose (live shower 82->100)."""

    def setUp(self):
        _load_pure()
        from ashley_e1 import e2_control
        self.control = e2_control

    def rows(self, *values):
        return [{"motives": [{"id": "hygiene", "value": h}, {"id": "bladder", "value": b},
                             {"id": "energy", "value": e}]} for h, b, e in values]

    def test_rises_largest_first_and_skips_relief(self):
        import types
        experiment = types.SimpleNamespace(_rows_since=self.rows(
            (82, 60, 30), (90, 59, 36), (100, 58, 38), (99, 58, 38)))
        risen = self.control._risen(experiment, set())
        self.assertEqual([(m, s) for m, s in risen],
                         [("hygiene", [82, 100, 99]), ("energy", [30, 38, 38])])
        self.assertEqual([m for m, _s in self.control._risen(experiment, {"hygiene"})],
                         ["energy"])

    def test_small_or_falling_needs_are_quiet(self):
        import types
        experiment = types.SimpleNamespace(_rows_since=self.rows(
            (82, 60, 30), (85, 50, 31), [True, None, "x"]))
        self.assertEqual(self.control._risen(experiment, set()), [])



class LiveReflexAftermathReplay(_Replay):
    """bf262461-5: sink_washHands FINISHED row 933; bladder 12 at row 1069 brought the
    game's reflex (toilet, flush, then AUTONOMY sink_washHands on our sink at 1089);
    VERDICT OUTCOME_UNKNOWN foreign_roots=1."""

    def test_native_reflex_after_finish_is_not_a_rival(self):
        import types
        self.ready()
        self._clock()
        self._motives(energy=70, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(5):
            self._step()
        self.base.sim.si_state = []
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        for _ in range(8):
            self._step()
        self.base.sim.si_state = [types.SimpleNamespace(
            id=1687, guid64=14241, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=AUTONOMY))]
        steps = 0
        while not experiment.closed and steps < 300:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertEqual(experiment.foreign_roots, [])
        self.assertEqual(experiment.verdict, "PASS")

    def test_native_follow_up_inside_the_grace_is_not_a_rival(self):
        """8f02c83a-1: toilet-use-sitting FINISHED row 880; the game's AUTONOMY
        toilet-flush on our toilet at 881; VERDICT OUTCOME_UNKNOWN foreign_roots=1."""
        import types
        self.ready()
        self._clock()
        self._motives(energy=70, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(12):
            self._step()
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        self.base.sim.si_state = [types.SimpleNamespace(
            id=939, guid64=14426, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=AUTONOMY))]
        steps = 0
        while not experiment.closed and steps < 300:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertEqual(experiment.foreign_roots, [])
        self.assertEqual(experiment.verdict, "PASS")


class RejectCodeTests(Hosted):
    """D34: 2c815d4c BODY_BUSY (a game reaction_SmellBad was running) replied
    REJECTED with code null; the reason lived only in its TRIAL_REJECT line."""

    def test_reject_line_names_the_code(self):
        code = self.probe._reject_code
        self.assertEqual(code(["TRIAL_REJECT BODY_BUSY"]), "BODY_BUSY")
        self.assertEqual(code(["other", "TRIAL_REJECT OBJECT_EXCLUDED x"]), "OBJECT_EXCLUDED")
        self.assertIsNone(code([]))
        self.assertIsNone(code(["TRIAL_PUSHED a-1 interaction 50", None]))


class Collect_Clean_Dish(object):
    guid64 = 13173


class generic_consume_food(object):
    guid64 = 13433


class _Plate(object):
    _super_affordances = (Collect_Clean_Dish,)

    def __init__(self, object_id):
        self.id = int(object_id)
        self.offered_calls = 0

    def super_affordances(self, context=None):
        self.offered_calls += 1
        yield Collect_Clean_Dish
        yield generic_consume_food


class ComponentOfferTests(Hosted):
    """D35: 2c815d4c-2 cooked a grilled cheese; the plate's eat (generic_consume_food,
    from its consumable component) was in neither preflight nor the food scan."""

    def _rows(self, command, scan_attr, tick):
        from test_da6c import PreflightTests
        PreflightTests._manager(self, {self.plate.id: self.plate})
        connection = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch({"command": command, "args": {}},
                                                   connection), connection.code)
        scan = getattr(self.probe, scan_attr)
        while scan.state == "running":
            tick()
        import json
        with open(scan.out_path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def setUp(self):
        super(ComponentOfferTests, self).setUp()
        self.ready()
        self.assertTrue(self.probe._start_inbox_pump("import"))
        self.base.sim.test_super_affordance = lambda affordance, obj, context: True
        self.plate = _Plate("845576415849939098")

    def test_preflight_lists_the_plate_eat_once(self):
        rows = self._rows("preflight", "_PREFLIGHT", self.probe._preflight_tick)
        names = [row["name"] for row in rows if row["kind"] == "preflight"]
        self.assertEqual(sorted(names), ["Collect_Clean_Dish", "generic_consume_food"])
        self.assertEqual(self.plate.offered_calls, 1)

    def test_food_scan_names_the_plate_eat(self):
        _load_pure()
        from ashley_e1 import food
        self.assertTrue(food.name_hit("generic_consume_food", 13433))
        self.assertFalse(food.name_hit("Collect_Clean_Dish", 13173))


class LiveReactionAftermathReplay(_Replay):
    """2c815d4c-3: generic_consume_food FINISHED row 958; dish to the sink, then the
    game's reaction_SmellBad (source SCRIPT) at a spoiled tray at 970; VERDICT
    OUTCOME_UNKNOWN foreign_roots=1 rose=hunger 35->100->98."""

    def _finished_then(self, source):
        import types
        self.ready()
        self._clock()
        self._motives(energy=70, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(12):
            self._step()
        self.base.sim.si_state = []
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        for _ in range(8):
            self._step()
        self.base.sim.si_state = [types.SimpleNamespace(
            id=911, guid64=24661, affordance="x",
            target=types.SimpleNamespace(id=744245394127586618),
            context=types.SimpleNamespace(source=source))]
        steps = 0
        while not experiment.closed and steps < 300:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        return experiment

    def test_game_reaction_after_finish_is_not_a_rival(self):
        experiment = self._finished_then("InteractionSource.SCRIPT")
        self.assertEqual(experiment.foreign_roots, [])
        self.assertEqual(experiment.verdict, "PASS")

    def test_a_late_push_with_intent_is_still_a_rival(self):
        experiment = self._finished_then(SCRIPT)
        self.assertEqual(len(experiment.foreign_roots), 1)
        self.assertEqual(experiment.verdict, "OUTCOME_UNKNOWN")
