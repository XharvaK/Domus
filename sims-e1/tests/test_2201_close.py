"""2.20.1: after her answer the game's close goes to the client at once, not on a later pass."""
import sys
import unittest

import test_2180_answer as answers


class _Distributor(object):
    def __init__(self, calls, fails=False):
        self.calls, self.fails = calls, fails

    def process_events(self):
        self.calls.append("process_events")
        if self.fails:
            raise RuntimeError("no client")


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.case = answers.AnswerTests()
        self.case.setUp()
        self.module = sys.modules[type(self.case.probe._E2).__module__]
        self.saved = self.module.Distributor
        self.calls = self.case.service.calls

    def tearDown(self):
        self.module.Distributor = self.saved
        self.case.tearDown()

    def use(self, fails=False):
        distributor = _Distributor(self.calls, fails)
        self.module.Distributor = type("Distributor", (), {"instance": staticmethod(lambda: distributor)})

    def test_the_close_is_sent_right_after_the_answer(self):
        self.use()
        self.case.case.ready()
        self.case.hold_recipes()  # 2.31.0 (W4): her picker is a held window
        ok, connection = self.case.answer("13")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.calls, [("pick", 555, [13]), ("respond", 555, 10001), "process_events"])

    def test_a_failed_send_never_changes_the_answer(self):
        self.use(fails=True)
        self.case.case.ready()
        self.case.hold_recipes()  # 2.31.0 (W4): her picker is a held window
        ok, connection = self.case.answer("13")
        self.assertTrue(ok, connection.lines)
        phases = [(e["phase"], e["finishing_type"]) for e in self.case.case.events()]
        self.assertEqual(phases, [("ACCEPTED", None), ("FINISHED", "ANSWERED")])

    def test_without_the_distributor_the_answer_stands(self):
        self.module.Distributor = None
        self.case.case.ready()
        self.case.hold_recipes()  # 2.31.0 (W4): her picker is a held window
        ok, _ = self.case.answer("13")
        self.assertTrue(ok)
        self.assertEqual(self.calls, [("pick", 555, [13]), ("respond", 555, 10001)])


if __name__ == "__main__":
    unittest.main()
