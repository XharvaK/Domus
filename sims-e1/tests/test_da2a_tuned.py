"""DA2A 2.5.0 tuned_scan. Fakes only."""
import json
import os
import sys
import unittest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from test_binding import install_stubs, load_probe
from test_d10 import command

install_stubs()
from ashley_e1.tuned import TunedScan
import ashley_e1.cmdbox as cmdbox
import ashley_e1.schema as schema


def _clock(values):
    pending = list(values)

    def clock():
        if len(pending) > 1:
            return pending.pop(0)
        return pending[0]
    return clock


class _Aff(object):
    def __init__(self, guid):
        self.guid64 = guid


class _Base(object):
    _super_affordances = (_Aff(2), _Aff(1))
    is_sim = False


class _Child(_Base):
    @property
    def _super_affordances(self):
        raise AssertionError("instance property")


class _BadMeta(type):
    @property
    def __name__(self):
        raise RuntimeError("boom")


class _Bad(object, metaclass=_BadMeta):
    _super_affordances = ()


class _Trip(object):
    _super_affordances = (_Aff(3),)
    is_sim = True

    def super_affordances(self, *args, **kwargs):
        raise AssertionError("super_affordances")

    def potential_interactions(self, *args, **kwargs):
        raise AssertionError("potential_interactions")

    def component_super_affordances_gen(self, *args, **kwargs):
        raise AssertionError("component_super_affordances_gen")

    def _potential_behavior_affordances_gen(self, *args, **kwargs):
        raise AssertionError("_potential_behavior_affordances_gen")

    def is_affordance_available(self, *args, **kwargs):
        raise AssertionError("is_affordance_available")

    def push_super_affordance(self, *args, **kwargs):
        raise AssertionError("push_super_affordance")

    def get_statistic(self, *args, **kwargs):
        raise AssertionError("get_statistic")

    def get_value(self, *args, **kwargs):
        raise AssertionError("get_value")


def _obj(guid_pair=True):
    obj = _Child()
    obj.__dict__["id"] = 11
    definition = type("Def", (), {})()
    definition.__dict__["id"] = 22
    obj.__dict__["definition"] = definition
    return obj


class TunedModuleTests(unittest.TestCase):
    def test_budget_and_chunk_cap(self):
        objs = [_obj(), _obj(), _obj(), _obj(), _obj()]
        path = os.path.join(self._dir(), "cap.jsonl")
        scan = TunedScan(objs, path, budget_ms=5.0, max_per_chunk=50,
                         clock=_clock([0.0, 0.0, 0.006]))
        scan.step()
        self.assertEqual(scan.progress()["done"], 1)
        capped = TunedScan(objs, path + ".b", budget_ms=5.0, max_per_chunk=2,
                           clock=_clock([0.0]))
        capped.step()
        self.assertEqual(capped.progress()["done"], 2)

    def test_cursor_resumes_without_duplicates(self):
        objs = [_obj(), _obj(), _obj()]
        for index, obj in enumerate(objs):
            obj.__dict__["id"] = index + 1
        path = os.path.join(self._dir(), "cursor.jsonl")
        scan = TunedScan(objs, path, budget_ms=1000.0, max_per_chunk=2,
                         clock=_clock([0.0]))
        scan.step()
        scan.step()
        self.assertEqual(scan.state, "done")
        ids = [row["object_id"] for row in _rows(path) if row["kind"] == "tuned_on_class"]
        self.assertEqual(ids, ["1", "2", "3"])

    def test_class_value_not_instance_property(self):
        path = os.path.join(self._dir(), "class.jsonl")
        scan = TunedScan([_obj()], path, budget_ms=1000.0, clock=_clock([0.0]))
        scan.step()
        row = [item for item in _rows(path) if item["kind"] == "tuned_on_class"][0]
        self.assertEqual(row["affordance_guid64s"], [1, 2])
        self.assertFalse(row["truncated"])
        self.assertEqual(row["is_sim"], False)
        self.assertEqual(row["definition_id"], 22)
        self.assertEqual(row["class_name"], "_Child")

    def test_cap_64_and_truncated(self):
        class Wide(_Base):
            _super_affordances = tuple(_Aff(index) for index in range(70, 0, -1))
        obj = Wide()
        obj.__dict__["id"] = 5
        path = os.path.join(self._dir(), "wide.jsonl")
        scan = TunedScan([obj], path, budget_ms=1000.0, clock=_clock([0.0]))
        scan.step()
        row = [item for item in _rows(path) if item["kind"] == "tuned_on_class"][0]
        self.assertEqual(row["affordance_guid64s"], list(range(1, 65)))
        self.assertTrue(row["truncated"])

    def test_class_affordances_guid_on_class_mro(self):
        aff_a = type("AffA", (), {"guid64": 123})
        aff_b = type("AffB", (), {"guid64": 45})

        class _Parent(object):
            guid64 = 9

        class _ChildAff(_Parent):
            pass

        class _Desc(object):
            @property
            def guid64(self):
                return 999

        class _Pair(object):
            _super_affordances = (aff_a, aff_b, _ChildAff, _Desc)

        class _Frozen(object):
            _super_affordances = frozenset((aff_b, aff_a))

        class _AsSet(object):
            _super_affordances = set((aff_a,))

        pair = _Pair()
        pair.__dict__["id"] = 30
        frozen = _Frozen()
        frozen.__dict__["id"] = 31
        as_set = _AsSet()
        as_set.__dict__["id"] = 32
        path = os.path.join(self._dir(), "class-guid.jsonl")
        scan = TunedScan([pair, frozen, as_set], path, budget_ms=1000.0, clock=_clock([0.0]))
        scan.step()
        rows = {row["object_id"]: row for row in _rows(path) if row["kind"] == "tuned_on_class"}
        self.assertEqual(rows["30"]["affordance_guid64s"], [9, 45, 123])
        self.assertEqual(rows["31"]["affordance_guid64s"], [45, 123])
        self.assertEqual(rows["32"]["affordance_guid64s"], [123])

    def test_error_row_continues(self):
        bad = _Bad()
        bad.__dict__["id"] = 8
        good = _obj()
        path = os.path.join(self._dir(), "err.jsonl")
        scan = TunedScan([bad, good], path, budget_ms=1000.0, clock=_clock([0.0]))
        scan.step()
        kinds = [row["kind"] for row in _rows(path)]
        self.assertIn("tuned_error", kinds)
        self.assertIn("tuned_on_class", kinds)
        self.assertEqual(scan.state, "done")

    def _dir(self):
        root = os.path.join(os.environ.get("TEMP", "."), "da2a-tuned-unit")
        os.makedirs(root, exist_ok=True)
        return root


def _rows(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class TunedProbeTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _calls = load_probe()
        self.probe._start_inbox_pump("import")

        class _Manager(object):
            def __init__(self):
                self._objects = {}

        self.manager = _Manager()
        services = self.probe._services_module

        def object_manager():
            return self.manager

        services.object_manager = object_manager

    def test_no_manager_rejects_without_file(self):
        self.probe._services_module.object_manager = lambda: None
        reply = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._inbox_dispatch(command("tuned_scan"), reply))
        self.assertEqual(reply.code, "TUNED_NO_LOT")
        folder = os.path.join(self.probe._TELEMETRY_ROOT, "atlas")
        self.assertFalse(os.path.isdir(folder))

    def test_second_scan_is_busy(self):
        obj = _obj()
        self.manager._objects = {11: obj}
        reply = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(command("tuned_scan"), reply))
        again = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._inbox_dispatch(command("tuned_scan"), again))
        self.assertEqual(again.code, "TUNED_BUSY")

    def test_status_tuned_validates(self):
        status = self.probe._inbox_status()
        schema.validate_tuned(status["tuned"])
        self.assertEqual(status["tuned"]["state"], "idle")

    def test_parse_tuned_scan_args(self):
        row = command("tuned_scan", {})
        self.assertEqual(cmdbox.parse(json.dumps(row).encode("utf-8"), 1000, ()), (row, None))
        bad = command("tuned_scan", {"x": 1})
        self.assertEqual(cmdbox.parse(json.dumps(bad).encode("utf-8"), 1000, ())[1], "BAD_ARGS")

    def test_tripwires_are_not_called(self):
        obj = _Trip()
        obj.__dict__["id"] = 3
        self.manager._objects = {3: obj}
        reply = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(command("tuned_scan"), reply))
        while self.probe._TUNED.state == "running":
            self.probe._tuned_tick()
        rows = _rows(self.probe._TUNED.out_path)
        kinds = [row["kind"] for row in rows]
        self.assertIn("tuned_on_class", kinds)
        self.assertEqual(rows[-1]["kind"], "tuned_footer")
        self.assertEqual(rows[-1]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
