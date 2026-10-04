"""S1: object facts as the game holds them (servings, freshness, recipe, crafter)."""
import json
import os
import types
import unittest

from test_da6c import Hosted
from test_ds3_senses import _Wrapper


class Freshness(object):
    pass


class Freshness_Fresh(object):
    pass


class DishLocation(object):
    pass


class DishLocation_Counter(object):
    pass


class statistic_Servings(object):
    pass


class commodity_Spoilage(object):
    pass


class recipe_Food_EggsAndToast(object):
    name = _Wrapper(0xa70d623e)
    multi_serving_name = _Wrapper(0x1234)


class _Tracker(object):
    def should_suppress_calculations(self):
        return True


class object_Food_PlateFork_Multi(object):
    is_sim = False

    def __init__(self, object_id):
        self.id = object_id
        self.definition = types.SimpleNamespace(id=555)
        self.position = types.SimpleNamespace(x=4.0, y=0.0, z=1.0)
        self.level = 0
        self.zone_id = 7
        self.state_component = types.SimpleNamespace(_states={
            Freshness: Freshness_Fresh, DishLocation: DishLocation_Counter})
        self.statistic_tracker = types.SimpleNamespace(_statistics={
            statistic_Servings: types.SimpleNamespace(_modified_value=7)})
        self.commodity_tracker = types.SimpleNamespace(_statistics={
            commodity_Spoilage: types.SimpleNamespace(_value=63.456, _last_update=10,
                                                      _tracker=_Tracker())})
        process = types.SimpleNamespace(
            _recipe=recipe_Food_EggsAndToast, _crafter_sim_id=100,
            crafter=types.SimpleNamespace(first_name="E1", last_name="Proband"))
        self.crafting_component = types.SimpleNamespace(_crafting_process=process)

    def get_value(self, *args):
        raise AssertionError("plain reads only")


class object_sinkPedC(object):
    is_sim = False

    def __init__(self, object_id):
        self.id = object_id
        self.definition = types.SimpleNamespace(id=556)
        self.position = types.SimpleNamespace(x=9.0, y=0.0, z=1.0)
        self.level = 0
        self.zone_id = 7


class SimLike(object):
    is_sim = True
    id = 100


class ObjectFactTests(unittest.TestCase):
    def setUp(self):
        from test_binding import load_probe
        _, self.probe, _ = load_probe()
        self.probe.observers.get_room_id = lambda zone, position, level: 3
        self.situation = self.probe.situation

    def test_platter_reads_like_its_tooltip(self):
        row = self.situation.object_fact(object_Food_PlateFork_Multi(40557982600986950), 20)
        self.assertEqual(row, {
            "kind": "object", "object_id": "40557982600986950", "definition_id": "555",
            "class": "object_Food_PlateFork_Multi",
            "position": {"x": 4.0, "y": 0.0, "z": 1.0, "level": 0}, "room": "3",
            "states": {"DishLocation": "DishLocation_Counter", "Freshness": "Freshness_Fresh"},
            "stats": {"commodity_Spoilage": 63.46, "statistic_Servings": 7.0},
            "craft": {"recipe": "recipe_Food_EggsAndToast", "name_key": str(0xa70d623e),
                      "multi_name_key": str(0x1234), "crafter_id": "100",
                      "crafter": "E1 Proband"},
            "tags": None, "in_use": False, "used_by": [], "rates": {}})

    def test_plain_object_and_sims(self):
        row = self.situation.object_fact(object_sinkPedC(9), 20)
        self.assertEqual((row["class"], row["states"], row["stats"], row["craft"]),
                         ("object_sinkPedC", None, {}, None))
        self.assertIsNone(self.situation.object_fact(SimLike(), 20))
        self.assertIsNone(self.situation.object_fact(types.SimpleNamespace(is_sim=False), 20))

    def test_scan_writes_header_rows_footer(self):
        import tempfile
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "situation.jsonl")
        clock = iter([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        scan = self.situation.SituationScan(
            [object_Food_PlateFork_Multi(1), SimLike(), object_sinkPedC(2)], path, 20,
            header={"body_id": "100"}, clock=lambda: next(clock, 0.0))
        while scan.state == "running":
            scan.step()
        with open(path, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertEqual(rows[0]["kind"], "situation_header")
        self.assertEqual(rows[0]["body_id"], "100")
        self.assertEqual([row["object_id"] for row in rows if row["kind"] == "object"],
                         ["1", "2"])
        self.assertEqual(rows[-1]["kind"], "situation_footer")
        self.assertEqual(rows[-1]["count"], 2)


class SituationCommandTests(Hosted):
    def test_gates_then_scan(self):
        connection = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._inbox_dispatch(
            {"command": "situation_scan", "args": {}}, connection))
        self.assertEqual(connection.code, "SITUATION_UNARMED")
        self.ready()
        self.assertTrue(self.probe._start_inbox_pump("import"))
        manager = types.SimpleNamespace(
            _objects={1: object_Food_PlateFork_Multi(1)}, get=lambda oid: None)
        self.probe._services_module.object_manager = lambda: manager
        connection = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(
            {"command": "situation_scan", "args": {}}, connection), connection.code)
        scan = self.probe._SITUATION
        while scan.state == "running":
            self.probe._situation_tick()
        self.assertEqual(self.probe._inbox_status()["situation"]["state"], "done")
        with open(scan.out_path, encoding="utf-8") as handle:
            kinds = [json.loads(line)["kind"] for line in handle]
        self.assertEqual(kinds, ["situation_header", "object", "situation_footer"])

    def test_command_is_on_the_wire(self):
        from ashley_e1 import cmdbox
        self.assertIn("situation_scan", cmdbox.COMMANDS)


if __name__ == "__main__":
    unittest.main()
