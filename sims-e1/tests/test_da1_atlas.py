"""DA1 2.4.0 atlas_dump. Fakes only."""
import json
import os
import sys
import types
import unittest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from test_binding import install_stubs, load_probe
from test_d10 import command

install_stubs()
from ashley_e1.atlas import AtlasDump
import ashley_e1.cmdbox as cmdbox
import ashley_e1.schema as schema


WHITELIST = (
    "guid64", "name", "is_super", "is_social", "allow_autonomous",
    "allow_user_directed", "require_current_posture", "posture_preferences",
    "static_commodities",
)


def _clock(values):
    pending = list(values)

    def clock():
        if len(pending) > 1:
            return pending.pop(0)
        return pending[0]
    return clock


class _Entry(object):
    def __init__(self, guid, commodity=None):
        self.guid64 = guid
        if commodity is not None:
            self.static_commodity = commodity


class _Commodity(object):
    def __init__(self, guid):
        self.guid64 = guid


class _Affordance(object):
    def __init__(self, guid, name="Sit"):
        self.guid64 = guid
        self.__name__ = name
        self.is_super = True
        self.is_social = False
        self.allow_autonomous = True
        self.allow_user_directed = False
        self._require_current_posture = True
        self.posture_preferences = object()
        self.target_type = "SHOULD_NOT_APPEAR"
        self.commodity_flags = (1, 2)
        self._static_commodities = (
            _Entry(9, _Commodity(4)),
            _Entry(2),
            _Entry("nope"),
        )
        self.extra_field = "nope"


class _BoomMeta(type):
    @property
    def is_social(self):
        raise RuntimeError("boom")


class _Boom(object):
    __metaclass__ = _BoomMeta
    guid64 = 7


class Boom(object, metaclass=_BoomMeta):
    guid64 = 7


class AtlasModuleTests(unittest.TestCase):
    def test_budget_and_chunk_cap(self):
        classes = {index: _Affordance(index) for index in range(5)}
        path = os.path.join(self._dir(), "cap.jsonl")
        dump = AtlasDump(classes, path, budget_ms=5.0, max_per_chunk=200,
                         clock=_clock([0.0, 0.0, 0.006]))
        dump.step()
        self.assertEqual(dump.progress()["done"], 1)
        capped = AtlasDump(classes, path + ".b", budget_ms=5.0, max_per_chunk=2,
                           clock=_clock([0.0]))
        capped.step()
        self.assertEqual(capped.progress()["done"], 2)

    def test_cursor_resumes_without_dup_or_skip(self):
        classes = {"b": _Affordance(2), "a": _Affordance(1), "c": _Affordance(3)}
        path = os.path.join(self._dir(), "cursor.jsonl")
        dump = AtlasDump(classes, path, budget_ms=1000.0, max_per_chunk=2,
                         clock=_clock([0.0]))
        dump.step()
        dump.step()
        dump.step()
        self.assertEqual(dump.state, "done")
        rows = _rows(path)
        guids = [row["guid64"] for row in rows if row["kind"] == "affordance"]
        self.assertEqual(sorted(guids), [1, 2, 3])
        self.assertEqual(len(guids), 3)

    def test_whitelist_caps_and_sorts(self):
        many = tuple(_Entry(index) for index in range(40, 0, -1))
        affordance = _Affordance(5)
        affordance._static_commodities = many
        path = os.path.join(self._dir(), "white.jsonl")
        dump = AtlasDump({"k": affordance}, path, budget_ms=1000.0, clock=_clock([0.0]))
        dump.step()
        self.assertEqual(dump.state, "done")
        row = [item for item in _rows(path) if item["kind"] == "affordance"][0]
        self.assertEqual(set(row) - {"kind"}, set(WHITELIST))
        self.assertNotIn("target_type", row)
        self.assertNotIn("commodity_flags", row)
        self.assertEqual(row["static_commodities"], list(range(1, 33)))
        self.assertLessEqual(len(row["static_commodities"]), 32)
        self.assertEqual(row["posture_preferences"], "object")

    def test_attribute_error_continues(self):
        path = os.path.join(self._dir(), "err.jsonl")
        dump = AtlasDump({"bad": Boom, "good": _Affordance(3)}, path,
                         budget_ms=1000.0, clock=_clock([0.0]))
        dump.step()
        rows = _rows(path)
        kinds = [row["kind"] for row in rows]
        self.assertIn("affordance_error", kinds)
        self.assertIn("affordance", kinds)
        self.assertEqual(dump.state, "done")

    def _dir(self):
        root = os.path.join(os.environ.get("TEMP", "."), "da1-atlas-unit")
        os.makedirs(root, exist_ok=True)
        return root


def _rows(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class AtlasProbeTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, self.calls = load_probe()
        self.probe._start_inbox_pump("import")
        self.interaction = object()

        class _Manager(object):
            def __init__(self):
                self.all_instances_loaded = True
                self._tuned_classes = {}

            @property
            def types(self):
                raise AssertionError("types")

        self.manager = _Manager()
        services = self.probe._services_module
        services.get_instance_manager = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("get_instance_manager"))
        services.tuning_managers = {self.interaction: self.manager}
        resources = types.ModuleType("sims4.resources")
        resources.Types = types.SimpleNamespace(INTERACTION=self.interaction)
        sys.modules["sims4.resources"] = resources

    def test_missing_manager_rejects_without_file(self):
        self.probe._services_module.tuning_managers = {}
        reply = self.probe._InboxReply("helper")
        cmd = command("atlas_dump")
        self.assertFalse(self.probe._inbox_dispatch(cmd, reply))
        self.assertEqual(reply.code, "ATLAS_NO_MANAGER")
        folder = os.path.join(self.probe._TELEMETRY_ROOT, "atlas")
        self.assertFalse(os.path.isdir(folder))

    def test_second_dump_is_busy(self):
        self.manager._tuned_classes = {"a": _Affordance(1)}
        reply = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(command("atlas_dump"), reply))
        again = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._inbox_dispatch(command("atlas_dump"), again))
        self.assertEqual(again.code, "ATLAS_BUSY")

    def test_partial_until_done_then_footer_matches(self):
        self.manager._tuned_classes = {index: _Affordance(index) for index in range(3)}
        reply = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch(command("atlas_dump"), reply))
        progress = self.probe._inbox_status()["atlas"]
        self.assertTrue(progress["file"].endswith(".partial"))
        self.assertTrue(os.path.exists(progress["file"]))
        final = progress["file"][:-len(".partial")]
        self.assertFalse(os.path.exists(final))
        while self.probe._ATLAS.state == "running":
            self.probe._atlas_tick()
        self.assertEqual(self.probe._ATLAS.state, "done")
        self.assertTrue(os.path.exists(final))
        self.assertFalse(os.path.exists(final + ".partial"))
        rows = _rows(final)
        self.assertEqual(rows[0]["kind"], "atlas_header")
        self.assertEqual(rows[0]["total"], 3)
        self.assertEqual(rows[-1]["kind"], "atlas_footer")
        self.assertEqual(rows[-1]["count"] + rows[-1]["errors"], 3)

    def test_status_atlas_validates(self):
        status = self.probe._inbox_status()
        schema.validate_atlas(status["atlas"])
        self.assertEqual(status["atlas"]["state"], "idle")

    def test_parse_atlas_dump_args(self):
        row = command("atlas_dump", {})
        self.assertEqual(cmdbox.parse(json.dumps(row).encode("utf-8"), 1000, ()), (row, None))
        bad = command("atlas_dump", {"x": 1})
        self.assertEqual(cmdbox.parse(json.dumps(bad).encode("utf-8"), 1000, ())[1], "BAD_ARGS")


if __name__ == "__main__":
    unittest.main()
