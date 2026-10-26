"""2.32.0 (PR17, PR18): a pushed act is LEFT_QUEUE only when her queue was read whole (a truncated or incomplete read
counts no miss), and a serialize drop names the row kind and the failing field in its summary."""
import unittest

import test_2160_act as acts
import test_2191_queue as queue


def _row(ids, complete=True, truncated=False):
    row = queue._row(ids)
    row["interactions"]["observation_complete"] = complete
    row["interactions"]["queue_truncated"] = truncated
    return row


class PushedCompletenessTests(unittest.TestCase):
    setUp = acts.ActCommandTests.setUp
    tearDown = acts.ActCommandTests.tearDown
    ready = acts.ActCommandTests.ready
    act = acts.ActCommandTests.act
    events = acts.ActCommandTests.events

    def control(self):
        return self.probe._E2

    def test_a_truncated_queue_never_says_the_act_is_gone(self):
        self.ready()
        self.assertTrue(self.act()[0])
        for _ in range(8):
            self.control().on_poll_row(_row([], truncated=True))
        self.assertEqual([e for e in self.events() if e["phase"] == "UNKNOWN"], [])

    def test_an_incomplete_capture_never_says_the_act_is_gone(self):
        self.ready()
        self.assertTrue(self.act()[0])
        for _ in range(8):
            self.control().on_poll_row(_row([], complete=False))
        self.assertEqual([e for e in self.events() if e["phase"] == "UNKNOWN"], [])

    def test_a_whole_queue_still_counts_the_misses_to_left_queue(self):
        self.ready()
        self.assertTrue(self.act()[0])
        for _ in range(6):
            self.control().on_poll_row(_row([]))
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "LEFT_QUEUE"))


def _writer_drop_detail():
    """The writer's own _drop_detail, compiled alone from its source (the test harness binds the writer's classes
    to its own namespace, which does not carry every module-level helper)."""
    import ast
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "src", "ashley_e1", "writer.py")
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_drop_detail"]
    namespace = {}
    exec(compile(ast.Module(body=found, type_ignores=[]), "writer.py", "exec"), namespace)
    return namespace["_drop_detail"]


class DropDetailTests(unittest.TestCase):
    def setUp(self):
        self.base = queue.acts.ActCommandTests()
        self.base.setUp()
        self.schema = self.base.probe.schema
        self.drop_detail = _writer_drop_detail()

    def tearDown(self):
        self.base.tearDown()

    def test_a_drop_names_the_row_kind_and_the_failing_field(self):
        try:
            raise self.schema.SchemaError("presence shape")
        except self.schema.SchemaError as error:
            detail = self.drop_detail({"event_kind": "presence_snapshot"}, error)
        self.assertEqual(detail, "presence_snapshot: presence shape")
        self.assertLessEqual(len(self.drop_detail({"event_kind": "x" * 500}, self.schema.SchemaError("y" * 500))),
                             120)

    def test_the_summary_carries_a_detail_only_on_a_dropped_summary(self):
        summary = self.schema.make_record("dropped_summary", telemetry_session_id="s", reason="SERIALIZE_FAILURE",
                                          counters={}, writer={"state": "OK", "rotation_index": 0},
                                          drop_detail="presence_snapshot: presence shape")
        self.schema.validate_record(summary)
        other = self.schema.make_record("session_checkpoint", telemetry_session_id="s",
                                        checkpoint_reason="PERIODIC_60S")
        self.assertIsNone(other["drop_detail"])
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_record(dict(other, drop_detail="stray"))


if __name__ == "__main__":
    unittest.main()
